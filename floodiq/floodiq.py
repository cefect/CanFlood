# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FloodIQ
                                 A QGIS plugin
 This plugin contains various FloodIQ modules
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-02-06
        git sha              : $Format:%H$
        copyright            : (C) 2020 by Tony De Crescenzo
        email                : tony.decrescenzo@ibigroup.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog

from .floodiq_dialog import FloodIQDialog
import os.path
from qgis.core import QgsProject, Qgis, QgsVectorLayer, QgsRasterLayer, QgsFeatureRequest

# User defined imports
from qgis.core import *
from qgis.analysis import *
import qgis.utils
import processing
from processing.core.Processing import Processing
import sys, os, warnings, tempfile, logging

sys.path.append(r'C:\IBI\_QGIS_\QGIS 3.8\apps\Python37\Lib\site-packages')
#sys.path.append(os.path.join(sys.exec_prefix, 'Lib/site-packages'))
import numpy as np
import pandas as pd

file_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(file_dir)
#import model
#from risk import RiskModel

import model.risk
import model.dmg
import prep.wsamp
from hp import Error

#import logging, logging.config
#logcfg_file = r'C:\Users\tony.decrescenzo\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\floodiq\_pars\logger.conf'
#logger = logging.getLogger() #get the root logger
#logging.config.fileConfig(logcfg_file) #load the configuration file
#logger.info('root logger initiated and configured from file: %s'%(logcfg_file))

class FloodIQ:
    """QGIS Plugin Implementation."""
    
    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface

        self.sel_val = []
        self.ras = []
        self.ras_dict = {}
        self.vec = None
        self.outp = None
        self.fpath = None
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'FloodIQ_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&FloodIQ')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FloodIQ', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/floodiq/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'FloodIQ'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&FloodIQ'),
                action)
            self.iface.removeToolBarIcon(action)
    
    def get_exp(self):                
        #=======================================================================
        # calculate poly stats
        #=======================================================================
        self.vec = self.dlg.comboBox.currentLayer()
        self.ras = list(self.ras_dict.values())
        if (self.vec is None or len(self.ras) == 0 or self.outp is None):
            self.iface.messageBar().pushMessage("Input field missing",
                                                 level=Qgis.Critical, duration=10)
            return
        prep.wsamp.main_run(self.ras, self.vec, self.outp)
    
    def run_risk(self):                
        #=======================================================================
        # run risk model
        #=======================================================================
        #filename = self.dlg.lineEdit.text()
        model.risk.main_run()

    def run_damage(self):                
        #=======================================================================
        # run damage model
        #=======================================================================
        #filename = self.dlg.lineEdit.text()
        model.dmg.main_run()
    
    def select_output_file(self):
        foldername = QFileDialog.getExistingDirectory(self.dlg, "Select Directory")
        self.outp = foldername 
        self.dlg.lineEdit.setText(foldername)
    
    def add_ras(self):
        x = [str(self.dlg.listWidget.item(i).text()) for i in range(self.dlg.listWidget.count())]  
        if (self.dlg.comboBox_2.currentText()) not in x:
            self.dlg.listWidget.addItem(self.dlg.comboBox_2.currentText())
            self.ras_dict.update({ (self.dlg.comboBox_2.currentText()) : (self.dlg.comboBox_2.currentLayer()) })
        
    def clear_text_edit(self):
        if len(self.ras_dict) > 0:
            self.dlg.listWidget.clear()
            self.ras_dict = {}
    
    def remove_text_edit(self):
        if (self.dlg.listWidget.currentItem()) is not None:
            value = self.dlg.listWidget.currentItem().text()
            item = self.dlg.listWidget.takeItem(self.dlg.listWidget.currentRow())
            item = None
            for k in list(self.ras_dict):
                if k == value:
                    self.ras_dict.pop(value)

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False            
            self.dlg = FloodIQDialog()
            self.dlg.pushButton.clicked.connect(self.select_output_file)
            self.dlg.pushButton_2.clicked.connect(self.get_exp)
            self.dlg.pushButton_3.clicked.connect(self.run_risk)
            self.dlg.pushButton_4.clicked.connect(self.run_damage)
            self.dlg.pushButton_5.clicked.connect(self.clear_text_edit)
            self.dlg.pushButton_6.clicked.connect(self.remove_text_edit)
            self.dlg.comboBox_2.currentTextChanged.connect(self.add_ras)            
        
        # Fetch the currently loaded layers
        layers = self.iface.mapCanvas().layers()
        layers_vec = [layer for layer in layers if layer.type() == QgsMapLayer.VectorLayer]
        layers_ras = [layer for layer in layers if layer.type() == QgsMapLayer.RasterLayer]
        self.dlg.comboBox.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.dlg.comboBox_2.setFilters(QgsMapLayerProxyModel.RasterLayer)
        
        # Clear the contents of the comboBox from previous runs
        self.dlg.comboBox.clear()
        self.dlg.comboBox_2.clear()
        self.dlg.lineEdit.clear()
        
        # Populate the comboBox with names of all the loaded layers
        #self.dlg.comboBox.addItems([layer.name() for layer in layers_vec])
        #self.dlg.comboBox_2.addItems([layer.name() for layer in layers_ras])
        
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        
        if result:
            pass
