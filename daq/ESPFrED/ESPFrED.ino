/* Program for interfacing MIT FrED Hardware with Python PC Control  
 * Uses the Adafuit Huzzah ESP32 Microcontroller
 * Started 3/17/20 J. Cuiffi
 */
//#include <Adafruit_MAX31865.h>
// note using a modified <Adafruit_MAX31856.h> to speed up reading - include .h and .cpp
#include <Adafruit_MAX31856.h>
#include <Adafruit_INA219.h>

// Output Pins
const int enc_pinA =        A2;     // interrrupt input for encoder A pulses
const int enc_pinB =        A1;     // interrrupt input for encoder B pulses
const int feed_dir_pin =    12;     // Spool direction, LOW = fwd(default), HIGH = rev
const int feed_step_pin =   15;     // CH4 Pulses for feed stepper drive
const int heater_pin =      27;     // CH0 PWM @ 15kHz for heater, 10bit duty (0-1023)
const int lsw1_pin =        A3;     // limit switch 1 R, uses external pull down
const int lsw2_pin =        A4;     // limit switch 2 L, uses external pull down
const int pt100_cs =        A5;     // chip select for pt100 SPI interface
const int spool_dir_pinA =  A0;     // Spool direction, HIGH = fwd (B LOW)
const int spool_dir_pinB =  21;     // Spool direction, HIGH = rev (A LOW)
const int stop_pin =        13;     // stop button, uses INPUT_PULLUP
const int spool_motor_pin = 33;     // CH2 PWM @ 15kHz for heater, 10bit duty (0-1023)
const int wind_step_pin =   32;     // CH6 Pulses for spooling back-forth stepper drive
const int wind_dir_pin =    14;     // Spool step direction, HIGH = R, LOW = L(default)

// Internal PWM channels
const int heater_ch = 0;
const int spool_motor_ch = 2;
const int feed_ch = 4;
const int wind_ch = 6;

// pt100 SPI MAX31865 definitions
// TODO - note SPI is slow, takes ~7.5msec to sample
// Note: switching to type T TC for now
//Adafruit_MAX31865 pt_100 = Adafruit_MAX31865(pt100_cs);
Adafruit_MAX31856 maxthermo = Adafruit_MAX31856(pt100_cs);
//#define RREF      4300.0 // had to adjust for wrong chip TODO - change with new chip
//#define RNOMINAL  100.0
// INA219 I2C definitions, takes ~2.2msec each to sample
Adafruit_INA219 ina219_1(0x40);      // spool motor
Adafruit_INA219 ina219_2(0x41);      // heater (R050) not averaged
Adafruit_INA219 ina219_3(0x44);      // steppers and electronics (R050) not averaged

// control variables
// spool current variables
int cur_index = 0;                     // index for averaging current
float current_ave = 0.0;               // current average over interval
unsigned long cur_interval = 25000;    // current read interval, usec
unsigned long cur_timestamp = 0;       // current read timestamp, usec
float currents[25];                    // array for averaging current readings
// spool encoder variables
volatile unsigned long enc_count = 0;  // current encoder pulse count
unsigned long enc_interval = 25000;    // encoder read interval, usec
float enc_pps = 0.0;                   // encoder speed, pulses/sec
unsigned long enc_timestamp = 0;       // encoder read timestamp, usec
int wind_count = 1;                    // current number of winding passes (starts at 1)
bool is_winding_R = true;              // is the spool moving right
// communication variables
char command = '\0';                   // command character incoming from serial
bool is_parsing = false;               // in the middle of reading a message string
bool is_initializing = false;          // initializing spool position
const int msgdata_max = 10;            // maximum number of characters in message string
char msgdata[msgdata_max];             // string for data message
int readindex = 0;                     // index for incoming string
char tempchar = '\0';                  // temporary character hold

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(100);
  delay(100);
    
  // configure general I/O pins
  pinMode(feed_dir_pin, OUTPUT);
  pinMode(lsw1_pin, INPUT);
  pinMode(lsw2_pin, INPUT);
  pinMode(spool_dir_pinA, OUTPUT);
  pinMode(spool_dir_pinB, OUTPUT);
  pinMode(stop_pin, INPUT_PULLUP);
  pinMode(wind_dir_pin, OUTPUT);
  digitalWrite(wind_dir_pin, HIGH);  // set to direction right
  is_winding_R = true;
  
  // configure encoder interrupt  
  pinMode(enc_pinA, INPUT);
  attachInterrupt(digitalPinToInterrupt(enc_pinA), count, CHANGE);
  pinMode(enc_pinB, INPUT);
  attachInterrupt(digitalPinToInterrupt(enc_pinB), count, CHANGE);

  // Attach pt100 SPI
  //pt_100.begin(MAX31865_2WIRE);
  maxthermo.begin();
  maxthermo.setThermocoupleType(MAX31856_TCTYPE_T);
  maxthermo.contconfig();
  // Attach INA219s I2C
  ina219_1.begin();
  ina219_2.begin();
  ina219_3.begin();

  // Setup frequency channels and attach to pins
  // Heater - channel 0
  ledcSetup(heater_ch, 15000, 10);
  ledcAttachPin(heater_pin, heater_ch);
  // Spool - channel 2
  ledcSetup(spool_motor_ch, 15000, 10);
  ledcAttachPin(spool_motor_pin, spool_motor_ch);
  // Feed - channel 4
  ledcSetup(feed_ch, 1000, 10);
  ledcAttachPin(feed_step_pin, feed_ch);
  // Spool - channel 6
  ledcSetup(wind_ch, 1000, 10);
  ledcAttachPin(wind_step_pin, wind_ch);

  delay(100);
  cur_timestamp = micros();
  enc_timestamp = micros();
}

