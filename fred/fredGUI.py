"""
GUI control window for FrED process control. Imports 
'fredGUIwin.py' created with QTDesigner - 'fredGUIwin.ui'

Note: Use ">pyuic5 --from-imports fredGUIwin.ui -o fredGUIwin.py" for 
      conversion in the resources folder. Use ">pyrcc5 res_file.qrc -o 
      res_file_rc.py" to recompile the resources file.

Started 3/16/20
Author - J. Heim, J. Cuiffi, Penn State University
"""

from PyQt5 import QtWidgets, QtCore
from resources.fredGUIwin import Ui_MainWindow
import logging
import process_models
import control_models
import sys
import csv
import time
from datetime import datetime

class fredwin(QtWidgets.QMainWindow):

    def __init__(self):
        super(fredwin,self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ctrl = control_models.ManualDAQ()
        # add controls to drop down list
        self.ui.ctrlOpts.currentIndexChanged.connect(self.updateControl)
        self.ui.ctrlOpts.addItems(['Manual Control'])
        self.ui.ctrlOpts.setCurrentIndex(0)
        self.ui.controlInterval.setText('{0:.3f}'.format(self.ctrl.interval))
        self.ui.controlInterval.editingFinished.connect(self.onCtrlIntCh)
        self.ui.filamentHeatSet.editingFinished.connect(self.onHeatCh)
        self.ui.htrP.editingFinished.connect(self.onHtrPCh)
        self.ui.htrI.editingFinished.connect(self.onHtrICh)
        self.ui.htrD.editingFinished.connect(self.onHtrDCh)
        self.ui.filamentFeedSet.editingFinished.connect(self.onFeedCh)
        self.ui.spoolWindSet.editingFinished.connect(self.onSpoolCh)
        self.ui.filamentDiamSet.editingFinished.connect(self.onFibCh)
        self.ui.spoolP.editingFinished.connect(self.onSpoolPCh)
        self.ui.spoolI.editingFinished.connect(self.onSpoolICh)
        self.ui.spoolD.editingFinished.connect(self.onSpoolDCh)
        self.ui.broadcastPeriodSet.setText('{0:.3f}'.format(self.ctrl.interval))
        self.ui.broadcastPeriodSet.editingFinished.connect(self.onOutIntCh)
        self.ui.mqttTopic.setText('fred/data')
        # buttons
        self.ui.startButton.clicked.connect(self.onStart)
        self.ui.stopButton.clicked.connect(self.onStop)
        self.ui.stopButton.setEnabled(False)
        self.ui.htrSetButton.clicked.connect(self.onSetHtr)
        self.ui.htrPIDSetButton.clicked.connect(self.onSetHtrPID)
        self.ui.feedSetButton.clicked.connect(self.onSetFeed)
        self.ui.spoolSetButton.clicked.connect(self.onSetSpool)
        self.ui.filepathSet.clicked.connect(self.onFile)
        self.ui.broadcastMQTTCheck.stateChanged.connect(self.onMqttCh)
        self.ui.unwindButton.clicked.connect(self.onSpoolWind)
        self.ui.initButton.clicked.connect(self.onInit)
        # GUI Updates
        self.outInterval = float(self.ui.broadcastPeriodSet.text())
        self.filepath = ''
        self.filename = ''
        self.file = None
        self.file_writer = None
        self.update_actual_interval = 200       # msec
        self.is_updating = False
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.updateActuals)
        
        self.log_timer = QtCore.QTimer()
        self.log_timer.timeout.connect(self.logData)
        self.mqtt_timer = QtCore.QTimer()
        self.mqtt_timer.timeout.connect(self.mqttData)
        self.opc_timer = QtCore.QTimer()
        self.opc_timer.timeout.connect(self.opcData)
        
    def mqttData(self):
        # TODO broadcast mqtt data
        pass

    def opcData(self):
        # TODO broadcast OPC data
        pass

    def logData(self):
        # add dataline to CSV file
        self.file_writer.writerow([time.time(), self.ctrl.htr_set_temp, self.ctrl.feed_set_speed, 
                                self.ctrl.spool_set_speed, self.ctrl.fiber_set_dia, 
                                self.ctrl.htr_temp, self.ctrl.feed_speed, 
                                self.ctrl.spool_speed, self.ctrl.fiber_dia, 
                                self.ctrl.fiber_len, self.ctrl.sys_power, self.ctrl.sys_energy])

    def onMqttCh(self):
        if self.ui.broadcastMQTTCheck.isChecked():
            # TODO connection to broker
            self.ui.messageWindow.appendPlainText('Starting MQTT Broadcast - Topic:' +
                                                  self.ui.mqttTopic.text())
            self.mqtt_timer.start(self.outInterval)
        else:
            self.ui.messageWindow.appendPlainText('Stopping MQTT Broadcast.')
            self.mqtt_timer.stop()
            self.mqtt_timer = QtCore.QTimer()
            self.mqtt_timer.timeout.connect(self.mqttData)
    
    def onFile(self):
        self.filepath = QtWidgets.QFileDialog.getExistingDirectory(
                            self, 'Datalog Save Folder')
        self.ui.filepathRead.setText(self.filepath)

    def onInit(self):
        self.ctrl.sendInit()

    def onSpoolPCh(self):
        try:
            spoolP = float(self.ui.spoolP.text())
            self.ui.spoolP.setText('{0:.4f}'.format(spoolP))
        except ValueError:
            pass

    def onSpoolICh(self):
        try:
            spoolI = float(self.ui.spoolI.text())
            self.ui.spoolI.setText('{0:.4f}'.format(spoolI))
        except ValueError:
            pass

    def onSpoolDCh(self):
        try:
            spoolD = float(self.ui.spoolD.text())
            self.ui.spoolD.setText('{0:.4f}'.format(spoolD))
        except ValueError:
            pass

    def onOutIntCh(self):
        try:
            self.outInterval = float(self.ui.broadcastPeriodSet.text())
            self.ui.broadcastPeriodSet.setText('{0:.3f}'.format(self.outInterval))
        except ValueError:
            pass

    def onCtrlIntCh(self):
        try:
            self.ctrl.interval = float(self.ui.controlInterval.text())
            self.ui.controlInterval.setText('{0:.3f}'.format(self.ctrl.interval))
        except ValueError:
            pass

    def onHeatCh(self):
        try:
            temp = float(self.ui.filamentHeatSet.text())
            self.ui.filamentHeatSet.setText('{0:.1f}'.format(temp))
        except ValueError:
            pass

    def onHtrPCh(self):
        try:
            htrP = float(self.ui.htrP.text())
            self.ui.htrP.setText('{0:.4f}'.format(htrP))
        except ValueError:
            pass
    
    def onHtrICh(self):
        try:
            htrI = float(self.ui.htrI.text())
            self.ui.htrI.setText('{0:.4f}'.format(htrI))
        except ValueError:
            pass

    def onHtrDCh(self):
        try:
            htrD = float(self.ui.htrD.text())
            self.ui.htrD.setText('{0:.4f}'.format(htrD))
        except ValueError:
            pass

    def onFeedCh(self):
        try:
            feed_set_speed = float(self.ui.filamentFeedSet.text())
            self.ui.filamentFeedSet.setText('{0:.4f}'.format(feed_set_speed))
        except ValueError:
            pass

    def onSpoolCh(self):
        try:
            spool_set_speed = float(self.ui.spoolWindSet.text())
            self.ui.spoolWindSet.setText('{0:.3f}'.format(spool_set_speed))
        except ValueError:
            pass

    def onSpoolWind(self):
        self.ctrl.sendSpoolWind()

    def onFibCh(self):
        try:
            fiber_set_dia = float(self.ui.filamentDiamSet.text())
            self.ui.filamentDiamSet.setText('{0:.3f}'.format(fiber_set_dia))
        except ValueError:
            pass

    def onSetFeed(self):
        self.ctrl.feed_set_speed = float(self.ui.filamentFeedSet.text())
        self.ctrl.feed_dir = self.ui.feedFWDCheck.isChecked()
        self.ctrl.feed_is_changed = True
        self.ui.messageWindow.appendPlainText('Setting feed speed to: {0:.4f}RPS'.format(self.ctrl.feed_set_speed)) 

    def onSetFib(self):
        self.ctrl.fiber_set_dia = float(self.ui.filamentDiamSet.text())

    def onSetFibPID(self):
        self.ctrl.spoolP = float(self.ui.spoolP.text())
        self.ctrl.spoolI = float(self.ui.spoolI.text())
        self.ctrl.spoolD = float(self.ui.spoolD.text())

    def onSetSpool(self):
        self.ctrl.spool_set_speed = float(self.ui.spoolWindSet.text())
        self.ctrl.spool_dir = self.ui.spoolFWDCheck.isChecked()
        self.ctrl.spool_is_changed = True
        self.ui.messageWindow.appendPlainText('Setting spool speed to: {0:.3f}RPS'.format(self.ctrl.spool_set_speed)) 

    def onSetHtr(self):
        self.ctrl.htr_set_temp = float(self.ui.filamentHeatSet.text())
        self.ui.messageWindow.appendPlainText('Setting target heater temperature to: {0:.1f}C'.format(self.ctrl.htr_set_temp)) 

    def onSetHtrPID(self):
        self.ctrl.htrP = float(self.ui.htrP.text())
        self.ctrl.htrI = float(self.ui.htrI.text())
        self.ctrl.htrD = float(self.ui.htrD.text())
        self.ctrl.setHtrPID()
        self.ui.messageWindow.appendPlainText('Setting heater PID to: P={0:.4f}, I={1:.4f}, D={2:.4f}'.format(self.ctrl.htrP,self.ctrl.htrI,self.ctrl.htrD)) 

    def onStart(self):
        # start logging
        if self.ui.dataLogCheck.isChecked():
            self.filename = ("log_" + self.ui.ctrlOpts.currentText() + "_" + 
                             datetime.now().strftime("_%Y-%m-%d_%H-%M-%S"))
            self.filepath = self.ui.filepathRead.text()
            self.ui.messageWindow.appendPlainText('Starting Datalog File: ' + self.filepath + '//' + self.filename + '.csv')
            self.file = open(self.filepath + '//' + self.filename + '.csv', 'a', newline='')
            self.file_writer = csv.writer(self.file, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            self.file_writer.writerow(['Time (sec)', 'Heater Set (C)', 'Filament Feed Rate Set (RPS)', 
                                'Spool Wind Rate Set (RPS)', 'Filament Diameter Set (mm)', 
                                'Heater Actual (C)', 'Filament Feed Rate Actual (RPS)', 
                                'Spool Wind Rate Actual (RPS)', 'Filament Diameter Actual (mm)', 
                                'Total Fiber Produced (m)', 'Power (W)', 'Total Energy Used (Wh)'])
            self.log_timer.start(self.outInterval * 1000)
        self.ui.broadcastPeriodSet.setEnabled(False)
        self.ui.filepathSet.setEnabled(False)
        self.ui.dataLogCheck.setEnabled(False)
        try:
            self.ctrl.htr_set_temp = float(self.ui.filamentHeatSet.text())
            self.ctrl.feed_set_speed = float(self.ui.filamentFeedSet.text())
            self.ctrl.spool_set_speed = float(self.ui.spoolWindSet.text())
            self.ctrl.fiber_set_dia = float(self.ui.filamentDiamSet.text())
        except ValueError:
            pass
        self.ui.messageWindow.appendPlainText('Starting Process Control... ' + type(self.ctrl).__name__)
        self.ui.messageWindow.appendPlainText('Connecting to FrED...')
        self.ctrl.connect()
        self.ui.messageWindow.appendPlainText('Setting all Process Values...')
        # TODO
        self.onSetHtrPID()
        self.onSetHtr()
        self.onSetFeed()
        self.onSetSpool()

        self.ui.messageWindow.appendPlainText('Starting Control Threads...')
        self.ctrl.start()
        self.update_timer.start(self.update_actual_interval)
        # clean up GUI
        self.ui.startButton.setEnabled(False)
        self.ui.controlInterval.setEnabled(False)
        self.ui.broadcastPeriodSet.setEnabled(False)
        self.ui.ctrlOpts.setEnabled(False)
        self.ui.stopButton.setEnabled(True)
        self.ui.filepathSet.setEnabled(False)

    def onStop(self):
        if self.mqtt_timer.isActive():
            self.ui.messageWindow.appendPlainText('Stopping MQTT Broadcast.')
            self.mqtt_timer.stop()
            self.mqtt_timer = QtCore.QTimer()
            self.mqtt_timer.timeout.connect(self.mqttData)
        if self.log_timer.isActive():
            self.ui.messageWindow.appendPlainText('Stopping Data Log.')
            self.log_timer.stop()
            self.file.close()
            self.log_timer = QtCore.QTimer()
            self.log_timer.timeout.connect(self.logData)
        self.ui.messageWindow.appendPlainText('Stopping FrED Outputs...')
        self.ctrl.sendStop()
        self.ui.messageWindow.appendPlainText('Stopping Control Threads...')
        self.update_timer.stop()
        self.ctrl.is_running = False
        self.ctrl.join()
        self.ui.messageWindow.appendPlainText('Process Run Complete.')
        # reassign threads
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.updateActuals)
        self.ctrl = control_models.ManualDAQ()
        # cleanup and refersh GUI
        self.ui.startButton.setEnabled(True)
        self.ui.controlInterval.setEnabled(True)
        self.ui.broadcastPeriodSet.setEnabled(True)
        self.ui.ctrlOpts.setEnabled(True)
        self.ui.stopButton.setEnabled(False)
        self.ui.filepathSet.setEnabled(True)
        self.ui.broadcastPeriodSet.setEnabled(True)
        self.ui.filepathSet.setEnabled(True)
        self.ui.dataLogCheck.setEnabled(True)

    def updateControl(self):
        if (self.ui.ctrlOpts.currentText() == 'Manual Control'):
            self.ctrl = control_models.ManualDAQ()
            self.ui.filamentHeatSet.setEnabled(True)
            self.ui.filamentFeedSet.setEnabled(True)
            self.ui.spoolWindSet.setEnabled(True)
            self.ui.autoDiaCheck.setEnabled(False)
            self.ui.filamentDiamSet.setEnabled(False)
            self.ui.spoolP.setEnabled(False)
            self.ui.spoolI.setEnabled(False)
            self.ui.spoolD.setEnabled(False)
        self.ui.htrP.setText('{0:.4f}'.format(self.ctrl.htrP))
        self.ui.htrI.setText('{0:.4f}'.format(self.ctrl.htrI))
        self.ui.htrD.setText('{0:.4f}'.format(self.ctrl.htrD))
        self.ui.filamentHeatSet.setText('{0:.1f}'.format(self.ctrl.htr_set_temp))
        self.ui.filamentFeedSet.setText('{0:.4f}'.format(self.ctrl.feed_set_speed))
        self.ui.spoolWindSet.setText('{0:.3f}'.format(self.ctrl.spool_set_speed))
        self.ui.filamentDiamSet.setText('{0:.3f}'.format(self.ctrl.fiber_set_dia))
        if (self.ui.ctrlOpts.currentIndex() != -1):
            self.ui.messageWindow.appendPlainText('Setting Control: ' +
                                    self.ui.ctrlOpts.currentText())

    def updateActuals(self):
        self.ui.filamentHeatAct.setText('{0:.1f}'.format(self.ctrl.htr_temp))
        self.ui.filamentFeedAct.setText('{0:.4f}'.format(self.ctrl.feed_speed))
        self.ui.spoolWindAct.setText('{0:.3f}'.format(self.ctrl.spool_speed))
        self.ui.filamentDiamAct.setText('{0:.3f}'.format(self.ctrl.fiber_dia))
        self.ui.filamentTotLen.setText('{0:.2f}'.format(self.ctrl.fiber_len/1000.0))
        self.ui.totPowerAct.setText('{0:.1f}'.format(self.ctrl.sys_power))
        
if __name__ == "__main__":  
    logging.basicConfig(level=logging.INFO)
    # below lines add scaling funcitnoality for high res screens
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication([])
    win = fredwin()
    win.show()
    sys.exit(app.exec())