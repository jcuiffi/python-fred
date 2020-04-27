"""
Classes for control of the MIT FrED process. The Control base class can be used
as a parent class for each control algoritm. Override "update()" to implement
algorithm. The ManualDAQ class is used to control FrED through the ESP 32 
microcontroller and a serial connection - see "ESPFrED.ino". The pid1 class is a 
basic PID implementation for closed loop control.

Started 2/23/20
Author - J. Cuiffi, Penn State University
"""

import datetime
import logging
import math
import numpy as np
import process_models
import serial
import threading
import time

class Control(threading.Thread):
    """
    Thread class that defines a runnable FrED control algorithm. Override
    "update()" to implement custom control algorithm.
 
    Attributes
    ----------
        twin (process_models.ProcessTwin): Digital twin model, if needed.
        - Conrol target settings
        feed_set_freq (float): Feed stepper drive frequency setting, 
                               0.0-320.0 (Hz).
        feed_set_speed (float): Feed set stepper speed, 0.0.000-.1 (RPS). 
        fiber_set_dia (float): Fiber set diameter, 0.0-nozzle diameter (mm).
        htr_set_pwr (float): Heater set power setting, 0.0-1.0 (0-100%).
        htr_set_temp (float): Heater set temperature, 20.0-120.0 (C).
        spool_set_pwr (float): Spool motor drive setting, 0.0-1.0 (0-100%).
        spool_set_speed (float): Winding spool set speed, 0.0-1.5 (RPS).
        wind_set_freq (float): Winding back/forth set PPS (Hz)
        - Control algorithm settings
        debug_log_interval (float)(default=1.0): Interval between debug logs 
                                                 (sec). 
        interval (float)(default=.1): Interval between process calculation
                                       updates (sec).
        is_running (bool): Stay in main running loop. Set to False to stop run.
        
    Methods
    -------
        debug_log_data (): Logs data to debug. Can be overridden.
        run (): Thread override to run the process. DO NOT call directly.
                Use ProcessTwin.start() Stop with is_running = False.
        update (): Override this method to calculate updated control values.
    """
    
    def __init__(self):
        threading.Thread.__init__(self)
        self.logging = logging.getLogger(__name__)
        self.lock = threading.Lock()

        # twin model
        self.twin = process_models.ProcessTwin()
        # target settings
        self._feed_set_freq = 0.0           # steps/s
        self._feed_set_speed = 0.0          # RPS
        self._fiber_set_dia = 0.0           # mm
        self._htr_set_pwr = 0.0             # 0.0-1.0 (0.0-100.0%)
        self._htr_set_temp = 20.0           # C
        self._spool_set_pwr = 0.0           # 0.0-1.0 (0.0-100.0%)
        self._spool_set_speed = 0.0         # RPS
        self._wind_set_freq = 0.0           # PPS
        # process parameters
        self.debug_log_interval = 1.0       # sec
        self.interval = .1                  # sec
        self.is_running = False             # bool
        # internal parameters
        self.cur_time = None                # sec UNIX time
        self.prev_time = None               # sec UNIX time
        self.debug_log_prev_time = None     # sec UNIX time
    
    @property
    def feed_set_freq(self):
        return self._feed_set_freq

    @feed_set_freq.setter
    def feed_set_freq(self, value):
        if (value < 0.0):
            self._feed_set_freq = 0.0
            self.logging.info('Feed set frequency must be > 0.0')
        elif (value > 320.0):
            self._feed_set_freq = 320.0
            self.logging.info('Feed set frequency must be < 320.0')
        else:
            self._feed_set_freq = value
    
    @property
    def feed_set_speed(self):
        return self._feed_set_speed

    @feed_set_speed.setter
    def feed_set_speed(self, value):
        if (value < 0.0):
            self._feed_set_speed = 0.0
            self.logging.info('Feed set speed must be > 0.0')
        elif (value > .1):
            self._feed_set_speed = .1
            self.logging.info('Feed set speed must be < 0.1')
        else:
            self._feed_set_speed = value

    @property
    def fiber_set_dia(self):
        return self._fiber_set_dia
    
    @fiber_set_dia.setter
    def fiber_set_dia(self, value):
        if (value < 0.0):
            self._fiber_set_dia = 0.0
            self.logging.info('Fiber set diameter must be > 0.0')
        elif (value > (self.twin.FIL_FEED_R*2.0)):
            self._fiber_set_dia = (self.twin.FIL_FEED_R * 2.0)
            self.logging.info('Fiber set diamter must be < {0:.3f}'.format(
                                self.twin.FIL_FEED_R * 2.0))
        else:
            self._fiber_set_dia = value

    @property
    def htr_set_pwr(self):
        return self._htr_set_pwr
    
    @htr_set_pwr.setter
    def htr_set_pwr(self, value):
        if (value < 0.0):
            self._htr_set_pwr = 0.0
            self.logging.info('Heater set power must be > 0.0')
        elif (value > 1.0):
            self._htr_set_pwr = 1.0
            self.logging.info('Heater set power must be < 1.0')
        else:
            self._htr_set_pwr = value

    @property
    def htr_set_temp(self):
        return self._htr_set_temp

    @htr_set_temp.setter
    def htr_set_temp(self, value):
        if (value < 20.0):
            self._htr_set_temp = 20.0
            self.logging.info('Heater set temperature must be > 20.0')
        elif (value > 120.0):
            self._htr_set_temp = 120.0
            self.logging.info('Heater set temperature must be < 120.0')
        else:
            self._htr_set_temp = value

    @property
    def spool_set_pwr(self):
        return self._spool_set_pwr
    
    @spool_set_pwr.setter
    def spool_set_pwr(self, value):
        if (value < 0.0):
            self._spool_set_pwr = 0.0
            self.logging.info('Spool set power must be > 0.0')
        elif (value > 1.0):
            self._spool_set_pwr = 1.0
            self.logging.info('Spool set power must be < 1.0')
        else:
            self._spool_set_pwr = value

    @property
    def spool_set_speed(self):
        return self._spool_set_speed
    
    @spool_set_speed.setter
    def spool_set_speed(self, value):
        if (value < 0.0):
            self._spool_set_speed = 0.0
            self.logging.info('Spool set speed must be > 0.0')
        elif (value > 1.5):
            self._spool_set_speed = 1.5
            self.logging.info('Spool set speed must be < 1.5')
        else:
            self._spool_set_speed = value

    @property
    def wind_set_freq(self):
        return self._wind_set_freq
    
    @wind_set_freq.setter
    def wind_set_freq(self, value):
        if (value < 0.0):
            self._wind_set_freq = 0.0
            self.logging.info('Wind frequency must be > 0.0')
        else:
            self._wind_set_freq = value

    def debug_log_data(self):
        """
        Logs current twin data at debug level - can be overridden.
        Args: None
        Returns: None
        """
        self.logging.debug('htr_set_pwr(%):{0:.3f}, '.format(self._htr_set_pwr) 
                           + 'feed_set_freq(steps/s):{0:.1f}, '
                           .format(self._feed_set_freq) +
                           'spool_set_pwr(%):{0:.3f}, '
                           .format(self._spool_set_pwr))
        
    def run(self):
        """
        Thread override to run the process. DO NOT call directly.
        Use Control.start()
        Stop by setting is_Running to False.
        Args: None
        Returns: None
        """
        self.logging.info('Starting System Control')
        self.is_running = True
        self.prev_time = self.debug_log_prev_time = time.time()
        self.logging.info('Control Start Time: ' + 
            datetime.datetime.fromtimestamp(self.prev_time).isoformat())
        while(self.is_running):
            self.cur_time = time.time()
            if (self.cur_time >= (self.prev_time + self.interval)):
                with self.lock:
                    self.update()
                self.prev_time = self.cur_time
            if (self.cur_time >= (self.debug_log_prev_time + 
                                  self.debug_log_interval)):
                self.debug_log_data()
                self.debug_log_prev_time = self.cur_time
        self.logging.info('Control Stop Time:' + 
            datetime.datetime.fromtimestamp(time.time()).isoformat())
    
    def update(self):
        """
        Override this method to calculate updated control values at interval.
        Args: None
        Returns: None
        """
        # read inputs
        # calculate response
        # set outputs
        pass

