"""
Classes that represent a digital twin of the MIT FrED process. The Control base
class can be used as a parent class for each process model. Override 
"model()" to implement model.

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
        STEP_FEED_PITCH_D (float): Gear pitch (mm) of the feed stepper.
        FIL_FEED_R (float): Radius (mm) of the input filament.
        NOZZLE_R (float): Radius (mm) of the extrusion nozzle.
        SPOOL_D (flaot): Starting diameter (mm) of the winding spool.
        SPOOL_W (float): Width (mm) of the winding spool.
        - Model settings and readings
        htr_pwr (float): Heater power setting, 0.0-1.0 (0-100%).
        feed_freq (float): Feed stepper drive frequency setting, 0.0-100.0 (Hz).
        spool_pwr (float): Spool motor drive setting, 0.0-1.0 (0-100%).
        htr_temp (float): Heater temperature, 20.0-120.0 (C).
        feed_speed (float): Feed stepper speed, 0.0-.0031 (RPS). 
                            Sets feed_freq if set.
        spool_speed (float): Winding spool speed, 0.0-1.5 (RPS).
        fiber_dia (float): Fiber diameter, 0.0-nozzle diameter (mm).
        sys_power (float)(read only): System power (W).
        sys_energy (float)(read only): Cumulative simulation energy use (Wh).
        fiber_len (float)(read only): Cumulative fiber length on spool (mm).
        - Simulation settings
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
        self.STEP_FEED_PITCH_D = 8.98       # mm
        self.FIL_FEED_R = 3.175             # mm
        self.NOZZLE_R = 2.54                # mm
        self.SPOOL_D = 25.4                 # mm
        self.SPOOL_W = 76.2                 # mm    
        # "actuator" settings
        self._htr_pwr = 0.0                  # 0.0-1.0 (0.0-100.0%)
        self._feed_freq = 0.0                # steps/s
        self._spool_pwr = 0.0                # 0.0-1.0 (0.0-100.0%)
        # "sensor" readings
        self._htr_temp = 20.0                # C
        self._feed_speed = 0.0               # RPS
        self._spool_speed = 0.0              # RPS
        self._fiber_dia = 0.0                # mm
        self._sys_power = 0.0                # W
        # accumulated values
        self._sys_energy = 0.0               # Wh
        self._fiber_len = 0.0                # mm
        # model parameters
        self.is_running = False             # bool
        self.interval = .01                 # sec
        self.cur_time = None                # sec UNIX time
        self.prev_time = None               # sec UNIX time
        self.debug_log_interval = 1.0       # sec UNIX time
        self.debug_log_prev_time = None     # sec UNIX time

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
    def spool_speed(self):
        return self._spool_speed
    
    @spool_speed.setter
    def spool_speed(self, value):
        if (value < 0.0):
            self._spool_speed = 0.0
            self.logging.info('Spool speed must be > 0.0')
        elif (value > 1.5):
            self._spool_speed = 1.5
            self.logging.info('Spool speed must be < 1.0')
        else:
            self._spool_speed = value

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
    def sys_power(self):
        return self._sys_power
    
    @property
    def sys_energy(self):
        return self._sys_energy

    @property
    def fiber_len(self):
        return self._fiber_len
    
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
    Basic time-independent state based model using mass conservation
    From MIT - DSCC 2017, D. Kim, B. Anthony

    Note: Set htr_temp, feed_freq or feed_speed, and spool_speed directly.
 
    Methods
    -------
        model (): Updates model values.
    """

    def __init__(self):
        ProcessTwin.__init__(self)
        
    def model(self):
        # check for proper run conditions        
        if (self._htr_temp >= 90.0):
            if (self._feed_freq > 0.0):
                self._feed_speed = self._feed_freq / 3200.0
                # equations from article
                v1 = (self.STEP_FEED_PITCH_D * math.pi * self._feed_speed)
                v2 = v1 * (self.FIL_FEED_R**2 / self.NOZZLE_R**2)
                if (self._spool_speed > 0.0):
                    v3 = math.pi * self.SPOOL_D * self._spool_speed
                    self._fiber_dia = 2 * self.FIL_FEED_R * math.sqrt(v2 / v3)
                    if (self._fiber_dia > (self.FIL_FEED_R * 2.0)):
                        self._fiber_dia = self.FIL_FEED_R * 2.0
                    self._fiber_len += v3 * (self.cur_time - self.prev_time)
                else:
                    self._fiber_dia = self.NOZZLE_R * 2.0
            else:
                self._fiber_dia = 0.0
        else:
            self._feed_freq = 0.0
            self._feed_speed = 0.0
            self._spool_speed = 0.0
            self._fiber_dia = 0.0
        # placeholder for power consumption
        if (self._htr_temp > 20.0):
            self._sys_power = 10.0
        
