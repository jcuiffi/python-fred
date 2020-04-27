"""
Classes that represent a digital twin of the MIT FrED process. The ProcessTwin 
base class can be used as a parent class for each process model. Override 
"model()" to implement model. BasicStateTwin is an analytical model for fiber
diameter. RegressionStateTwin contains regression models based on historic data
for fiber diameter and power consumption. RegressionDynamicTwin captures various
time-based process dynamics through regression and model fitting.

Started 2/18/20
Author - J. Cuiffi, Penn State University
"""

import datetime
import logging
import math
import threading
import time

class ProcessTwin(threading.Thread):
    """
    Thread class that defines a runnable FrED process digital twin. Override
    "model()" to implement custom model.
 
    Attributes
    ----------
        - Constants
        FIL_FEED_R (float): Radius (mm) of the input filament.
        NOZZLE_R (float): Radius (mm) of the extrusion nozzle.
        STEP_FEED_PITCH_D (float): Gear pitch (mm) of the feed stepper.
        SPOOL_D (float): Starting diameter (mm) of the winding spool.
        SPOOL_W (float): Width (mm) of the winding spool.
        STEP_FEED_PITCH_D (float): feed gear pitch diameter (mm)
        WIND_UM_P (float): wind back/forth travel (microns per pulse)    
        - "Actuator" settings
        feed_freq (float): Feed stepper drive frequency setting, 0.0-100.0 (Hz).
        htr_pwr (float): Heater power setting, 0.0-1.0 (0-100%).
        spool_pwr (float): Spool motor drive setting, 0.0-1.0 (0-100%).
        wind_dir (int): Winf back/forth dirction (1=R, 0=L)
        - "Sensor" readings
        fiber_dia (float): Fiber diameter, 0.0-nozzle diameter (mm).
        fiber_dia_std (float): Fiber diamter standard deviation (mm)
        feed_speed (float): Feed stepper speed, 0.0-.0031 (RPS). 
                            Sets feed_freq if set.
        htr_current (float): Heater current (mA)
        htr_temp (float): Heater temperature, 20.0-120.0 (C).
        spool_current (float): Spool motor current (mA)
        spool_speed (float): Winding spool speed, 0.0-1.5 (RPS).
        step_current (float): Stepper and 12V electronics current (mA)
        sys_power (float)(read only): System power (W).
        wind_count (int): Nubmer of windings on spool
        - Accumulated values
        sys_energy (float)(read only): Cumulative simulation energy use (Wh).
        fiber_len (float)(read only): Cumulative fiber length on spool (mm).
        fiber_ave_dia (float): Rolling average fiber diamter (mm)
        fiber_ave_dia_std (flaot): Rolling average fiber standard deviation (mm)
        - Model parameters
        is_Running (bool): Stay in main running loop. Set to False to stop run.
        interval (float)(default=.01): Interval between simulation calculation
                                       updates (sec).
        debug_log_interval (float)(default=1.0): Interval between debug logs 
                                                 (sec). 
        
    Methods
    -------
        debug_log_data (): Logs data to debug. Can be overridden.
        model (): Override this method to calculate updated model values.
        run (): Thread override to run the process. DO NOT call directly.
                Use ProcessTwin.start()
    """

    def __init__(self):
        threading.Thread.__init__(self)
        self.logging = logging.getLogger(__name__)
        self.lock = threading.Lock()

        # FrED parameters
        self.FIL_FEED_R = 3.5               # feed stock diameter mm
        self.NOZZLE_R = 1.5                 # extrusion nozzle radius mm
        self.SPOOL_D = 20.0                 # spool starting diameter mm
        self.SPOOL_W = 40.0                 # spool width mm
        self.STEP_FEED_PITCH_D = 18.5       # feed gear pitch diameter mm
        self.WIND_UM_P = 2.5                # wind travel microns per pulse    
        # "actuator" settings
        self._feed_freq = 0.0               # steps/s
        self._htr_pwr = 0.0                 # 0.0-1.0 (0.0-100.0%)
        self._spool_pwr = 0.0               # 0.0-1.0 (0.0-100.0%)
        self._wind_dir = 0                  # wind direction 1=Right
        # "sensor" readings
        self._fiber_dia = 0.0               # mm
        self._fiber_dia_std = 0.0           # mm
        self._feed_speed = 0.0              # RPS
        self._htr_current = 0.0             # mA
        self._htr_temp = 20.0               # C
        self._spool_current = 0.0           # mA
        self._spool_speed = 0.0             # RPS
        self._step_current = 0.0            # mA
        self._sys_power = 0.0               # W
        self._wind_count = 1                # number of filament windings on spool
        # accumulated values
        self._fiber_len = 0.0               # mm
        self._fiber_ave_dia = 0.0           # rolling average diameter mm
        self._fiber_ave_dia_std = 0.0       # rolling std dev (mm)
        self._sys_energy = 0.0              # Wh
        # model parameters
        self.is_running = False             # bool
        self.interval = .1                  # sec
        self.cur_time = None                # sec UNIX time
        self.prev_time = None               # sec UNIX time
        self.debug_log_interval = 1.0       # sec UNIX time
        self.debug_log_prev_time = None     # sec UNIX time

    @property
    def feed_freq(self):
        return self._feed_freq

    @feed_freq.setter
    def feed_freq(self, value):
        if (value < 0.0):
            self._feed_freq = 0.0
            self.logging.info('Feed frequency must be > 0.0')
        elif (value > 100.0):
            self._feed_freq = 100.0
            self.logging.info('Feed frequency must be < 100.0')
        else:
            self._feed_freq = value

    @property
    def htr_pwr(self):
        return self._htr_pwr
    
    @htr_pwr.setter
    def htr_pwr(self, value):
        if (value < 0.0):
            self._htr_pwr = 0.0
            self.logging.info('Heater power must be > 0.0')
        elif (value > 1.0):
            self._htr_pwr = 1.0
            self.logging.info('Heater power must be < 1.0')
        else:
            self._htr_pwr = value

    @property
    def spool_pwr(self):
        return self._spool_pwr
    
    @spool_pwr.setter
    def spool_pwr(self, value):
        if (value < 0.0):
            self._spool_pwr = 0.0
            self.logging.info('Spool power must be > 0.0')
        elif (value > 1.0):
            self._spool_pwr = 1.0
            self.logging.info('Spool power must be < 1.0')
        else:
            self._spool_pwr = value

    @property
    def wind_dir(self):
        return self._wind_dir

    @wind_dir.setter
    def wind_dir(self, value):
        if value < 0:
            self._wind_dir = 0
        elif value > 1:
            self._wind_dir = 1
        else:
            self._wind_dir = value

    @property
    def fiber_dia(self):
        return self._fiber_dia
    
    @fiber_dia.setter
    def fiber_dia(self, value):
        if (value < 0.0):
            self._fiber_dia = 0.0
            self.logging.info('Fiber diameter must be > 0.0')
        elif (value > (self.FIL_FEED_R*2.0)):
            self._fiber_dia = (self.FIL_FEED_R * 2.0)
            self.logging.info('Fiber diamter must be < {0:.3f}'.format(
                                self.FIL_FEED_R * 2.0))
        else:
            self._fiber_dia = value

    @property
    def fiber_dia_std(self):
        return self._fiber_dia_std

    @property
    def feed_speed(self):
        return self._feed_speed

    @feed_speed.setter
    def feed_speed(self, value):
        if (value < 0.0):
            self._feed_speed = 0.0
            self.logging.info('Feed speed must be > 0.0')
        elif (value > .031):
            self._feed_speed = .031
            self.logging.info('Feed speed must be < 0.031')
        else:
            self._feed_speed = value
        self._feed_freq = self._feed_speed * 3200.0

    @property
    def htr_current(self):
        return self._htr_current
    
    @property
    def htr_temp(self):
        return self._htr_temp

    @htr_temp.setter
    def htr_temp(self, value):
        if (value < 20.0):
            self._htr_temp = 20.0
            self.logging.info('Heater temperature must be > 20.0')
        elif (value > 120.0):
            self._htr_temp = 120.0
            self.logging.info('Heater temperature must be < 120.0')
        else:
            self._htr_temp = value

    @property
    def spool_current(self):
        return self._spool_current

    @property
    def spool_speed(self):
        return self._spool_speed
    
    @spool_speed.setter
    def spool_speed(self, value):
        if (value < 0.0):
            self._spool_speed = 0.0
            self.logging.info('Spool speed must be > 0.0')
        elif (value > 1.5):
            self._spool_speed = 1.5
            self.logging.info('Spool speed must be < 1.5')
        else:
            self._spool_speed = value

    @property
    def step_current(self):
        return self._step_current

    @property
    def sys_power(self):
        return self._sys_power

    @property
    def wind_count(self):
        return self._wind_count

    @property
    def fiber_len(self):
        return self._fiber_len

    @property
    def fiber_ave_dia(self):
        return self._fiber_ave_dia

    @property
    def fiber_ave_dia_std(self):
        return self._fiber_ave_dia_std
        
    @property
    def sys_energy(self):
        return self._sys_energy

    def debug_log_data(self):
        """
        Logs current twin data at debug level - can be overridden.
        Args: None
        Returns: None
        """
        self.logging.debug('htr_temp(C):{0:.1f}, '.format(self._htr_temp) +
                        'feed_speed(RPS):{0:.4f}, '.format(self._feed_speed) +
                        'spool_speed(RPS):{0:.3f}, '.format(self._spool_speed) +
                        'fiber_dia(mm):{0:.3f}, '.format(self._fiber_dia) +
                        'sys_power(W):{0:.2f}'.format(self._sys_power))
        
    def model(self):
        """
        Override this method to calculate updated model values.
        Args: None
        Returns: None
        """
        pass

    def run(self):
        """
        Thread override to run the process. DO NOT call directly.
        Use ProcessTwin.start()
        Stop by setting is_Running to False.
        Args: None
        Returns: None
        """
        # Thread override to start process
        self.logging.info('Starting Process Model')
        self.is_running = True
        self.prev_time = self.debug_log_prev_time = time.time()
        self.logging.info('Modeling Start Time: ' + 
            datetime.datetime.fromtimestamp(self.prev_time).isoformat())
        while(self.is_running):
            self.cur_time = time.time()
            if (self.cur_time >= (self.prev_time + self.interval)):
                with self.lock:
                    self.model()
                    self._sys_energy += (self._sys_power * 
                        (self.cur_time - self.prev_time) / 3600.0)    
                self.prev_time = self.cur_time
            if (self.cur_time >= (self.debug_log_prev_time + 
                                  self.debug_log_interval)):
                self.debug_log_data()
                self.debug_log_prev_time = self.cur_time
        self.logging.info('Modeling Stop Time:' + 
            datetime.datetime.fromtimestamp(time.time()).isoformat())

