"""
Classes for control of the MIT FrED process. The Control base class can be used
as a parent class for each control algoritm. Override "update()" to implement
algorithm.

Started 2/23/20
Author - J. Cuiffi, Penn State University
"""

import datetime
import logging
import process_models
import threading
import simple_pid
import time

class Control(threading.Thread):
    """
    Thread class that defines a runnable FrED control algorithm. Override
    "update()" to implement custom control algorithm.
 
    Attributes
    ----------
        twin (process_models.ProcessTwin): Digital twin model, if needed.
        - Conrol target settings
        htr_set_temp (float): Heater set temperature, 20.0-120.0 (C).
        fiber_set_dia (float): Fiber set diameter, 0.0-nozzle diameter (mm).
        feed_set_speed (float): Feed set stepper speed, 0.0-.0031 (RPS). 
        spool_set_speed (float): Winding spool set speed, 0.0-1.5 (RPS).
        htr_set_pwr (float): Heater set power setting, 0.0-1.0 (0-100%).
        feed_set_freq (float): Feed stepper drive frequency setting, 
                               0.0-100.0 (Hz).
        spool_set_pwr (float): Spool motor drive setting, 0.0-1.0 (0-100%).
        - Control algorithm settings
        is_Running (bool): Stay in main running loop. Set to False to stop run.
        interval (float)(default=.1): Interval between process calculation
                                       updates (sec).
        debug_log_interval (float)(default=1.0): Interval between debug logs 
                                                 (sec). 

    Methods
    -------
        debug_log_data (): Logs data to debug. Can be overridden.
        update (): Override this method to calculate updated control values.
        run (): Thread override to run the process. DO NOT call directly.
                Use ProcessTwin.start()
    """
    
    def __init__(self):
        threading.Thread.__init__(self)
        self.logging = logging.getLogger(__name__)
        self.lock = threading.Lock()

        # twin model
        self.twin = process_models.BasicStateTwin()
        # target settings
        self._htr_set_temp = 20.0           # C
        self._fiber_set_dia = 0.0           # mm
        self._feed_set_speed = 0.0          # RPS
        self._spool_set_speed = 0.0         # RPS
        self._htr_set_pwr = 0.0             # 0.0-1.0 (0.0-100.0%)
        self._feed_set_freq = 0.0           # steps/s
        self._spool_set_pwr = 0.0           # 0.0-1.0 (0.0-100.0%)
        # process parameters
        self.is_running = False             # bool
        self.interval = .1                  # sec
        self.cur_time = None                # sec UNIX time
        self.prev_time = None               # sec UNIX time
        self.debug_log_interval = 1.0       # sec
        self.debug_log_prev_time = None     # sec UNIX time
    
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
    def feed_set_speed(self):
        return self._feed_set_speed

    @feed_set_speed.setter
    def feed_set_speed(self, value):
        if (value < 0.0):
            self._feed_set_speed = 0.0
            self.logging.info('Feed set speed must be > 0.0')
        elif (value > .031):
            self._feed_set_speed = .031
            self.logging.info('Feed set speed must be < 0.031')
        else:
            self._feed_set_speed = value

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
            self.logging.info('Spool set speed must be < 1.0')
        else:
            self._spool_set_speed = value

    @property
    def htr_set_pwr(self):
        return self._htr_set_pwr
    
    @htr_set_pwr.setter
    def htr_pwr(self, value):
        if (value < 0.0):
            self._htr_set_pwr = 0.0
            self.logging.info('Heater set power must be > 0.0')
        elif (value > 1.0):
            self._htr_set_pwr = 1.0
            self.logging.info('Heater set power must be < 1.0')
        else:
            self._htr_set_pwr = value

    @property
    def feed_set_freq(self):
        return self._feed_set_freq

    @feed_set_freq.setter
    def feed_set_freq(self, value):
        if (value < 0.0):
            self._feed_set_freq = 0.0
            self.logging.info('Feed set frequency must be > 0.0')
        elif (value > 100.0):
            self._feed_set_freq = 100.0
            self.logging.info('Feed set frequency must be < 100.0')
        else:
            self._feed_set_freq = value

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