void loop() {
  // check for input serial commands
  readserial();
  
  // check for pushbutton stop
  if (digitalRead(stop_pin) == LOW){
    ledcWrite(heater_ch, 0);
    ledcWrite(spool_motor_ch, 0);
    ledcWriteTone(feed_ch, 0);
    ledcWriteTone(wind_ch, 0);
    digitalWrite(wind_dir_pin, HIGH);
    is_winding_R = true;
    digitalWrite(feed_dir_pin, LOW);
    digitalWrite(spool_dir_pinA, LOW);
    digitalWrite(spool_dir_pinB, LOW);
    wind_count = 1;
  }
  
  // check for spool limit switches and change direction
  if (digitalRead(lsw1_pin) == HIGH){  // on right
    if (is_winding_R == true){  // increment wind count
      wind_count += 1;
      digitalWrite(wind_dir_pin, LOW);
      is_winding_R = false;
    }
  } else if (digitalRead(lsw2_pin) == HIGH){  // on left
    if (is_winding_R == false){  // increment wind count
      if (is_initializing == true){  // stop at left limit switch
        ledcWriteTone(wind_ch, 0);
        is_initializing = false;
        wind_count = 1;
      } else {
        wind_count += 1;   
      }
      digitalWrite(wind_dir_pin, HIGH);
      is_winding_R = true;
    }
  }
  
  // update encoder speeed at defined interval
  if (micros() >= (enc_timestamp + enc_interval)){
    enc_pps = float(enc_count * 1000000) / float(micros() - enc_timestamp); 
    enc_timestamp = micros();
    enc_count = 0;
  }

  // read current, average if at interval
  currents[cur_index] = ina219_1.getCurrent_mA(); // takes ~2.2msec to sample
  cur_index++;
  if (micros() >= (cur_timestamp + cur_interval)) {
    float tot = 0.0;
    for (int i=0; i < cur_index; i++) {
      tot += currents[i];
    }
    current_ave = tot / float(cur_index);
    cur_timestamp = micros();
    cur_index = 0;
  }
  if (cur_index >= 25 ){
    cur_timestamp = micros();
    cur_index = 0;
  }
  // end of main loop
}

// Increment encoder pulse count - on an interrupt
void count(){
  enc_count++;
}

