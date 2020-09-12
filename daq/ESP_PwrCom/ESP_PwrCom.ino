/* Program for using INA219 current sensors for FrED - broadcasting over Serial
 * Broadcasts each sensor current data (mA) and total system power (W)
 * Uses the Adafuit Huzzah ESP32 Microcontroller
 * Started 7/2/20 J. Cuiffi
 */
#include <Adafruit_INA219.h>

// INA219 I2C definitions, takes ~2.2msec each to sample
Adafruit_INA219 ina219_1(0x41);        // spool (R050)
Adafruit_INA219 ina219_2(0x44);        // heater (R050)
Adafruit_INA219 ina219_3(0x40);        // steppers and electronics (R100)

// variables
int cur1_num = 0;                      // number of current readings
float cur1_tot = 0.0;                  // accumulating total current
float cur1_ave = 0.0;                  // current average over interval
int cur2_num = 0;                      // number of current readings
float cur2_tot = 0.0;                  // accumulating total current
float cur2_ave = 0.0;                  // current average over interval
int cur3_num = 0;                      // number of current readings
float cur3_tot = 0.0;                  // accumulating total current
float cur3_ave = 0.0;                  // current average over interval
int pwr_num = 0;                       // number of pwr readings
float pwr_tot = 0.0;                   // accumulating total power 
float pwr_ave = 0.0;                   // power average over interval
unsigned long cur_interval = 1000000;   // current publish interval, usec
unsigned long cur_timestamp = 0;       // current publish timestamp, usec
unsigned long cur_last_timestamp = 0;  // current last timestamt, usec
unsigned long pwr_interval = 1000000;  // pwr publish interval, usec
unsigned long pwr_timestamp = 0;       // pwr publish timestamp, usec

void setup() {
  // Start serial monitor
  Serial.begin(9600);
  delay(2000);
  
  // Attach INA219s I2C
  if (!ina219_1.begin()){
    Serial.println("Sensor 1 connection fail.");
  }
  if (!ina219_2.begin()){
    Serial.println("Sensor 2 connection fail.");
  }
  if (!ina219_3.begin()){
    Serial.println("Sensor 3 connection fail.");
  }

  // reset timestamps
  cur_timestamp = micros();
  cur_last_timestamp = micros();
  pwr_timestamp = micros();
}

void loop() {
  
  // read currents, average if at interval and add to accumulating pwr
  cur1_tot += ina219_1.getCurrent_mA();
  cur1_num++;
  cur2_tot += ina219_2.getCurrent_mA();
  cur2_num++;
  cur3_tot += ina219_3.getCurrent_mA();
  cur3_num++;
  
  if (micros() >= (cur_timestamp + cur_interval)) {
    cur_last_timestamp = cur_timestamp;
    cur_timestamp = micros();
    cur1_ave = (cur1_tot * 2.0) / float(cur1_num);
    cur1_tot = 0.0;
    cur1_num = 0;
    cur2_ave = (cur2_tot * 2.0) / float(cur2_num);
    cur2_tot = 0.0;
    cur2_num = 0;
    cur3_ave = cur3_tot / float(cur3_num);
    cur3_tot = 0.0;
    cur3_num = 0;
    // accumulate power
    pwr_tot += (cur1_ave + cur2_ave + cur3_ave) * ina219_1.getBusVoltage_V() / 1000.0;
    pwr_num++;
    // send data
    Serial.print("Current: Spool = ");
    Serial.print(cur1_ave);
    Serial.print("mA, Heater = ");
    Serial.print(cur2_ave);
    Serial.print("mA, Steppers and Electronics = ");
    Serial.print(cur3_ave);
    Serial.println("mA");
  }
  if (micros() >= (pwr_timestamp + pwr_interval)) {
    pwr_timestamp = micros();
    // send data
    Serial.print("Total System Power = ");
    Serial.print(pwr_tot / float(pwr_num));
    Serial.println("W");
    // rest pwr
    pwr_tot = 0.0;
    pwr_num = 0;
  }

  // end of main loop
}
