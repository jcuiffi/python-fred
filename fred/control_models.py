"""
Classes for control of the MIT FrED digital twim processes. The 
ManualDynamicTwin class interfaces with dynamic twins - with time dependent
processes. The ManualStateTwin class interfaces with state models of the
process.

Started 2/23/20
Author - J. Cuiffi, Penn State University
"""

from control import Control, pid1
import math
import numpy as np
import logging
import process_models
import threading
import time

class ManualDynamicTwin(Control):
    """
    Runnable FrED control algorithm that can use PID for heater temperature, 
    spool speed, and fiber diameter based on spool speed. 

    Note: Will use PID versus raw duty cycle if pid1.is_running = True
          Currently works with process_models.RegressionDynamicTwin
    """

    def __init__(self, twin=process_models.RegressionDynamicTwin()):
        Control.__init__(self)
        self.twin = twin
        self.interval=.1           # sec
        # control parameters
        self.htrP = 0.02             # .02
        self.htrI = 0.00005          # .0005
        self.htrD = 0.0
        self.htrPIDint = .5         # sec
        self.htrPID_last_time = 0.0
        self.tempPID = pid1()
        self.tempPID.is_running = False
        self.tempPID.iomax = 1.0    # .3  
        self.spoolP = 0.1           # .1
        self.spoolI = 0.5           # .5
        self.spoolD = 0.0
        self.spoolPIDint = .25      # sec
        self.spoolPID_last_time = 0.0
        self.spoolPID = pid1()
        self.spoolPID.is_running = False
        self.spool_cur_dia = 20.0   # mm
        self.wind_set_freq = 0.0
        self.wind_count = 1    
        self.fibP = 0.0
        self.fibI = 0.0
        self.fibD = 0.0
        self.fibPIDint = .5         # sec
        self.fibPID = pid1()

    def setFibPID(self, start=True):
        pass

    def setHtrPID(self, start=True):
        if start:
            self.tempPID.time_last = self.htrPID_last_time = time.time()
            self.tempPID.current_val_last = self.twin.htr_temp
            self.tempPID.iomin = 0.0
            self.tempPID.io = 0.0
            self.tempPID.is_running = True
        else:
            self.tempPID.is_running = False

    def setSpoolPID(self, start=True):
        if start:
            self.spoolPID.time_last = self.spoolPID_last_time = time.time()
            self.spoolPID.current_val_last = self.twin.spool_speed
            self.spoolPID.iomin = 0.0
            self.spoolPID.io = 0.0
            self.spoolPID.out_max_ch = .5
            self.spoolPID.is_running = True
        else:
            self.spoolPID.is_running = False

    def sendSpoolWind(self, auto = False):
        self.is_msg_wind = True
        if auto:
            self.is_auto_wind = True
            self.wind_set_freq = self.calcWind(2)
        else:
            self.is_auto_wind = False

    def calcWind(self, method = 1):
        if method == 1:
            return self.spool_set_pwr * 300.0
        elif method == 2:
            if self._spool_set_speed > 0.0:
                return 600.0 * self._spool_set_speed * 6.732 * math.sqrt(self.twin.feed_speed / self._spool_set_speed)
            else:
                return 0.0
        else:
            return 0.0

    def update(self):
        
        if self.tempPID.is_running:
            if time.time() > (self.htrPID_last_time + self.htrPIDint):
                self.htr_set_pwr = self.tempPID.calc_output(self.htrP, self.htrI, self.htrD, 
                                                self.htr_set_temp,self.twin.htr_temp)
                self.htrPID_last_time = time.time()
        self.twin.htr_pwr = self.htr_set_pwr
        
        if self.spoolPID.is_running:
            if time.time() > (self.spoolPID_last_time + self.spoolPIDint):
                self.spool_set_pwr = self.spoolPID.calc_output(self.spoolP, self.spoolI, self.spoolD, 
                                                    self.spool_set_speed,self.twin.spool_speed)
                self.spoolPID_last_time = time.time()
        #print(self._spool_set_pwr)
        self.twin.spool_pwr = self._spool_set_pwr
        
        if (self.twin.htr_temp >= 75.0):
            self.twin.feed_freq = self._feed_set_freq = (
                                        self._feed_set_speed * 3200.0) 
        else:
            self.twin.feed_freq = 0.0

class ManualStateTwin(Control):
    """
    Runnable FrED control algorithm that can use PID for heater temperature, 
    spool speed, and fiber diameter based on spool speed. 

    Note: Set htr_set_temp, feed_set_speed, and spool_set_speed, fiber_set_dia
          Currently works with process_models.BasicStateTwin, 
            RegressionStateTwin
    """

    def __init__(self, twin=process_models.BasicStateTwin()):
        Control.__init__(self)
        self.twin = twin
        self.interval=.1            # sec
        self.calc_spool = False

    def update(self):
        self.twin.htr_temp = self._htr_set_temp
        if self.twin.htr_temp >= 75.0:
            self.twin.feed_freq = self._feed_set_freq = (
                                            self._feed_set_speed * 3200.0) 
        else:
            self.twin.feed_freq = 0.0
        if self.calc_spool:
            self.twin.spool_speed = self.twin.calc_spool_speed(
                feed=self._feed_set_speed, fdia = self._fiber_set_dia)
        else:
            self.twin.spool_speed = self._spool_set_speed

if __name__ == "__main__":
    # for testing
    logging.basicConfig(level=logging.DEBUG)
    proc = ManualDynamicTwin()
    proc.start()
    proc.htr_set_temp = 100.0
    proc.setHtrPID(True)
    time.sleep(10)
    proc.is_running = False
    proc.join()
    