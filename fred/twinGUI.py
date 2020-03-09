"""
GUI control window for FrED process and control simulations. Imports 
'twinGUIwin.py' created with QTDesigner - 'twinGUIwin.ui'

Note: Use ">pyuic5 --from-imports twinGUIwin.ui -o twinGUIwin.py" for 
      conversion in the resources folder. Use ">pyrcc5 res_file.qrc -o 
      res_file_rc.py" to recompile the resources file.

Started 2/18/20
Author - J. Heim, J. Cuiffi, Penn State University
"""

from PyQt5 import QtWidgets, QtCore
from resources.twinGUIwin import Ui_MainWindow
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
        self.twin = process_models.BasicStateTwin()
        self.ctrl = control_models.ManualStateTwin()
        # add models and processes to drop down lists
        self.ui.ctrlOpts.currentIndexChanged.connect(self.updateControl)
        self.ui.processModelSelect.addItems(['Basic State Model',
                                             'Basic Dynamic Model'])
        self.ui.processModelSelect.currentIndexChanged.connect(self.updateModel)
        self.ui.processModelSelect.setCurrentIndex(0)
        self.updateModel()
        self.updateActuals()
        self.ui.filamentHeatSet.editingFinished.connect(self.onHeatCh)
        self.ui.filamentFeedSet.editingFinished.connect(self.onFeedCh)
        self.ui.spoolWindSet.editingFinished.connect(self.onSpoolCh)
        self.ui.filamentDiamSet.editingFinished.connect(self.onFibCh)
        self.ui.processInterval.setText('{0:.3f}'.format(self.twin.interval))
        self.ui.processInterval.editingFinished.connect(self.onProcIntCh)
        self.ui.controlInterval.setText('{0:.3f}'.format(self.ctrl.interval))
        self.ui.controlInterval.editingFinished.connect(self.onCtrlIntCh)
        self.ui.broadcastPeriodSet.setText('{0:.3f}'.format(self.ctrl.interval))
        self.ui.broadcastPeriodSet.editingFinished.connect(self.onOutIntCh)
        self.ui.mqttTopic.setText('fred/twindata')
        # buttons
        self.ui.startButton.clicked.connect(self.onStart)
        self.ui.stopButton.clicked.connect(self.onStop)
        self.ui.stopButton.setEnabled(False)
        self.ui.filepathSet.clicked.connect(self.onFile)
        self.ui.broadcastMQTTCheck.stateChanged.connect(self.onMqttCh)
        self.ui.plotCheck.stateChanged.connect(self.onPlotCh)
        # GUI Updates
        self.outInterval = float(self.ui.broadcastPeriodSet.text())
        self.filepath = ''
        self.filename = ''
        self.file = None
        self.file_writer = None
        self.update_actual_interval = 200       # msec
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.updateActuals)
        self.log_timer = QtCore.QTimer()
        self.log_timer.timeout.connect(self.logData)
        self.mqtt_timer = QtCore.QTimer()
        self.mqtt_timer.timeout.connect(self.mqttData)
        self.opc_timer = QtCore.QTimer()
        self.opc_timer.timeout.connect(self.opcData)
        self.ui.graphWidget.setBackground('w')
        self.ui.graphWidget.setLabel('left', 'Diameter (mm)')
        self.ui.graphWidget.setLabel('bottom', 'Time (s)')
        self.yPlotVals = [0] * 200
        self.ui.graphWidget.setYRange(0.0,1.0)
        self.xPlotVals = [0] * 200
        self.ui.graphWidget.setXRange(-100.0,0.0)
        self.ui.graphWidget.showGrid(x=True, y=True)
        self.plotLine = None
        self.plotPen = None
        self.plotTimestamp = NotImplemented
        self.plot_interval = 500
        self.plot_timer = QtCore.QTimer()
        self.plot_timer.timeout.connect(self.updatePlot)

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
                                self.twin.htr_temp, self.twin.feed_speed, 
                                self.twin.spool_speed, self.twin.fiber_dia, 
                                self.twin.fiber_len, self.twin.sys_power, self.twin.sys_energy])

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
    
    def onPlotCh(self):
        if self.ui.plotCheck.isChecked():
            self.plotTimestamp = time.time()
            self.xPlotVals = self.xPlotVals[1:]
            self.xPlotVals.append(time.time() - self.plotTimestamp)
            self.yPlotVals = self.yPlotVals[1:]
            self.yPlotVals.append(self.twin.fiber_dia)
            self.plotPen = pyqtgraph.mkPen(color='k', width=5)
            self.plotLine = self.ui.graphWidget.plot(self.xPlotVals, self.yPlotVals, pen=self.plotPen)
            self.ui.graphWidget.setXRange(self.xPlotVals[-1]-100.0, self.xPlotVals[-1])
            self.plot_timer.start(self.plot_interval)
        else:
            self.plot_timer.stop()
            self.plot_timer = QtCore.QTimer()
            self.plot_timer.timeout.connect(self.updatePlot)

    def updatePlot(self):
        self.xPlotVals = self.xPlotVals[1:]
        self.xPlotVals.append(time.time() - self.plotTimestamp)
        self.yPlotVals = self.yPlotVals[1:]
        self.yPlotVals.append(self.twin.fiber_dia)
        self.plotLine.setData(self.xPlotVals, self.yPlotVals, pen=self.plotPen)
        self.ui.graphWidget.setXRange(self.xPlotVals[-1]-100.0,self.xPlotVals[-1])

    def onFile(self):
        self.filepath = QtWidgets.QFileDialog.getExistingDirectory(
                            self, 'Datalog Save Folder')
        self.ui.filepathRead.setText(self.filepath)

    def onOutIntCh(self):
        try:
            self.outInterval = float(self.ui.broadcastPeriodSet.text())
            self.ui.broadcastPeriodSet.setText('{0:.3f}'.format(self.outInterval))
        except ValueError:
            pass

    def onProcIntCh(self):
        try:
            self.twin.interval = float(self.ui.processInterval.text())
            self.ui.processInterval.setText('{0:.3f}'.format(self.twin.interval))
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
            self.ctrl.htr_set_temp = float(self.ui.filamentHeatSet.text())
            self.ui.filamentHeatSet.setText('{0:.1f}'.format(self.ctrl.htr_set_temp))
        except ValueError:
            pass

    def onFeedCh(self):
        try:
            self.ctrl.feed_set_speed = float(self.ui.filamentFeedSet.text())
            self.ui.filamentFeedSet.setText('{0:.4f}'.format(self.ctrl.feed_set_speed))
        except ValueError:
            pass

    def onSpoolCh(self):
        try:
            self.ctrl.spool_set_speed = float(self.ui.spoolWindSet.text())
            self.ui.spoolWindSet.setText('{0:.3f}'.format(self.ctrl.spool_set_speed))
        except ValueError:
            pass

    def onFibCh(self):
        try:
            self.ctrl.fiber_set_dia = float(self.ui.filamentDiamSet.text())
            self.ui.filamentDiamSet.setText('{0:.3f}'.format(self.ctrl.fiber_set_dia))
        except ValueError:
            pass

    def onStart(self):
        self.ctrl.twin = self.twin
        # start logging
        if self.ui.dataLogCheck.isChecked():
            self.filename = ("log_" + self.ui.processModelSelect.currentText() + 
                             "_" + self.ui.ctrlOpts.currentText() + "_" + 
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
        self.ui.messageWindow.appendPlainText('Starting Model: ' + type(self.twin).__name__)
        self.twin.start()
        self.ui.messageWindow.appendPlainText('Starting Process Control: ' + type(self.ctrl).__name__)
        self.ctrl.start()
        self.update_timer.start(self.update_actual_interval)
        self.ui.startButton.setEnabled(False)
        self.ui.controlInterval.setEnabled(False)
        self.ui.processInterval.setEnabled(False)
        self.ui.broadcastPeriodSet.setEnabled(False)
        self.ui.processModelSelect.setEnabled(False)
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
        self.ui.messageWindow.appendPlainText('Stopping Model and Process Threads...')
        self.update_timer.stop()
        self.twin.is_running = False
        self.twin.join()
        self.ctrl.is_running = False
        self.ctrl.join()
        self.ui.messageWindow.appendPlainText('Simulation Complete.')
        # reassign threads
        # cleanup and refersh GUI
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.updateActuals)
        self.twin = process_models.BasicStateTwin()
        self.ctrl = control_models.ManualStateTwin()
        self.ui.processModelSelect.setCurrentIndex(0)
        self.updateModel()
        self.ui.startButton.setEnabled(True)
        self.ui.controlInterval.setEnabled(True)
        self.ui.processInterval.setEnabled(True)
        self.ui.broadcastPeriodSet.setEnabled(True)
        self.ui.processModelSelect.setEnabled(True)
        self.ui.ctrlOpts.setEnabled(True)
        self.ui.stopButton.setEnabled(False)
        self.ui.filepathSet.setEnabled(True)
        self.ui.broadcastPeriodSet.setEnabled(True)
        self.ui.filepathSet.setEnabled(True)
        self.ui.dataLogCheck.setEnabled(True)
        


    def updateModel(self):
        if (self.ui.processModelSelect.currentText() == 'Basic State Model'):
            self.twin = process_models.BasicStateTwin()
        elif (self.ui.processModelSelect.currentText() == 
              'Basic Dynamic Model'):
            self.twin = process_models.BasicDynamicTwin()
        self.ui.messageWindow.appendPlainText('Setting Model: ' +
           self.ui.processModelSelect.currentText())
        self.updateControlOpts()

    def updateControlOpts(self):
        self.ui.ctrlOpts.clear()
        if (self.ui.processModelSelect.currentText() == 'Basic State Model'):
            self.ui.ctrlOpts.addItems(['Manual Control',
                                       'Manual Control, Set Fiber Diameter'])
            self.ui.ctrlOpts.setCurrentIndex(0)
        elif (self.ui.processModelSelect.currentText() == 
              'Basic Dynamic Model'):
            self.ui.ctrlOpts.addItems(['Manual Speed Control, Set Heater Temperature',
                                       'Basic PID Control'])
            self.ui.ctrlOpts.setCurrentIndex(0)
        #self.updateControl()

    def updateControl(self):
        if (self.ui.ctrlOpts.currentText() == 'Manual Control'):
            self.ctrl = control_models.ManualStateTwin()
            self.ui.filamentHeatSet.setEnabled(True)
            self.ui.filamentFeedSet.setEnabled(True)
            self.ui.spoolWindSet.setEnabled(True)
            self.ui.filamentDiamSet.setEnabled(False)
        elif (self.ui.ctrlOpts.currentText() == 'Manual Control, Set Fiber Diameter'):
            self.ctrl = control_models.CalcDiaStateTwin()
            self.ui.filamentHeatSet.setEnabled(True)
            self.ui.filamentFeedSet.setEnabled(True)
            self.ui.spoolWindSet.setEnabled(False)
            self.ui.filamentDiamSet.setEnabled(True)
        elif (self.ui.ctrlOpts.currentText() == 'Manual Speed Control, Set Heater Temperature'):
            self.ctrl = control_models.ManualPIDDynamicTwin()
            self.ui.filamentHeatSet.setEnabled(True)
            self.ui.filamentFeedSet.setEnabled(True)
            self.ui.spoolWindSet.setEnabled(True)
            self.ui.filamentDiamSet.setEnabled(False)
        elif (self.ui.ctrlOpts.currentText() == 'Basic PID Control'):
            self.ctrl = control_models.BasicPIDDynamicTwin()
            self.ui.filamentHeatSet.setEnabled(True)
            self.ui.filamentFeedSet.setEnabled(True)
            self.ui.spoolWindSet.setEnabled(False)
            self.ui.filamentDiamSet.setEnabled(True)
        self.ui.filamentHeatSet.setText('{0:.1f}'.format(self.ctrl.htr_set_temp))
        self.ui.filamentFeedSet.setText('{0:.4f}'.format(self.ctrl.feed_set_speed))
        self.ui.spoolWindSet.setText('{0:.3f}'.format(self.ctrl.spool_set_speed))
        self.ui.filamentDiamSet.setText('{0:.3f}'.format(self.ctrl.fiber_set_dia))
        if (self.ui.ctrlOpts.currentIndex() != -1):
            self.ui.messageWindow.appendPlainText('Setting Process Control: ' +
                                    self.ui.ctrlOpts.currentText())

    def updateActuals(self):
        self.ui.filamentHeatAct.setText('{0:.1f}'.format(self.twin.htr_temp))
        self.ui.filamentFeedAct.setText('{0:.4f}'.format(self.twin.feed_speed))
        self.ui.spoolWindAct.setText('{0:.3f}'.format(self.twin.spool_speed))
        self.ui.filamentDiamAct.setText('{0:.3f}'.format(self.twin.fiber_dia))
        self.ui.filamentTotLen.setText('{0:.2f}'.format(self.twin.fiber_len/1000.0))
        self.ui.totPowerAct.setText('{0:.1f}'.format(self.twin.sys_power))

if __name__ == "__main__":  
    logging.basicConfig(level=logging.INFO)
    # below lines add scaling funcitnoality for high res screens
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication([])
    win = fredwin()
    win.show()
    sys.exit(app.exec())