class BasicStateTwin(ProcessTwin):
    """
    Thread class that defines a runnable FrED process digital twin. 
    Basic time-independent analytical state based model using mass conservation
    From MIT - DSCC 2017, D. Kim, B. Anthony

    Note: Set htr_temp, feed_freq or feed_speed, and spool_speed directly.
          Can use calc_spool_speed to return a spool speed bases on desired dia.
 
    Methods
    -------
        calc_spool_speed(feed,dia): calulates a spool speed based on feed speed
                                    and desired diameter
        model(): Updates model values.
    """

    def __init__(self):
        ProcessTwin.__init__(self)
        self.interval = .05                  # sec

    # calculates a spool speed based on a desired fiber diameter
    def calc_spool_speed(self, feed = 0.0, fdia = 0.0):
        if feed > 0.0 and fdia > 0.0:
            return ((feed * 6.73**2) / fdia**2)
        else:
            return 0.0

    def model(self):
        # check for proper run conditions        
        if (self._htr_temp >= 75.0):
            self._feed_speed = self._feed_freq / 3200.0
            if (self._feed_freq > 0.0):
                if (self._spool_speed > 0.0):
                    self._fiber_dia = 6.73 * math.sqrt(self._feed_speed /
                                                        self._spool_speed)
                    vspool = self._spool_speed * self.SPOOL_D * math.pi / 1000.0
                    self._fiber_len += vspool * (self.cur_time - self.prev_time)
                else:
                    self._fiber_dia = self.NOZZLE_R * 2.0
            else:
                self._fiber_dia = 0.0
        else:
            self._feed_freq = 0.0
            self._feed_speed = 0.0
            self._fiber_dia = 0.0