class BasicPIDDynamicTwin(Control):
    """
    Runnable FrED control algorithm that uses PID for heater temperature and
    fiber diameter, controlling spool rate. 

    Note: Set htr_set_temp, feed_set_speed, and fiber_set_dia
 
    Attributes
    ----------
        twin (BasicDynamicTwin): Simulation model.
        tempPID (simple_pid.PID): PID controller for temperature.
        diaPID (simple_pid.PID): PID controller for fiber diameter.

    Methods
    -------
        update (): Updates control values.
    """

    def __init__(self, twin=process_models.BasicDynamicTwin()):
        Control.__init__(self)
        
        self.twin = twin
        self.tempPID = simple_pid.PID(0.8,0.4,0.1,
                        sample_time=None,output_limits=(0.0,1.0))
        self.diaPID = simple_pid.PID(1.0,1.0,0.0,
                        sample_time=None,output_limits=(0.0,.99))

    def update(self):
        self.tempPID.setpoint = self._htr_set_temp
        self.twin.htr_pwr = self._htr_set_pwr = self.tempPID(self.twin.htr_temp)
        if (self.twin.htr_temp >= 80.0):
            self.twin.feed_freq = self._feed_set_freq = (
                                        self._feed_set_speed * 3200.0) 
            self.diaPID.setpoint = self._fiber_set_dia
            self.twin.spool_pwr = self._spool_set_pwr = (1.0 - 
                                  (self.diaPID(self.twin.fiber_dia)))
        else:
            self.twin.feed_freq = 0.0
            self.twin.spool_pwr = 0.0

class ManualPIDDynamicTwin(Control):
    """
    Runnable FrED control algorithm that uses PID for heater temperature, and
    manual control of feed speed and spool speed. 

    Note: Set htr_set_temp, feed_set_speed, and spool_set_speed
 
    Attributes
    ----------
        twin (BasicDynamicTwin): Simulation model.
        tempPID (simple_pid.PID): PID controller for temperature.
        
    Methods
    -------
        update (): Updates control values.
    """

    def __init__(self, twin=process_models.BasicDynamicTwin()):
        Control.__init__(self)
        
        self.twin = twin
        self.tempPID = simple_pid.PID(0.8,0.4,0.1,
                        sample_time=None,output_limits=(0.0,1.0))
        
    def update(self):
        self.tempPID.setpoint = self._htr_set_temp
        self.twin.htr_pwr = self._htr_set_pwr = self.tempPID(self.twin.htr_temp)
        if (self.twin.htr_temp >= 80.0):
            self.twin.feed_freq = self._feed_set_freq = (
                                        self._feed_set_speed * 3200.0) 
            self.twin.spool_pwr = self._spool_set_pwr = (self._spool_set_speed /
                                                         1.5)
        else:
            self.twin.feed_freq = 0.0
            self.twin.spool_pwr = 0.0

class ManualStateTwin(Control):
    """
    Runnable FrED control algorithm that simply passes along set values for
    manual control of the Basic State Model.

    Note: Set htr_set_temp, feed_set_speed, and spool_set_speed
 
    Attributes
    ----------
        twin (BasicStateTwin): Simulation model.
        
    Methods
    -------
        update (): Updates control values.
    """

    def __init__(self, twin=process_models.BasicStateTwin()):
        Control.__init__(self)
        
        self.twin = twin

    def update(self):
        self.twin.htr_temp = self._htr_set_temp
        self.twin.feed_freq = self._feed_set_freq = (
                                        self._feed_set_speed * 3200.0) 
        self.twin.spool_speed = self._spool_set_speed

class CalcDiaStateTwin(Control):
    """
    Runnable FrED control algorithm that calculates spool speed for a set fiber 
    diamter, and passes along heater and feed set values.

    Note: Set htr_set_temp, feed_set_speed, and fiber_set_dia
 
    Attributes
    ----------
        twin (BasicDynamicTwin): Simulation model.
        
    Methods
    -------
        update (): Updates control values.
    """

    def __init__(self, twin=process_models.BasicStateTwin()):
        Control.__init__(self)
        
        self.twin = twin

    def update(self):
        self.twin.htr_temp = self._htr_set_temp
        self.twin.feed_freq = self._feed_set_freq = (
                                        self._feed_set_speed * 3200.0) 
        if (self._fiber_set_dia > 0.0) :
            self.twin.spool_speed = self._spool_set_speed = (
                (self._feed_set_speed * self.twin.STEP_FEED_PITCH_D * 4 *
                self.twin.FIL_FEED_R**4) / (self.twin.SPOOL_D * 
                self._fiber_set_dia**2 * self.twin.NOZZLE_R**2))
        else:
            self.twin.spool_speed = self._spool_set_speed = 0.0

if __name__ == "__main__":
    # for testing
    logging.basicConfig(level=logging.DEBUG)
    twin = process_models.BasicDynamicTwin()
    proc = BasicPIDDynamicTwin(twin)
    twin.start()
    proc.htr_set_temp = 100.0
    proc.feed_set_speed = .0031
    proc.fiber_set_dia = .3
    proc.start()
    time.sleep(30)
    twin.is_running = False
    twin.join()
    proc.is_running = False
    proc.join()