class ManualDAQ(Control):
    """
    Thread class that controls FrED through an ESP 32 mirocontroller.
 
    """

    def __init__(self):
        Control.__init__(self)
        
        self.interval = .001    # override run interval, use update
        self.get_act_int = .01  # sec, updated as rapidly as possible
        self.update_last_time = time.time()
        self.is_first_update = True
        # control parameters
        self.htrP = 0.04
        self.htrI = 0.0005
        self.htrD = 0.0
        self.htrPIDint = .5     # sec
        self.htrPID_last_time = None
        self.tempPID = pid1()
        self.tempPID.iomax = .3  
        self.feed_dir = True    # FWD
        self.spool_dir = True   # FWD
        self.spoolP = 0.1
        self.spoolI = 0.5
        self.spoolD = 0.0
        self.spoolPIDint = .25   # sec
        self.spoolPID_last_time = None
        self.spoolPID = pid1()
        self.spool_cur_dia = 20.0   # mm
        self.wind_set_freq = 0.0
        self.is_auto_wind = False
        self.wind_dir = True    # Right
        self.wind_count = 1    
        self.fibP = 0.0
        self.fibI = 0.0
        self.fibD = 0.0
        self.fibPIDint = .5     # sec
        self.fibPID = pid1()
        self.ser = None         # serial connection to FrED
        # rolling averages
        self.fiber_ave_dia = 0.0            # rolling ave diameter
        self.fiber_std_dia = 0.0            # rolling std dev
        self.rolling_time = 60.0            # rolling time period sec
        self.roll_index = 0
        self.roll_times = np.zeros(1200)  # should be enough to hold 60sec, .05refresh
        self.fib_dias = np.zeros(1200)
        # current/actual values
        self.htr_temp = 0.0     # C
        self.feed_speed = 0.0   # RPS
        self.spool_speed = 0.0  # RPS
        self.fiber_dia = 0.0    # mm
        self.fiber_len = 0.0    # m
        self.htr_current = 0.0  # mA
        self.spool_current = 0.0# mA
        self.step_current = 0.0 # mA
        self.sys_power = 0.0    # W
        self.sys_energy = 0.0   # Wh
        # testing values
        self.time1 = 0
        self.time2 = 0
        self.time3 = 0
        self.time4 = 0
        self.time5 = 0
        self.time6 = 0
        # communication info
        self.msg_datareq = 'D\r\n'.encode()
        self.is_msg_datareq = False
        self.msg_htr = 'H0.0\r\n'
        self.is_msg_htr = False
        self.msg_feed_dir_F = 'f0\r\n'
        self.msg_feed_dir_R = 'f1\r\n'
        self.msg_feed = 'F0.0\r\n'
        self.is_msg_feed = False
        self.msg_spool_dir_F = 'p0\r\n'
        self.msg_spool_dir_R = 'p1\r\n'
        self.msg_spool = 'P0.0\r\n'
        self.is_msg_spool = False
        self.msg_wind_dir_L = 'w0\r\n'
        self.msg_wind_dir_R = 'w1\r\n'
        self.msg_wind = 'W0.0\r\n'
        self.is_msg_wind = False
        self.msg_init = 'I\r\n'
        self.is_msg_init = False
        self.msg_stop = 'S\r\n'.encode()
        self.is_msg_stop = False

    def connect(self, fred_com = 'COM5', micr_com = 'COM4'):
        try:
            self.ser = serial.Serial(fred_com, 9600, timeout=1)
            self.ser.reset_input_buffer()
            self.ser2 = serial.Serial(micr_com, 9600, timeout=1)
            self.ser2.reset_input_buffer()
            return True
        except serial.SerialException:
            self.logging.info('Issue Connecting to Serial Ports.')
            return False

    def disconnect(self):
        try:
            self.ser.close()
            self.ser2.close()
            return True
        except serial.SerialException:
            self.logging.info('Issue Disconnecting from Serial Ports.')
            return False
    
    def sendDataReq(self):
        self.is_msg_datareq = True

    def sendHtr(self):
        self.is_msg_htr = True

    def sendFeed(self):
        self._feed_set_freq = self._feed_set_speed * 3200.0
        self.is_msg_feed = True

    def sendSpool(self):
        self.is_msg_spool = True
        if self.is_auto_wind:
            self.sendSpoolWind(True)

    def sendSpoolWind(self, auto = False):
        self.is_msg_wind = True
        if auto:
            self.is_auto_wind = True
            self.wind_set_freq = self.calcWind(2)
        else:
            self.is_auto_wind = False

    def setFibPID(self, start=True):
        pass

    def setHtrPID(self, start=True):
        if start:
            self.tempPID.time_last = self.htrPID_last_time = time.time()
            self.tempPID.current_val_last = self.htr_temp
            self.tempPID.iomin = 0.0
            self.tempPID.io = 0.0
            self.tempPID.is_running = True
        else:
            self.tempPID.is_running = False

    def setSpoolPID(self, start=True):
        if start:
            self.spoolPID.time_last = self.spoolPID_last_time = time.time()
            self.spoolPID.current_val_last = self.spool_speed
            self.spoolPID.iomin = 0.0
            self.spoolPID.io = 0.0
            self.spoolPID.out_max_ch = .5
            self.spoolPID.is_running = True
        else:
            self.spoolPID.is_running = False

    def sendInit(self):
        self.is_msg_init = True
        self.is_auto_wind = False
        self.fiber_len = 0.0
        self.sys_energy = 0.0
        self.wind_set_freq = 0.0

    def sendStop(self):
        self.is_msg_stop = True

    def calcWind(self, method = 1):
        if method == 1:
            return self.spool_set_pwr * 300.0
        elif method == 2:
            if self._spool_set_speed > 0.0:
                return 600.0 * self._spool_set_speed * 6.732 * math.sqrt(self.feed_speed / self._spool_set_speed)
            else:
                return 0.0
        else:
            return 0.0

    def debug_log_data(self):
        """
        Logs current twin data at debug level - can be overridden.
        Args: None
        Returns: None
        """
        self.logging.debug((self.time1,self.time2,self.time3,self.time4,self.time5,self.time6))
        #self.logging.debug('htr_set_pwr(%):{0:.3f}, '.format(self._htr_set_pwr) 
        #                   + 'feed_set_freq(steps/s):{0:.1f}, '
        #                   .format(self._feed_set_freq) +
        #                   'spool_set_pwr(%):{0:.3f}'
        #                   .format(self._spool_set_pwr))

    def update(self):
        self.time1 = time.time()
        if self.is_first_update:
            self.update_last_time = time.time()
            self.is_first_update = False
        # read actuals
        try:
            self.ser.write(self.msg_datareq)
            inmsg = self.ser.readline().decode('ASCII')
            #self.logging.debug(inmsg)
            inmsgs = inmsg.split(sep=',')
            self.htr_temp = float(inmsgs[1])
            self.spool_speed = float(inmsgs[2]) / 8400.0
            self.spool_current = float(inmsgs[3])
            self.htr_current = float(inmsgs[4])
            self.step_current = float(inmsgs[5])
            self.wind_dir = int(inmsgs[6])
            temp_wind_count = int(inmsgs[7])
            if temp_wind_count > self.wind_count:
                self.spool_cur_dia += 2 * self.fiber_dia
            self.wind_count = temp_wind_count
            # TODO add wind b/f to len
        except (ValueError, IndexError, AttributeError, serial.SerialException):
            self.logging.info('Bad ESP data read.')
            pass
        try:
                self.ser2.write('MS\r\n'.encode())
                reading = float(self.ser2.readline().decode('ASCII').split(sep=',')[2])
                if reading < 0.0:
                    self.fiber_dia = 0.0
                else:
                    self.fiber_dia = reading
        except (serial.SerialException, ValueError, IndexError, AttributeError):
            self.logging.info('Bad RS-232 data read.')
            pass
        try:
            self.ser.reset_input_buffer()
            self.ser2.reset_input_buffer()
        except(serial.SerialException, AttributeError):
            pass
        if self.fiber_dia > 0.0 and self.spool_speed > 0.0:
            self.fiber_len += (self.feed_speed * 2.848 * (time.time() - self.update_last_time)) / self.fiber_dia**2
        self.sys_power = (self.htr_current + self.spool_current + self.step_current) * .012
        self.sys_energy += self.sys_power * (time.time() - self.update_last_time) / 3600.0 
        self.roll_times[self.roll_index] = time.time()
        if self.spool_speed > 0.0:
            self.fib_dias[self.roll_index] = self.fiber_dia
            self.fiber_ave_dia = np.mean(self.fib_dias[self.roll_times > (self.roll_times[self.roll_index] - self.rolling_time)])
            self.fiber_std_dia = np.std(self.fib_dias[self.roll_times > (self.roll_times[self.roll_index] - self.rolling_time)])
        else:
            self.fib_dias[self.roll_index] = 0.0
            self.fiber_ave_dia = 0.0
            self.fiber_std_dia = 0.0
        self.roll_index += 1
        if self.roll_index >= self.roll_times.size:
            self.roll_index = 0
        # update calculated outputs
        if self.tempPID.is_running:
            if time.time() > (self.htrPID_last_time + self.htrPIDint):
                self.htr_set_pwr = self.tempPID.calc_output(self.htrP, self.htrI, self.htrD, 
                                                self.htr_set_temp,self.htr_temp)
                self.sendHtr()
                self.htrPID_last_time = time.time()
        if self.spoolPID.is_running:
            if time.time() > (self.spoolPID_last_time + self.spoolPIDint):
                if self.spool_set_speed > 0.0:
                    self.spool_set_pwr = self.spoolPID.calc_output(self.spoolP, self.spoolI, self.spoolD, 
                                                    self.spool_set_speed,self.spool_speed)
                    self.spool_dir = True
                    self.sendSpool()
                self.spoolPID_last_time = time.time()
        #self.time5 = time.time() - self.time1
        self.feed_speed = self._feed_set_speed
            
        # messages to ESP
        if self.is_msg_stop:
            try:
                self.ser.write(self.msg_stop)
            except serial.SerialException:
                self.logging.info('Error sending STOP to FrED.')
            self.tempPID.is_running = False
            self.spoolPID.is_running = False
            self.feed_speed = 0.0
            self.is_msg_stop = False
        else: # send list of update messages
            msgs_out = []
            if self.is_msg_htr:
                msgs_out.append('H{0:.4f}\r\n'.format(self._htr_set_pwr))
                self.is_msg_htr = False
            if self.is_msg_feed:
                if self.feed_dir:
                    msgs_out.append(self.msg_feed_dir_F)
                else:
                    msgs_out.append(self.msg_feed_dir_R)
                msgs_out.append('F{0:.4f}\r\n'.format(self._feed_set_freq))
                self.is_msg_feed = False
            if self.is_msg_spool:
                if self.spool_dir:
                    msgs_out.append(self.msg_spool_dir_F)
                else:
                    msgs_out.append(self.msg_spool_dir_R)
                msgs_out.append('P{0:.3f}\r\n'.format(self._spool_set_pwr))
                self.is_msg_spool = False
            if self.is_msg_wind:
                if self.wind_dir:
                    msgs_out.append(self.msg_wind_dir_R)
                else:
                    msgs_out.append(self.msg_wind_dir_L)
                msgs_out.append('W{0:.3f}\r\n'.format(self.wind_set_freq))
                self.is_msg_wind = False
            if self.is_msg_init:
                msgs_out.append(self.msg_init)
                self.is_msg_init = False
            msg = ''.join(msgs_out).encode()
            try:
                self.ser.write(msg)
            except (serial.SerialException, AttributeError):
                self.logging.info('Error sending updates to FrED.')
         
        self.update_last_time = time.time()
        self.time6 = time.time() - self.time1