class RegressionDynamicTwin(ProcessTwin):
    """
    Thread class that defines a runnable FrED process digital twin. 
    Empirical physical based model based on historical run data and regression 
    models. Models heater, spool motor, fiber diameter (incuding wind count 
    effect), fiber standard deviation, system power. No delay in fiber diameter 
    changes - TODO.

    Note: Set htr_pwr, feed_freq, and spool_pwr or PID for any. 
 
    Methods
    -------
        calc_spool_speed(feed,dia): calulates a spool speed based on feed speed
                                    and desired diameter
        model (): Updates model values.
    """

    def __init__(self):
        ProcessTwin.__init__(self)
        # parameters for tracking spool diameter changes
        self.mc = .68                       # heater model constant
        self.ha = .0026                     # heater model constant
        self.htr_pwr_delay = 26.0               # sec
        self.wind_factor = 1.0              # diameter % based on wind count
        self.spool_cur_dia = self.SPOOL_D   # mm
        self.wind_prev_len = 0.0            # mm
        self.wind_dist = math.pi * self.spool_cur_dia * 50.0   # mm
        self.htr_temp_last = self._htr_temp
        self.wind_freq = 0.0
        self._wind_count = 1
        self.interval = .1
        self.htr_pwr_o = 0.0
        self.htr_pwr_target = 0.0
        self.htr_pwr_delta = 0.0
        self.htr_pwr_cur = 0.0
        self.htr_pwr_ch_time = 0.0
        self.spool_speed_target = 0.0
        self.spool_tau_acc = .04            # sec
        self.spool_tau_dec = .8653          # sec
        self.spool_kp = 1.5                 # RPS

    # calculates a spool speed based on a desired fiber diameter
    def calc_spool_speed(self, feed = 0.0, fdia = 0.0):
        if feed > 0.0 and fdia > 0.0:
            return ((feed * 6.38896**2) / (fdia - .011145)**2)
        else:
            return 0.0

    def model(self):
        # heater model
        # delay
        if self._htr_pwr != self.htr_pwr_target:
            self.htr_pwr_o = self.htr_pwr_cur
            self.htr_pwr_target = self._htr_pwr
            self.htr_pwr_delta = self.htr_pwr_target - self.htr_pwr_o
            self.htr_pwr_ch_time = self.cur_time
        if self.htr_pwr_cur != self.htr_pwr_target:
            if self.cur_time >= (self.htr_pwr_delay + self.htr_pwr_ch_time):
                self.htr_pwr_cur = self.htr_pwr_target
            else:
                self.htr_pwr_cur = ((self.cur_time - self.htr_pwr_ch_time) / self.htr_pwr_delay) * self.htr_pwr_delta + self.htr_pwr_o
                if self.htr_pwr_delta > 0:
                    if self.htr_pwr_cur > self.htr_pwr_target:
                        self.htr_pwr_cur = self.htr_pwr_target
                if self.htr_pwr_delta < 0:
                    if self.htr_pwr_cur < self.htr_pwr_target:
                        self.htr_pwr_cur = self.htr_pwr_target 
        # heat eq
        self._htr_temp = self.htr_temp_last + ((self.cur_time - self.prev_time) * 
                            ((self.htr_pwr_cur * self.mc) - 
                            (self.ha * (self.htr_temp_last - 20.0))))
        if self._htr_temp < 20.0:
            self._htr_temp = 20.0
        self.htr_temp_last = self._htr_temp
        # motor model
        self.spool_speed_target = self.spool_kp * self._spool_pwr
        if self.spool_speed_target >= self._spool_speed:
            # accelerating
            tau = self.spool_tau_acc
        else:
            # decelerating
            tau = self.spool_tau_dec
        self._spool_speed = math.exp(-(self.cur_time - self.prev_time) / tau) * (self._spool_speed - self.spool_speed_target) + self.spool_speed_target
        # check for proper run conditions
        if (self._htr_temp >= 75.0):
            self._feed_speed = self._feed_freq / 3200.0
            if (self._feed_freq > 0.0):
                if (self._spool_speed > 0.0):
                    # TODO fiber dynamic model for delay in diamater changes
                    self._fiber_dia = (((6.38896 * math.sqrt(self._feed_speed /
                                        self._spool_speed)) + .011145) * self.wind_factor)
                    # set a b/f winding speed - TODO use set spool speed
                    self.wind_freq = 600.0 * self._spool_speed * 6.732 * math.sqrt(self._feed_speed / self._spool_speed)
                    self.wind_prev_len += self.wind_freq * .0025 * (self.cur_time - self.prev_time)
                    # using regression 
                    if self.wind_prev_len >= self.SPOOL_W:
                        self.wind_prev_len = 0.0
                        self._wind_count += 1
                        #self.spool_cur_dia += self._fiber_dia * 2.0 * self.wind_factor
                        self.wind_factor = 1.0 - (0.0054695 * (self.wind_count - 1)) 
                    # total fiber length
                    self._fiber_len += (self._feed_speed * 2.848 * (self.cur_time - self.prev_time)) / self._fiber_dia**2
                else:
                    self._fiber_dia = self.NOZZLE_R * 2.0
            else:
                self._fiber_dia = 0.0
        else:
            self._feed_freq = 0.0
            self._feed_speed = 0.0
            self._fiber_dia = 0.0
        # using regression for standard deviation
        self._fiber_dia_std = .11 * self._fiber_dia - .007
        if self._fiber_dia_std < 0.0:
            self._fiber_dia_std = 0.0
        # power consumption
        self._htr_current = self._htr_pwr * 6400.0
        self._spool_current = (self._spool_speed / 1.5) * 182.8
        self._step_current = 509.0
        self._sys_power = (self._htr_current + self._spool_current + self._step_current) * .012
        self._sys_energy += self._sys_power * (self.cur_time - self.prev_time) / 3600.0

