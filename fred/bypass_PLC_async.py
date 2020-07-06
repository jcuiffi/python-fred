"""
Script for runnign custom spool speed claculation, bypassing PLC control.
Calculates new spool speed based on model and adjustments from process data. 
Note: MQTT Topics
/fred/bypass/PV_data - data from PLC for bypass
/fred/bypass/SP_data - data to PLC for bypass

Started 7/5/20
Author - J. Cuiffi, Penn State University
"""

import asyncio
from asyncio_mqtt import Client, MqttError
from datetime import datetime
import time
import math
import json
import csv

async def bypass_control():
    broker_address = '192.168.1.14'
    timestamp = last_time = time.time()
    PID_P = 0.0
    PID_I = 0.4
    I_adj = 0.0
    PID_adj = 0.0
    max_adj = .25
    min_adj = -.25

    async with Client(broker_address) as client:
        async with client.filtered_messages('/fred/bypass/PV_data') as messages:
            await client.subscribe('/fred/bypass/PV_data')
            async for message in messages:
                timestamp = time.time()
                msg = json.loads(message.payload)
                if(int(msg['Fib_Dia_SP']) > 0):
                    #print(msg)
                    fib_dia_sp = float(msg['Fib_Dia_SP']) / 1000.0
                    # calculate target spool speed based on model
                    calc_spool_SP = ((float(msg['Feed_SP']) / (fib_dia_sp / 6.3)**2))
                    # make adjusmetns with PID
                    error = msg['Fib_Dia_PV'] -  fib_dia_sp
                    P_adj = PID_P * error
                    I_adj += PID_I * error * (timestamp - last_time)
                    PID_adj = P_adj + I_adj
                    if (PID_adj > max_adj):
                        PID_adj = max_adj
                    elif (PID_adj < min_adj):
                        PID_adj = min_adj
                    #print(PID_adj)
                    msg_out = {}
                    msg_out['Spool_SP'] = calc_spool_SP + PID_adj
                    #print(json.dumps(msg_out))
                    # send spool speed update
                    await client.publish(topic='/fred/bypass/Spool_SP', payload=json.dumps(msg_out))
                last_time = timestamp

asyncio.run(bypass_control())