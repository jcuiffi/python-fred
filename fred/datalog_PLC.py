import paho.mqtt.client as mqtt
import time
import json
import csv

# custom callback for connection response
def on_mqtt_connect(client, userdata, flags, rc):
    if rc==0:
        print('Connection Successful')
        client.connected_flag = True
    else:
        print('Connection Unsuccessful - Error code ', rc)
        client.connected_flag = False

# MQTT message handler
def on_mqtt_message(client, userdata, msg):
    #print(msg)
    message = json.loads(msg.payload)
    print(msg.topic)
    print(time.time())
    print(message)
    
    #is_message = True

# create client with unique client name
client = mqtt.Client('SubTest03')
# attach custom callbacks
client.on_connect = on_mqtt_connect
client.on_message = on_mqtt_message
# create custom flag for connection status
client.connected_flag = False
# start threaded interface loop
client.loop_start()
# broker IP address - change form localhost if needed
broker_address = '192.168.1.14'
# connect to mqtt broker
print('Connecting to ', broker_address)
client.connect(broker_address)
# wait for connection response
while not client.connected_flag:
    time.sleep(.1) # wait 100ms
# start subscribing loop
print('Subscribing - Press Control C to Stop')
# send description messge
client.subscribe('/fred/run_data')
client.subscribe('/fred/cur_data')
client.subscribe('/fred/pwr_data')
# test
while client.connected_flag:
    pass

# stop client loop and disconnect
client.loop_stop()
client.disconnect()