class RegressionStateTwin(ProcessTwin):
    """
    Thread class that defines a runnable FrED process digital twin. 
    Time-independent empirical state based model based on historical run
    data and regression models. Models: fiber diameter, fiber standard 
    deviation, power. Spool diameter does not change.

    Note: Set htr_temp, feed_freq or feed_speed, and spool_speed directly.
          Can use calc_spool_speed to return a spool speed bases on desired dia.
 
    Methods
    -------
        calc_spool_speed(feed,dia): calulates a spool speed based on feed speed
                                    and desired diameter
        model (): Updates model values.
    """

    def __init__(self):
        ProcessTwin.__init__(self)

    # calculates a spool speed based on a desired fiber diameter
    def calc_spool_speed(self, feed = 0.0, fdia = 0.0):
        if feed > 0.0 and fdia > 0.0:
            return ((feed * 6.38896**2) / (fdia - .011145)**2)
        else:
            return 0.0

    def model(self):
        # check for proper run conditions        
        if (self._htr_temp >= 75.0):
            self._feed_speed = self._feed_freq / 3200.0
            if (self._feed_freq > 0.0):
                if (self._spool_speed > 0.0):
                    self._fiber_dia = ((6.38896 * math.sqrt(self._feed_speed /
                                        self._spool_speed)) + .011145)
                    vspool = self._spool_speed * self.SPOOL_D * math.pi / 1000.0
                    self._fiber_len += vspool * (self.cur_time - self.prev_time)
                else:
                    self._fiber_dia = self.NOZZLE_R * 2.0
            else:
                self._fiber_dia = 0.0
        else:
            self._feed_freq = 0.0
            self._feed_speed = 0.0
            self._fiber_dia = 0.0
        self.fiber_std_dia = .11 * self.fiber_dia - .007
        if self.fiber_std_dia < 0.0:
            self.fiber_std_dia = 0.0
        # power consumption
        self._htr_current = ((34.1 * self._htr_temp) - 1188.0 + 
                                ((self._feed_speed / .005) * 130.0))
        self._spool_current = (self._spool_speed / 1.5) * 182.8
        self._step_current = 509.0
        self._sys_power = (self._htr_current + self._spool_current + self._step_current) * .012
        self._sys_energy += self._sys_power * (self.cur_time - self.prev_time) / 3600.0

if __name__ == "__main__":
    # for testing
    logging.basicConfig(level=logging.DEBUG)
    twin = RegressionDynamicTwin()
    twin.start()
    twin.htr_pwr = 1.0
    time.sleep(20)
    twin.is_running = False
    twin.join()



