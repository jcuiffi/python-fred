/* Program for using INA219 current sensors for FrED - transmitting over MQTT
 * Broadcasts each sensor data "/fred/cur_data" (100ms) and total power 1/sec "/fred/tot_pwr/"
 * Uses the Adafuit Huzzah ESP32 Microcontroller
 * Started 7/2/20 J. Cuiffi
 */
#include <WiFi.h>
#include <ArduinoMqttClient.h>
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
unsigned long cur_interval = 250000;   // current publish interval, usec
unsigned long cur_timestamp = 0;       // current publish timestamp, usec
unsigned long cur_last_timestamp = 0;  // current last timestamt, usec
unsigned long pwr_interval = 1000000;  // pwr publish interval, usec
unsigned long pwr_timestamp = 0;       // pwr publish timestamp, usec

// WiFi Login Information
const char* ssid = "Cuifi";
const char* password = "P@ssw0rd";

// MQTT
WiFiClient wifiClient;       // create a wifi client object
MqttClient mqtt(wifiClient); // create a mqt client object
const char broker[] = "192.168.1.14";  // raspberry pi mosquitto broker
int port = 1883;  // broker port
// define message topics
const char topic_cur[] = "/fred/cur_data";
const char topic_pwr[] = "/fred/pwr_data";

void setup() {
  // Start serial monitor
  Serial.begin(9600);
  delay(2000);
  // connect to WiFi connection
  WiFi.begin(ssid,password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("Connecting...");
  }
  Serial.print("Connected, IP Address: ");
  Serial.println(WiFi.localIP());

  // Subscribe to MQTT broker
  if (!mqtt.connect(broker, port)) {
    Serial.println("MQTT Connection Failed!");
    Serial.println(mqtt.connectError());
    while (1);
  } else {
    Serial.print("Connected to MQTT broker: ");
    Serial.println(broker);
  }
  
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
    // send MQTT
    mqtt.beginMessage(topic_cur);
    mqtt.print("{\"cur1\": ");
    mqtt.print(cur1_ave);
    mqtt.print(", \"cur2\": ");
    mqtt.print(cur2_ave);
    mqtt.print(", \"cur3\": ");
    mqtt.print(cur3_ave);
    mqtt.print(", \"pwr\": ");
    mqtt.print(pwr_tot / float(pwr_num));
    mqtt.print("}");
    mqtt.endMessage();
  }
  if (micros() >= (pwr_timestamp + pwr_interval)) {
    pwr_timestamp = micros();
    // send MQTT
    mqtt.beginMessage(topic_pwr);
    mqtt.print("{\"sys_pwr\": ");
    mqtt.print(pwr_tot / float(pwr_num));
    mqtt.print("}");
    mqtt.endMessage();
    // rest pwr
    pwr_tot = 0.0;
    pwr_num = 0;
  }

  // end of main loop
}