class BasicDynamicTwin(ProcessTwin):
    """
    Thread class that defines a runnable FrED process digital twin. 
    Mass conservation model plus simple models for heater, spool speed, energy,
    and winding diameter changes.

    Note: Set htr_pwr, feed_freq, and spool_pwr.
 
    Attributes
    ----------
        MC (float): Heat transfer constant.
        spool_cur_dia (float): Current spool diameter with fiber coil (mm).
        wind_prev_len (float): Length of fiber at previous complete winding
                               level (mm).
        wind_dist (float): Length of fiber required to compelte next winding
                           (mm).
    Methods
    -------
        model (): Updates model values.
    """

    def __init__(self):
        ProcessTwin.__init__(self)
        # parameters for tracking spool diameter changes
        self.MC = .2                        # heat constant
        self.spool_cur_dia = self.SPOOL_D   # mm
        self.wind_prev_len = 0.0            # mm
        self.wind_dist = math.pi * self.spool_cur_dia * 50.0   # mm
        
    def model(self):
        # example for testing - TODO: clean up physics models
        # heater model
        temp_gain = (self.MC * 40.0 * self._htr_pwr * 
                     (self.cur_time - self.prev_time))
        temp_loss = ((self.cur_time - self.prev_time) *
                     ((.05 * (self._htr_temp - 20.0)) + .001 * self._feed_freq))
        self._htr_temp = self._htr_temp + temp_gain - temp_loss
        # check for proper run conditions
        if(self._htr_temp >= 90.0):
            if (self._feed_freq > 0.0):
                # feed extruder model
                self._feed_speed = self._feed_freq / 3200.0
                # equations from article
                v1 = (self.STEP_FEED_PITCH_D * math.pi * self._feed_speed)
                v2 = v1 * (self.FIL_FEED_R**2 / self.NOZZLE_R**2)
                if (self._spool_pwr > 0.0):
                    # spool model
                    self._spool_speed = 1.5 * self._spool_pwr
                    v3 = math.pi * self.spool_cur_dia * self._spool_speed
                    self._fiber_dia = 2 * self.FIL_FEED_R * math.sqrt(v2 / v3)
                    if (self._fiber_dia > (self.FIL_FEED_R * 2.0)):
                        self._fiber_dia = self.FIL_FEED_R * 2.0
                    self._fiber_len += v3 * (self.cur_time - self.prev_time)
                    # add winding diameter increase
                    if ((self._fiber_len - self.wind_prev_len) 
                        >= self.wind_dist):
                        self.wind_prev_len = self._fiber_len
                        self.spool_cur_dia += 2.0 * self._fiber_dia
                        self.wind_dist = math.pi * self.spool_cur_dia * 50.0
                else:
                    self._fiber_dia = self.NOZZLE_R * 2.0
            else:
                self._fiber_dia = 0.0
        else:
            self._feed_freq = 0.0
            self._feed_speed = 0.0
            self._spool_speed = 0.0
            self._fiber_dia = 0.0
        # power consumption
        self._sys_power = ((40.0 * self._htr_pwr) + 2.0 + 
                          (.002 * self._feed_freq) + (24.0 * self._spool_pwr))
        
if __name__ == "__main__":
    # for testing
    logging.basicConfig(level=logging.DEBUG)
    twin = BasicDynamicTwin()
    twin.start()
    twin.htr_pwr = 1.0
    time.sleep(20)
    twin.feed_freq = 10.0
    twin.spool_pwr = .31
    time.sleep(10)
    twin.is_running = False
    twin.join()



