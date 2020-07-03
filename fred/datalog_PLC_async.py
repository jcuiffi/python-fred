"""
Data logging script for FrED process control by PLC. Pulls in MQTT data from
the PLC  fred program and the ESP IoT power sensor setup. Uses async for
efficency. 

Started 7/3/20
Author - J. Cuiffi, Penn State University
"""

import asyncio
from asyncio_mqtt import Client, MqttError
from datetime import datetime
import time
import json
import csv

async def process_data():
    broker_address = '192.168.1.14'
    path = 'C:/Users/cuiff/Documents/Python/'
    filename = 'test.csv'
    header = (['Time (sec)', 'Run Time (sec)', 'Heater Set (C)', 'Heater Duty (0-1)', 
               'Filament Feed Rate Set (RPS)', 'Spool Wind Rate Set (RPS)', 'Spool Duty (0-1)',
               'Wind B-F Speed (PPS)', 'Filament Diameter Set (mm)', 
               'Heater Actual (C)', 'Filament Feed Rate Actual (RPS)', 
               'Spool Wind Rate Actual (RPS)', 'Wind Direction (R/L)', 'Wind Count (#)',
               'Filament Diameter Actual (mm)','Total Fiber Produced (m)', 
               'Heater Current (mA)','Spool DC Motor Current (mA)','Stepper and 12V Current (mA)',
               'Total Power (W)', 'Total Energy Used (Wh)'])
    cur1_mA = 0.0
    cur2_mA = 0.0
    cur3_mA = 0.0
    pwr_W = 0.0
    energy = 0.0
    new_file_interval = 120.0
    file_start_time = 0.0
    last_log_time = 0.0
    async with Client(broker_address) as client:
        async with client.filtered_messages('/fred/#') as messages:
            await client.subscribe('/fred/#')
            async for message in messages:
                if (message.topic == '/fred/cur_data'):
                    msg = json.loads(message.payload)
                    cur1_mA = msg['cur1']
                    cur2_mA = msg['cur2']
                    cur3_mA = msg['cur3']
                    pwr_W = msg['pwr']
                elif (message.topic == '/fred/run_data'):
                    timestamp = time.time()
                    if (timestamp > (last_log_time + new_file_interval)):
                        file_start_time = timestamp
                        filename = ("log_" + "PLC_Control" + "_" + 
                            datetime.now().strftime("_%Y-%m-%d_%H-%M-%S") + '.csv')
                        energy = 0.0
                        first_row = True
                    else:
                        energy += pwr_W * (timestamp - last_log_time) / 3600.0
                        first_row = False
                    last_log_time = timestamp
                    msg = json.loads(message.payload)
                    msg['cur1'] = cur1_mA
                    msg['cur2'] = cur2_mA
                    msg['cur3'] = cur3_mA
                    msg['time'] = timestamp
                    #print(msg)
                    with open((path + filename), 'a', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        if first_row:
                            writer.writerow(header)
                        writer.writerow([timestamp, (timestamp - file_start_time),
                            (float(msg['Temp_SP']) / 10.0), (float(msg['Duty_Temp']) / 1000.0), msg['Feed_SP'], msg['Spool_SP'],
                            (float(msg['Duty_Spool']) / 1000.0), msg['Wind_SP'], msg['Fib_Dia_SP'], (float(msg['Temp_PV']) / 10.0),
                            msg['Feed_SP'], msg['Spool_PV'], int(msg['Wind_Dir']),
                            msg['Wind_Count'], msg['Fib_Dia_PV'], msg['Fib_Len'],
                            cur2_mA, cur1_mA, cur3_mA, pwr_W, energy ])


asyncio.run(process_data())