class pid1():

    def __init__(self):
        threading.Thread.__init__(self)
        self.is_running = False
        self.time_last = None
        self.current_val_last = None
        self.po = 0.0
        self.io = 0.0
        self.do = 0.0
        self.iomin = -1.0
        self.iomax = 1.0
        self.out_last = 0.0
        self.out_max_ch = 1.0

    def calc_output(self, kp, ki, kd, target_val, current_val):
        time_current = time.time()
        dt = time_current - self.time_last
        if dt < .001:
            return 0.0
        err = target_val - current_val
        self.po = kp * err
        #if current_val >= target_val:
        #    self.io = 0.0
        #else:
        self.io += ki * err * dt
        self.io = self.io if self.io <= self.iomax else self.iomax
        self.io = self.io if self.io >= self.iomin else self.iomin
        self.do = -kd * (current_val - self.current_val_last) / dt
        self.current_val_last = current_val
        self.time_last = time_current
        out = self.po + self.io + self.do
        out = out if out <= 1.0 else 1.0
        out = out if out >= 0.0 else 0.0
        if abs(out - self.out_last) > self.out_max_ch:
            if out < self.out_last:
                out = self.out_last - self.out_max_ch
            else:
                out = self.out_last + self.out_max_ch
        self.out_last = out
        return out

if __name__ == "__main__":
    # for testing
    logging.basicConfig(level=logging.DEBUG)
    proc = ManualDAQ()
    proc.start()
    time.sleep(10)
    proc.is_running = False
    proc.join()
    