// Check and parse serial commands - non-blocking (mostly)
// Note - exception handling will set parameters to 0 
void readserial(){
  // look for command
  if (Serial.available() > 0){
    command = Serial.read();
    if (command == 'S'){
      // stop
      ledcWrite(heater_ch, 0);
      ledcWrite(spool_motor_ch, 0);
      ledcWriteTone(feed_ch, 0);
      ledcWriteTone(wind_ch, 0);
      digitalWrite(wind_dir_pin, HIGH);
      is_winding_R = true;
      digitalWrite(feed_dir_pin, LOW);
      digitalWrite(spool_dir_pinA, LOW);
      digitalWrite(spool_dir_pinB, LOW);
      wind_count = 1;
      command = '\0';
      is_parsing = false;
    } else if (command == 'I'){  // inititalize spool to home at 500 PPS
      is_initializing = true;
      digitalWrite(wind_dir_pin, LOW);
      is_winding_R = false;
      ledcWriteTone(wind_ch, 500.0);
      command = '\0';
      is_parsing = false;
    } else if (command == 'D'){  // send data
      senddata();
      command = '\0';
      is_parsing = false;
    } else if (command == 'H'){  // receiving heater duty cycle
      is_parsing = true;
      readindex = 0;
    } else if (command == 'f'){  // receiving feed direction 0 = fwd
      tempchar = Serial.read();
      digitalWrite(feed_dir_pin, String(tempchar).toInt());
      is_parsing = false;
    } else if (command == 'F'){  // receiving feed speed PPS
      is_parsing = true;
      readindex = 0;
    } else if (command == 'p'){  // receiving spool direction 0 = fwd
      tempchar = Serial.read();
      if (String(tempchar).toInt() == 0){
        digitalWrite(spool_dir_pinA, HIGH);
        digitalWrite(spool_dir_pinB, LOW);
      } else {
        digitalWrite(spool_dir_pinA, LOW);
        digitalWrite(spool_dir_pinB, HIGH);
      }
      is_parsing = false;
    } else if (command == 'P'){  // receiving spool duty cycle
      is_parsing = true;
      readindex = 0;
    } else if (command == 'w'){  // receiving wind direction 1 = right
      tempchar = Serial.read();
      digitalWrite(wind_dir_pin, String(tempchar).toInt());
      if (String(tempchar).toInt() == 1){
        is_winding_R = true;
      } else {
        is_winding_R = false;
      }
      is_parsing = false;
    } else if (command == 'W'){  // receiving wind B/F speed
      is_parsing = true;
      readindex = 0;
    } else { // junk
      command = '\0';
      is_parsing = false;
    }
  }
  // if_parsing, reading duty cycles and pulses/sec
  while ((Serial.available() > 0) && (is_parsing == true) && (readindex < msgdata_max)){
    tempchar = Serial.read();
    if (tempchar == '\r'){  // end of message
      msgdata[readindex] = '\0';
      
      if (command == 'H'){  // incoming heater duty 0.0-1.0
        ledcWrite(heater_ch, int(String(msgdata).toFloat() * 1023.0));
      } else if (command == 'F'){ // incoming feed PPS
        ledcWriteTone(feed_ch, String(msgdata).toFloat());
      } else if (command == 'P'){ // incoming spool duty 0.0-1.0
        ledcWrite(spool_motor_ch, int(String(msgdata).toFloat() * 1023.0));
      } else if (command == 'W'){ // incoming wind PPS
        ledcWriteTone(wind_ch, String(msgdata).toFloat());
      }
      readindex = 0;
      is_parsing = false;
    } else {
      msgdata[readindex] = tempchar;
      readindex++;
    }
  }
  readindex = 0;
  command = '\0';
  msgdata[0] = '\0';
  is_parsing = false;
  // end of read serial
}

// Send data over serial connection
// 'D,'htr temp (C)','spool speed (PPS)','spool current (mA)','heater current (mA)','step_elec current(mA)','wind dir','wind count'\r\n'
void senddata(){
  Serial.print("D,");
  //Serial.print(pt_100.temperature(RNOMINAL, RREF));  // not averaged - takes ~7.5msec to sample
  // note modifed function below
  Serial.print(maxthermo.readThermocoupleTemperature2());
  Serial.print(",");
  Serial.print(enc_pps);
  Serial.print(",");
  Serial.print(current_ave);
  Serial.print(",");
  Serial.print(ina219_2.getCurrent_mA() * 2.0);
  Serial.print(",");
  Serial.print(ina219_3.getCurrent_mA() * 2.0);
  Serial.print(",");
  Serial.print(is_winding_R);
  Serial.print(",");
  Serial.println(wind_count);
}
