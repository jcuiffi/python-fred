"""
GUI control window for full FrED twin simulation. Imports 
'fredfulltwinGUIwin.py' created with QTDesigner - 'fredfulltwinGUIwin.ui'

Note: Use ">pyuic5 --from-imports fredfulltwinGUIwin.ui -o fredfulltwinGUIwin.py" for 
      conversion in the resources folder. Use ">pyrcc5 res_file.qrc -o 
      res_file_rc.py" to recompile the resources file.

Started 3/16/20
Author - J. Heim, J. Cuiffi, Penn State University
"""

from PyQt5 import QtWidgets, QtCore
from resources.fredfulltwinGUIwin import Ui_MainWindow
import logging
import process_models
import control_models
import sys
import csv
import time
from datetime import datetime
import pyqtgraph

class fredwin(QtWidgets.QMainWindow):

    def __init__(self):
        super(fredwin,self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # set basic state twin as base model
        self.ctrl = control_models.ManualStateTwin(process_models.BasicStateTwin())
        # add models to drop down list
        self.ui.ctrlOpts.currentIndexChanged.connect(self.updateControl)
        self.ui.ctrlOpts.addItems(['Basic State Twin',
                                   'Regression State Twin',
                                   'Regression Dynamic Twin'])
        self.ui.ctrlOpts.setCurrentIndex(0)
        # text elements
        self.ui.controlInterval.setText('0.500')
        self.ui.controlInterval.editingFinished.connect(self.onCtrlIntCh)
        self.ui.filamentDutySet.editingFinished.connect(self.onHtrDutCh)
        self.ui.filamentHeatSet.editingFinished.connect(self.onHeatCh)
        self.ui.htrP.editingFinished.connect(self.onHtrPCh)
        self.ui.htrI.editingFinished.connect(self.onHtrICh)
        self.ui.htrD.editingFinished.connect(self.onHtrDCh)
        self.ui.htrPIDInterval.editingFinished.connect(self.onHtrPIDInt)
        self.ui.filamentFeedSet.editingFinished.connect(self.onFeedCh)
        self.ui.spoolDutySet.editingFinished.connect(self.onSpoolDutCh)
        self.ui.spoolWindSet.editingFinished.connect(self.onSpoolCh)
        self.ui.spoolP.editingFinished.connect(self.onSpoolPCh)
        self.ui.spoolI.editingFinished.connect(self.onSpoolICh)
        self.ui.spoolD.editingFinished.connect(self.onSpoolDCh)
        self.ui.spoolPIDInterval.editingFinished.connect(self.onSpoolPIDInt)
        self.ui.windSet.editingFinished.connect(self.onWindCh)
        self.ui.filamentDiamSet.editingFinished.connect(self.onFibCh)
        self.ui.fibP.editingFinished.connect(self.onFibPCh)
        self.ui.fibI.editingFinished.connect(self.onFibICh)
        self.ui.fibD.editingFinished.connect(self.onFibDCh)
        self.ui.fibPIDInterval.editingFinished.connect(self.onFibPIDInt)
        self.ui.broadcastPeriodSet.setText('1.000')
        self.ui.broadcastPeriodSet.editingFinished.connect(self.onOutIntCh)
        self.ui.filepathRead.setText('./')
        self.ui.mqttTopic.setText('fred/twin/data')
        # check boxes
        self.ui.htrPIDCheck.stateChanged.connect(self.onHtrPIDChkCh)
        self.ui.spoolPIDCheck.stateChanged.connect(self.onSpoolPIDChkCh)
        self.ui.autoDiaCheck.stateChanged.connect(self.onFibPIDChkCh)
        self.ui.broadcastMQTTCheck.setEnabled(False)
        self.ui.broadcastMQTTCheck.stateChanged.connect(self.onMqttCh)
        self.ui.broadcastOPCCheck.setEnabled(False)
        self.ui.windAutoCheck.stateChanged.connect(self.onSetWindAuto)
        self.ui.dataLogCheck.stateChanged.connect(self.onLogChkCh)
        self.ui.HtrPlotChk.stateChanged.connect(self.onHtrPlotChkCh)
        self.ui.FibPlotChk.stateChanged.connect(self.onFibPlotChkCh)
        self.ui.SpoolPlotChk.stateChanged.connect(self.onSpoolPlotChkCh)
        # TODO - add OPC functions
        # buttons
        self.ui.htrSetButton.clicked.connect(self.onSetHtr)
        self.ui.htrPIDSetButton.clicked.connect(self.onSetHtrPID)
        self.ui.feedSetButton.clicked.connect(self.onSetFeed)
        self.ui.spoolSetButton.clicked.connect(self.onSetSpool)
        self.ui.spoolPIDButton.clicked.connect(self.onSetSpoolPID)
        self.ui.windButton.clicked.connect(self.onSetWind)
        self.ui.fiberSetButton.clicked.connect(self.onSetFib)
        self.ui.fiberPIDButton.clicked.connect(self.onSetFibPID)
        self.ui.filepathSet.clicked.connect(self.onFile)
        self.ui.startButton.clicked.connect(self.onStart)
        self.ui.stopButton.clicked.connect(self.onStop)
        self.ui.stopButton.setEnabled(False)
        # GUI Updates
        self.outInterval = float(self.ui.broadcastPeriodSet.text())
        self.filepath = ''
        self.filename = ''
        self.file = None
        self.file_writer = None
        self.update_actual_interval = float(self.ui.controlInterval.text())
        self.is_updating = False
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.updateActuals)
        self.log_timer = QtCore.QTimer()
        self.log_timer.timeout.connect(self.logData)
        self.log_timestamp = 0.0
        self.mqtt_timer = QtCore.QTimer()
        self.mqtt_timer.timeout.connect(self.mqttData)
        # plot setup
        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.updatePlot)
        self.ui.graphWidget.setBackground('w')
        self.ui.graphWidget.setLabel('bottom', 'Time (s)')
        self.yPlotVals = [0] * 200
        self.ui.graphWidget.setYRange(0.0,1.0)
        self.xPlotVals = [0] * 200
        self.ui.graphWidget.setXRange(-100.0,0.0)
        self.ui.graphWidget.showGrid(x=True, y=True)
        self.plotLine = None
        self.plotPen = None
        self.plotTimestamp = 0.0
        # TODO OPC
        #self.opc_timer = QtCore.QTimer()
        #self.opc_timer.timeout.connect(self.opcData)
    
    # Start/Stop and Output Functions

    def onStart(self):
        self.ui.messageWindow.appendPlainText('Starting Process Control... ' + type(self.ctrl).__name__)
        self.ui.messageWindow.appendPlainText('Starting FrED Twin Threads...')
        self.ctrl.twin.start()
        self.ui.messageWindow.appendPlainText('Starting Control Threads...')
        self.ctrl.is_running = True
        self.ctrl.start()
        self.update_timer.start(self.update_actual_interval * 1000)
        # clean up GUI
        self.ui.controlInterval.setEnabled(False)
        self.ui.htrSetButton.setEnabled(True)
        self.ui.feedSetButton.setEnabled(True)
        self.ui.spoolSetButton.setEnabled(True)
        self.onFibPIDChkCh()
        if self.ui.ctrlOpts.currentText() == 'Regression Dynamic Twin':
            self.onHtrPIDChkCh()
            self.onSpoolPIDChkCh()
            self.ui.windButton.setEnabled(True)
        self.ui.startButton.setEnabled(False)
        self.ui.ctrlOpts.setEnabled(False)
        self.ui.stopButton.setEnabled(True)
        
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
        self.ui.messageWindow.appendPlainText('Stopping Update Threads...')
        self.update_timer.stop()
        self.ui.messageWindow.appendPlainText('Stopping FrED Twin...')
        if self.ctrl.twin.is_running:
            self.ctrl.twin.is_running = False
            self.ctrl.twin.join()
        if self.ctrl.is_running:
            self.ctrl.is_running = False
            self.ctrl.join()
            self.ui.messageWindow.appendPlainText('Process Run Complete.')
        # reassign threads
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.updateActuals)
        self.ui.ctrlOpts.setCurrentIndex(0)
        self.updateControl()
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

    def logData(self, firstline=False):
        if firstline:
            self.file_writer.writerow(['Time (sec)', 'Run Time (sec)', 'Heater Set (C)', 'Heater Duty (0-1)', 
                                'Filament Feed Rate Set (RPS)', 'Spool Wind Rate Set (RPS)', 'Spool Duty (0-1)',
                                'Wind B-F Speed (PPS)', 'Filament Diameter Set (mm)', 
                                'Heater Actual (C)', 'Filament Feed Rate Actual (RPS)', 
                                'Spool Wind Rate Actual (RPS)', 'Wind Direction (R/L)', 'Wind Count (#)',
                                'Filament Diameter Actual (mm)','Total Fiber Produced (m)', 
                                'Heater Current (mA)','Spool DC Motor Current (mA)','Stepper and 12V Current (mA)',
                                'Total Power (W)', 'Total Energy Used (Wh)'])
        else:
            now = time.time()
            self.file_writer.writerow([now, now - self.log_timestamp, self.ctrl.htr_set_temp, self.ctrl.htr_set_pwr, 
                                self.ctrl.feed_set_speed, self.ctrl.spool_set_speed, self.ctrl.spool_set_pwr,
                                self.ctrl.wind_set_freq, self.ctrl.fiber_set_dia, 
                                self.ctrl.twin.htr_temp, self.ctrl.twin.feed_speed, 
                                self.ctrl.twin.spool_speed, int(self.ctrl.twin.wind_dir), self.ctrl.twin.wind_count,
                                self.ctrl.twin.fiber_dia, self.ctrl.twin.fiber_len, 
                                self.ctrl.twin.htr_current, self.ctrl.twin.spool_current, self.ctrl.twin.step_current,
                                self.ctrl.twin.sys_power, self.ctrl.twin.sys_energy])
    
    def mqttData(self):
        # TODO broadcast mqtt data
        pass

    def opcData(self):
        # TODO broadcast OPC data
        pass

    def updatePlot(self):
        self.xPlotVals = self.xPlotVals[1:]
        self.xPlotVals.append(time.time() - self.plotTimestamp)
        self.yPlotVals = self.yPlotVals[1:]
        if self.ui.FibPlotChk.isChecked():
            self.yPlotVals.append(self.ctrl.twin.fiber_dia)
            self.plotLine.setData(self.xPlotVals, self.yPlotVals, pen=self.plotPen)
        elif self.ui.HtrPlotChk.isChecked():
            self.yPlotVals.append(self.ctrl.twin.htr_temp)
            self.plotLine.setData(self.xPlotVals, self.yPlotVals, pen=self.plotPen)
        elif self.ui.SpoolPlotChk.isChecked():
            self.yPlotVals.append(self.ctrl.twin.spool_speed)
            self.plotLine.setData(self.xPlotVals, self.yPlotVals, pen=self.plotPen)
        self.ui.graphWidget.setXRange(self.xPlotVals[-1]-100.0,self.xPlotVals[-1])

    # GUI Updates

    def updateControl(self):
        if ((self.ui.ctrlOpts.currentText() == 'Basic State Twin') or
            (self.ui.ctrlOpts.currentText() == 'Regression State Twin')):
            if self.ui.ctrlOpts.currentText() == 'Basic State Twin':
                self.ctrl = control_models.ManualStateTwin(process_models.BasicStateTwin())
            else:
                self.ctrl = control_models.ManualStateTwin(process_models.RegressionStateTwin())
            self.ui.filamentDutySet.setEnabled(False)
            self.ui.filamentHeatSet.setEnabled(True)
            self.ui.filamentHeatSet.setText('{0:.1f}'.format(self.ctrl.htr_set_temp))
            self.ui.htrPIDCheck.setChecked(True)
            self.ui.htrPIDCheck.setEnabled(False)
            self.ui.htrP.setEnabled(False)
            self.ui.htrI.setEnabled(False)
            self.ui.htrD.setEnabled(False)
            self.ui.htrPIDInterval.setEnabled(False)
            self.ui.feedFWDCheck.setEnabled(False)
            self.ui.filamentFeedSet.setEnabled(True)
            self.ui.filamentFeedSet.setText('{0:.4f}'.format(self.ctrl.feed_set_speed))
            self.ui.spoolFWDCheck.setEnabled(False)
            self.ui.spoolDutySet.setEnabled(False)
            self.ui.spoolWindSet.setEnabled(True)
            self.ui.spoolWindSet.setText('{0:.3f}'.format(self.ctrl.spool_set_speed))
            self.ui.spoolPIDCheck.setChecked(True)
            self.ui.spoolPIDCheck.setEnabled(False)
            self.ui.spoolP.setEnabled(False)
            self.ui.spoolI.setEnabled(False)
            self.ui.spoolD.setEnabled(False)
            self.ui.spoolPIDInterval.setEnabled(False)
            self.ui.windAutoCheck.setChecked(True)
            self.ui.windAutoCheck.setEnabled(False)
            self.ui.windRTCheck.setEnabled(False)
            self.ui.windSet.setEnabled(False)
            self.ui.autoDiaCheck.setChecked(False)
            self.ui.filamentDiamSet.setEnabled(False)
            self.ui.filamentDiamSet.setText('{0:.3f}'.format(self.ctrl.fiber_set_dia))
            self.ui.fibP.setEnabled(False)
            self.ui.fibI.setEnabled(False)
            self.ui.fibD.setEnabled(False)
            self.ui.fibPIDInterval.setEnabled(False)
        elif (self.ui.ctrlOpts.currentText() == 'Regression Dynamic Twin'):
            self.ctrl = control_models.ManualDynamicTwin(process_models.RegressionDynamicTwin())
            self.ui.htrPIDCheck.setChecked(False)
            self.ui.htrPIDCheck.setEnabled(True)
            self.onHtrPIDChkCh()
            self.ui.spoolPIDCheck.setChecked(False)
            self.ui.spoolPIDCheck.setEnabled(False)
            self.onSpoolPIDChkCh()
            self.ui.autoDiaCheck.setChecked(False)
            # TODO - setup auto diameter
            self.ui.autoDiaCheck.setEnabled(False)
            self.onFibPIDChkCh()
            self.ui.filamentDutySet.setText('{0:.3f}'.format(self.ctrl._htr_set_pwr))
            self.ui.filamentHeatSet.setText('{0:.1f}'.format(self.ctrl.htr_set_temp))
            self.ui.htrP.setText('{0:.5f}'.format(self.ctrl.htrP))
            self.ui.htrI.setText('{0:.5f}'.format(self.ctrl.htrI))
            self.ui.htrD.setText('{0:.5f}'.format(self.ctrl.htrD))
            self.ui.htrPIDInterval.setText('{0:.3f}'.format(self.ctrl.htrPIDint))
            self.ui.filamentFeedSet.setText('{0:.4f}'.format(self.ctrl.feed_set_speed))
            self.ui.spoolDutySet.setText('{0:.3f}'.format(self.ctrl.spool_set_pwr))
            self.ui.spoolWindSet.setText('{0:.3f}'.format(self.ctrl.spool_set_speed))
            self.ui.spoolP.setText('{0:.5f}'.format(self.ctrl.spoolP))
            self.ui.spoolI.setText('{0:.5f}'.format(self.ctrl.spoolI))
            self.ui.spoolD.setText('{0:.5f}'.format(self.ctrl.spoolD))
            self.ui.spoolPIDInterval.setText('{0:.3f}'.format(self.ctrl.spoolPIDint))
            self.ui.windSet.setText('{0:.3}'.format(self.ctrl.wind_set_freq))
            self.ui.filamentDiamSet.setText('{0:.3f}'.format(self.ctrl.fiber_set_dia))
            self.ui.fibP.setText('{0:.5f}'.format(self.ctrl.fibP))
            self.ui.fibI.setText('{0:.5f}'.format(self.ctrl.fibI))
            self.ui.fibD.setText('{0:.5f}'.format(self.ctrl.fibD))
            self.ui.fibPIDInterval.setText('{0:.3f}'.format(self.ctrl.fibPIDint))
        if (self.ui.ctrlOpts.currentIndex() != -1):
            self.ui.messageWindow.appendPlainText('Setting Control: ' +
                                    self.ui.ctrlOpts.currentText())
            self.ui.htrSetButton.setEnabled(False)
            self.ui.htrPIDSetButton.setEnabled(False)
            self.ui.feedSetButton.setEnabled(False)
            self.ui.spoolSetButton.setEnabled(False)
            self.ui.spoolPIDButton.setEnabled(False)
            self.ui.windButton.setEnabled(False)
            self.ui.fiberSetButton.setEnabled(False)
            self.ui.fiberPIDButton.setEnabled(False)
            
    def updateActuals(self):
        self.ui.filamentHeatAct.setText('{0:.1f}'.format(self.ctrl.twin.htr_temp))
        self.ui.filamentFeedAct.setText('{0:.4f}'.format(self.ctrl.twin.feed_speed))
        self.ui.spoolWindAct.setText('{0:.3f}'.format(self.ctrl.twin.spool_speed))
        self.ui.filamentDiamAct.setText('{0:.3f}'.format(self.ctrl.twin.fiber_dia))
        self.ui.filamentTotLen.setText('{0:.2f}'.format(self.ctrl.twin.fiber_len))
        self.ui.totPowerAct.setText('{0:.1f}'.format(self.ctrl.twin.sys_power))
        self.ui.totEnergyAct.setText('{0:.1f}'.format(self.ctrl.twin.sys_energy))

    def closeEvent(self, event):
        # override to shut down threads gracefully
        self.onStop()
        event.accept()

    # Text Area Functions

    def onCtrlIntCh(self):
        try:
            intr = float(self.ui.controlInterval.text())
            intr = intr if intr >= 0.2 else 0.2
            self.update_actual_interval = intr
            self.ui.controlInterval.setText('{0:.3f}'.format(intr))
        except ValueError:
            pass
    
    def onFeedCh(self):
        try:
            feed_set_speed = float(self.ui.filamentFeedSet.text())
            feed_set_speed = feed_set_speed if feed_set_speed >= 0.0 else 0.0
            self.ui.filamentFeedSet.setText('{0:.4f}'.format(feed_set_speed))
        except ValueError:
            pass

    def onFibCh(self):
        try:
            fiber_set_dia = float(self.ui.filamentDiamSet.text())
            fiber_set_dia = fiber_set_dia if fiber_set_dia >= 0.0 else 0.0
            fiber_set_dia = fiber_set_dia if fiber_set_dia <= 1.5 else 1.5
            self.ui.filamentDiamSet.setText('{0:.3f}'.format(fiber_set_dia))
        except ValueError:
            pass

    def onFibPCh(self):
        try:
            fibP = float(self.ui.fibP.text())
            self.ui.fibP.setText('{0:.5f}'.format(fibP))
        except ValueError:
            pass
    
    def onFibICh(self):
        try:
            fibI = float(self.ui.fibI.text())
            self.ui.fibI.setText('{0:.5f}'.format(fibI))
        except ValueError:
            pass

    def onFibDCh(self):
        try:
            fibD = float(self.ui.fibD.text())
            self.ui.fibD.setText('{0:.5f}'.format(fibD))
        except ValueError:
            pass

    def onFibPIDInt(self):
        try:
            intr = float(self.ui.fibPIDInterval.text())
            intr = intr if intr >= 0.05 else 0.05
            self.ui.fibPIDInterval.setText('{0:.3f}'.format(intr))
        except ValueError:
            pass

    def onFile(self):
        self.filepath = QtWidgets.QFileDialog.getExistingDirectory(
                            self, 'Datalog Save Folder')
        self.ui.filepathRead.setText(self.filepath + '/')

    def onHtrDutCh(self):
        try:
            duty = float(self.ui.filamentDutySet.text())
            duty = duty if duty <= 1.0 else 1.0
            duty = duty if duty >= 0.0 else 0.0
            self.ui.filamentDutySet.setText('{0:.3f}'.format(duty))
        except ValueError:
            pass

    def onHeatCh(self):
        try:
            temp = float(self.ui.filamentHeatSet.text())
            temp = temp if temp <= 120.0 else 120.0
            temp = temp if temp >= 0.0 else 0.0
            self.ui.filamentHeatSet.setText('{0:.1f}'.format(temp))
        except ValueError:
            pass

    def onHtrPCh(self):
        try:
            htrP = float(self.ui.htrP.text())
            self.ui.htrP.setText('{0:.5f}'.format(htrP))
        except ValueError:
            pass
    
    def onHtrICh(self):
        try:
            htrI = float(self.ui.htrI.text())
            self.ui.htrI.setText('{0:.5f}'.format(htrI))
        except ValueError:
            pass

    def onHtrDCh(self):
        try:
            htrD = float(self.ui.htrD.text())
            self.ui.htrD.setText('{0:.5f}'.format(htrD))
        except ValueError:
            pass

    def onHtrPIDInt(self):
        try:
            intr = float(self.ui.htrPIDInterval.text())
            intr = intr if intr >= 0.05 else 0.05
            self.ui.htrPIDInterval.setText('{0:.3f}'.format(intr))
        except ValueError:
            pass
    
    def onOutIntCh(self):
        try:
            intr = float(self.ui.broadcastPeriodSet.text())
            intr = intr if intr >= 0.05 else 0.05
            self.outInterval = intr
            self.ui.broadcastPeriodSet.setText('{0:.3f}'.format(intr))
        except ValueError:
            pass
    
    def onSpoolCh(self):
        try:
            spool_set_speed = float(self.ui.spoolWindSet.text())
            spool_set_speed = spool_set_speed if spool_set_speed <= 1.5 else 1.5
            spool_set_speed = spool_set_speed if spool_set_speed >= 0.0 else 0.0
            self.ui.spoolWindSet.setText('{0:.3f}'.format(spool_set_speed))
        except ValueError:
            pass

    def onSpoolDutCh(self):
        try:
            duty = float(self.ui.spoolDutySet.text())
            duty = duty if duty <= 1.0 else 1.0
            duty = duty if duty >= 0.0 else 0.0
            self.ui.spoolDutySet.setText('{0:.3f}'.format(duty))
        except ValueError:
            pass

    def onSpoolPCh(self):
        try:
            spoolP = float(self.ui.spoolP.text())
            self.ui.spoolP.setText('{0:.5f}'.format(spoolP))
        except ValueError:
            pass

    def onSpoolICh(self):
        try:
            spoolI = float(self.ui.spoolI.text())
            self.ui.spoolI.setText('{0:.5f}'.format(spoolI))
        except ValueError:
            pass

    def onSpoolDCh(self):
        try:
            spoolD = float(self.ui.spoolD.text())
            self.ui.spoolD.setText('{0:.5f}'.format(spoolD))
        except ValueError:
            pass

    def onSpoolPIDInt(self):
        try:
            intr = float(self.ui.spoolPIDInterval.text())
            intr = intr if intr >= 0.05 else 0.05
            self.ui.spoolPIDInterval.setText('{0:.3f}'.format(intr))
        except ValueError:
            pass

    def onWindCh(self):
        try:
            pps = float(self.ui.windSet.text())
            pps = pps if pps >= 0.0 else 0.0
            self.ui.windSet.setText('{0:.1f}'.format(pps))
        except ValueError:
            pass

    # Check Box Functions

    def onFibPlotChkCh(self):
        if self.ui.FibPlotChk.isChecked():
            if self.ui.SpoolPlotChk.isChecked():
                self.ui.SpoolPlotChk.setChecked(False)
                self.onSpoolPlotChkCh()
            if self.ui.HtrPlotChk.isChecked():
                self.ui.HtrPlotChk.setChecked(False)
                self.onHtrPlotChkCh()
            self.ui.graphWidget.setLabel('left', 'Fiber Diameter (mm)')
            self.yPlotVals = [0] * 200
            self.xPlotVals = [0] * 200
            self.plotTimestamp = time.time()
            self.xPlotVals = self.xPlotVals[1:]
            self.xPlotVals.append(time.time() - self.plotTimestamp)
            self.yPlotVals = self.yPlotVals[1:]
            self.yPlotVals.append(self.ctrl.twin.fiber_dia)
            self.plotPen = pyqtgraph.mkPen(color='r', width=4)
            self.plotLine = self.ui.graphWidget.plot(self.xPlotVals, self.yPlotVals, pen=self.plotPen)
            self.ui.graphWidget.setYRange(0.0,1.0)
            self.ui.graphWidget.setXRange(self.xPlotVals[-1]-100.0, self.xPlotVals[-1])
            self.plot_timer.start(self.outInterval * 1000.0)
        else:
            self.plot_timer.stop()
            self.plot_timer = QtCore.QTimer()
            self.plot_timer.timeout.connect(self.updatePlot)
            self.ui.graphWidget.clear()

    def onHtrPIDChkCh(self):
        if self.ui.htrPIDCheck.isChecked():
            self.ui.htrP.setEnabled(True)
            self.ui.htrI.setEnabled(True)
            self.ui.htrD.setEnabled(True)
            self.ui.htrPIDInterval.setEnabled(True)
            self.ui.filamentDutySet.setEnabled(False)
            self.ui.filamentHeatSet.setEnabled(True)
            if self.ctrl.is_running:
                self.ui.htrPIDSetButton.setEnabled(True)
        else:
            self.ui.htrP.setEnabled(False)
            self.ui.htrI.setEnabled(False)
            self.ui.htrD.setEnabled(False)
            self.ui.htrPIDInterval.setEnabled(False)
            self.ui.filamentDutySet.setEnabled(True)
            self.ui.filamentHeatSet.setEnabled(False)
            self.ui.htrPIDSetButton.setEnabled(False)
            self.ctrl.setHtrPID(False)

    def onHtrPlotChkCh(self):
        if self.ui.HtrPlotChk.isChecked():
            if self.ui.SpoolPlotChk.isChecked():
                self.ui.SpoolPlotChk.setChecked(False)
                self.onSpoolPlotChkCh()
            if self.ui.FibPlotChk.isChecked():
                self.ui.FibPlotChk.setChecked(False)
                self.onFibPlotChkCh()
            self.ui.graphWidget.setLabel('left', 'Temperature (C)')
            self.yPlotVals = [0] * 200
            self.xPlotVals = [0] * 200
            self.plotTimestamp = time.time()
            self.xPlotVals = self.xPlotVals[1:]
            self.xPlotVals.append(time.time() - self.plotTimestamp)
            self.yPlotVals = self.yPlotVals[1:]
            self.yPlotVals.append(self.ctrl.twin.htr_temp)
            self.plotPen = pyqtgraph.mkPen(color='r', width=4)
            self.plotLine = self.ui.graphWidget.plot(self.xPlotVals, self.yPlotVals, pen=self.plotPen)
            self.ui.graphWidget.setYRange(0.0,120.0)
            self.ui.graphWidget.setXRange(self.xPlotVals[-1]-100.0, self.xPlotVals[-1])
            self.plot_timer.start(self.outInterval * 1000.0)
        else:
            self.plot_timer.stop()
            self.plot_timer = QtCore.QTimer()
            self.plot_timer.timeout.connect(self.updatePlot)
            self.ui.graphWidget.clear()

    def onLogChkCh(self):
        if self.ui.dataLogCheck.isChecked(): # start logging
            self.filename = ("log_" + self.ui.ctrlOpts.currentText() + "_" + 
                            datetime.now().strftime("_%Y-%m-%d_%H-%M-%S"))
            self.filepath = self.ui.filepathRead.text()
            self.ui.messageWindow.appendPlainText('Starting Data Log File: ' + self.filepath + self.filename + '.csv')
            self.file = open(self.filepath + self.filename + '.csv', 'a', newline='')
            self.file_writer = csv.writer(self.file, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            self.log_timestamp = time.time()
            self.logData(True)
            self.log_timer.start(self.outInterval * 1000)
            self.ui.broadcastPeriodSet.setEnabled(False)
            self.ui.filepathSet.setEnabled(False)
        else: # stop logging
            if self.log_timer.isActive():
                self.ui.messageWindow.appendPlainText('Stopping Data Log.')
                self.log_timer.stop()
                self.file.close()
                self.log_timer = QtCore.QTimer()
                self.log_timer.timeout.connect(self.logData)
                self.ui.broadcastPeriodSet.setEnabled(True)
                self.ui.filepathSet.setEnabled(True)

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

    def onSetWindAuto(self):
        if self.ui.windAutoCheck.isChecked():
            self.ui.windSet.setEnabled(False)
            self.ui.windRTCheck.setEnabled(False)
        else:
            self.ui.windSet.setEnabled(True)
            self.ui.windRTCheck.setEnabled(True)
            if self.ctrl.is_running:
                self.ui.windButton.setEnabled(True)

    def onSpoolPIDChkCh(self):
        if self.ui.spoolPIDCheck.isChecked():
            self.ui.spoolP.setEnabled(True)
            self.ui.spoolI.setEnabled(True)
            self.ui.spoolD.setEnabled(True)
            self.ui.spoolPIDInterval.setEnabled(True)
            self.ui.spoolDutySet.setEnabled(False)
            self.ui.spoolWindSet.setEnabled(True)
            if self.ctrl.is_running:
                self.ui.spoolPIDButton.setEnabled(True)
        else:
            self.ui.spoolP.setEnabled(False)
            self.ui.spoolI.setEnabled(False)
            self.ui.spoolD.setEnabled(False)
            self.ui.spoolPIDInterval.setEnabled(False)
            self.ui.spoolDutySet.setEnabled(True)
            self.ui.spoolWindSet.setEnabled(False)
            self.ui.spoolPIDButton.setEnabled(False)
            self.ctrl.setSpoolPID(False)

    def onSpoolPlotChkCh(self):
        if self.ui.SpoolPlotChk.isChecked():
            if self.ui.HtrPlotChk.isChecked():
                self.ui.HtrPlotChk.setChecked(False)
                self.onHtrPlotChkCh()
            if self.ui.FibPlotChk.isChecked():
                self.ui.FibPlotChk.setChecked(False)
                self.onFibPlotChkCh()
            self.ui.graphWidget.setLabel('left', 'Spool Speed (RPS)')
            self.yPlotVals = [0] * 200
            self.xPlotVals = [0] * 200
            self.plotTimestamp = time.time()
            self.xPlotVals = self.xPlotVals[1:]
            self.xPlotVals.append(time.time() - self.plotTimestamp)
            self.yPlotVals = self.yPlotVals[1:]
            self.yPlotVals.append(self.ctrl.twin.spool_speed)
            self.plotPen = pyqtgraph.mkPen(color='r', width=4)
            self.plotLine = self.ui.graphWidget.plot(self.xPlotVals, self.yPlotVals, pen=self.plotPen)
            self.ui.graphWidget.setYRange(0.0,2.0)
            self.ui.graphWidget.setXRange(self.xPlotVals[-1]-100.0, self.xPlotVals[-1])
            self.plot_timer.start(self.outInterval * 1000.0)
        else:
            self.plot_timer.stop()
            self.plot_timer = QtCore.QTimer()
            self.plot_timer.timeout.connect(self.updatePlot)
            self.ui.graphWidget.clear()

    def onFibPIDChkCh(self):
        if self.ui.autoDiaCheck.isChecked():
            if ((self.ui.ctrlOpts.currentText() == 'Basic State Twin') or
                (self.ui.ctrlOpts.currentText() == 'Regression State Twin')):
                self.ctrl.calc_spool = True
                self.ui.spoolWindSet.setEnabled(False)
                self.ui.spoolSetButton.setEnabled(False)
                self.ui.filamentDiamSet.setEnabled(True)
                if self.ctrl.is_running:
                    self.ui.fiberSetButton.setEnabled(True)
            else:
                self.ui.fibP.setEnabled(True)
                self.ui.fibI.setEnabled(True)
                self.ui.fibD.setEnabled(True)
                self.ui.fibPIDInterval.setEnabled(True)
                self.ui.filamentDiamSet.setEnabled(True)
                if self.ctrl.is_running:
                    self.ui.fiberPIDButton.setEnabled(True)
                    self.ui.fiberSetButton.setEnabled(True)
        else:
            self.ui.fibP.setEnabled(False)
            self.ui.fibI.setEnabled(False)
            self.ui.fibD.setEnabled(False)
            self.ui.fibPIDInterval.setEnabled(False)
            self.ui.filamentDiamSet.setEnabled(False)
            self.ui.fiberPIDButton.setEnabled(False)
            self.ui.fiberSetButton.setEnabled(False)
            if ((self.ui.ctrlOpts.currentText() == 'Basic State Twin') or
                (self.ui.ctrlOpts.currentText() == 'Regression State Twin')):
                self.ctrl.calc_spool = False
                self.ui.filamentDiamSet.setEnabled(False)
                self.ui.fiberSetButton.setEnabled(False)
                self.ui.spoolWindSet.setEnabled(True)   
                if self.ctrl.is_running:
                    self.ui.spoolSetButton.setEnabled(True)
            else:
                pass
                self.ctrl.setFibPID(False)

    # Button Functions

    def onSetFeed(self):
        try:
            self.ctrl.feed_set_speed = float(self.ui.filamentFeedSet.text())
            self.ui.messageWindow.appendPlainText('Setting feed speed to: {0:.4f}RPS'.format(self.ctrl.feed_set_speed)) 
        except ValueError:
            pass

    def onSetFib(self):
        try:
            self.ctrl.fiber_set_dia = float(self.ui.filamentDiamSet.text())
            self.ui.messageWindow.appendPlainText('Setting fiber diameter to: {0:.3f}mm'.format(self.ctrl.fiber_set_dia))
        except ValueError:
            pass

    def onSetFibPID(self):
        try:
            self.ctrl.fibP = float(self.ui.fibP.text())
            self.ctrl.fibI = float(self.ui.fibI.text())
            self.ctrl.fibD = float(self.ui.fibD.text())
            self.ctrl.fibPIDint = float(self.ui.fibPIDInterval.text())
            self.ctrl.setFibPID(True)
            self.ui.messageWindow.appendPlainText('Setting fiber PID to: P={0:.5f}, I={1:.5f}, D={2:.5f}'.format(self.ctrl.fibP,self.ctrl.fibI,self.ctrl.fibD)) 
        except ValueError:
            pass

    def onSetHtr(self):
        try:
            if self.ui.htrPIDCheck.isChecked():
                self.ctrl.htr_set_temp = float(self.ui.filamentHeatSet.text())
                self.ui.messageWindow.appendPlainText('Setting target heater temperature to: {0:.1f}C'.format(self.ctrl.htr_set_temp)) 
            else:
                self.ctrl.htr_set_pwr = float(self.ui.filamentDutySet.text())
                self.ui.messageWindow.appendPlainText('Setting target heater power to: {0:.3f}%'.format(self.ctrl.htr_set_pwr * 100)) 
        except ValueError:
                pass

    def onSetHtrPID(self):
        try:
            self.ctrl.htrP = float(self.ui.htrP.text())
            self.ctrl.htrI = float(self.ui.htrI.text())
            self.ctrl.htrD = float(self.ui.htrD.text())
            self.ctrl.htrPIDInt = float(self.ui.htrPIDInterval.text())
            self.ctrl.setHtrPID(True)
            self.ui.messageWindow.appendPlainText('Setting heater PID to: P={0:.5f}, I={1:.5f}, D={2:.5f}'.format(self.ctrl.htrP,self.ctrl.htrI,self.ctrl.htrD)) 
        except ValueError:
            pass

    def onSetSpool(self):
        try:
            self.ctrl.spool_dir = self.ui.spoolFWDCheck.isChecked()
            if self.ui.spoolPIDCheck.isChecked():
                self.ctrl.spool_set_speed = float(self.ui.spoolWindSet.text())
                self.ui.messageWindow.appendPlainText('Setting spool speed to: {0:.3f}RPS'.format(self.ctrl.spool_set_speed)) 
            else:
                self.ctrl.spool_set_pwr = float(self.ui.spoolDutySet.text())
                # set nominal set speed
                self.ctrl.spool_set_speed = 1.5 * self.ctrl.spool_set_pwr
                self.ui.messageWindow.appendPlainText('Setting spool power to: {0:.3f}%'.format(self.ctrl.spool_set_pwr * 100)) 
        except ValueError:
            pass

    def onSetSpoolPID(self):
        try:
            self.ctrl.spoolP = float(self.ui.spoolP.text())
            self.ctrl.spoolI = float(self.ui.spoolI.text())
            self.ctrl.spoolD = float(self.ui.spoolD.text())
            self.ctrl.spoolPIDint = float(self.ui.spoolPIDInterval.text())
            self.ctrl.setSpoolPID(True)
            self.ui.messageWindow.appendPlainText('Setting spool PID to: P={0:.5f}, I={1:.5f}, D={2:.5f}'.format(self.ctrl.spoolP,self.ctrl.spoolI,self.ctrl.spoolD)) 
        except ValueError:
            pass

    def onSetWind(self):
        try:
            if self.ui.windAutoCheck.isChecked():
                self.ctrl.sendSpoolWind(True)
                self.ui.messageWindow.appendPlainText('Setting automatic spool winding back-forth.') 
            else:
                self.ctrl.wind_dir = self.ui.windRTCheck.isChecked()
                self.ctrl.wind_set_freq = float(self.ui.windSet.text())
                self.ctrl.sendSpoolWind(False)
                self.ui.messageWindow.appendPlainText('Setting spool back-forth PPS: {0:.1f}'.format(self.ctrl.wind_set_freq)) 
        except ValueError:
            pass
        
if __name__ == "__main__":  
    logging.basicConfig(level=logging.INFO)
    #logging.basicConfig(level=logging.DEBUG)
    
    # below lines add scaling funcitnoality for high res screens
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication([])
    win = fredwin()
    win.show()
    sys.exit(app.exec())