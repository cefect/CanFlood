# -*- coding: utf-8 -*-
"""
ui class for the MODEL toolset
"""

import os,  os.path, warnings, tempfile, logging, configparser, sys, time
from shutil import copyfile

from PyQt5 import uic, QtWidgets


from PyQt5.QtCore import QSettings, QTranslator, QCoreApplication, QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QFileDialog, QListWidget

# Initialize Qt resources from file resources.py
#from .resources import *
# Import the code for the dialog



# User defined imports
from qgis.core import *
from qgis.analysis import *
import qgis.utils
import processing
from processing.core.Processing import Processing



import numpy as np
import pandas as pd



#==============================================================================
# custom imports 
#==============================================================================
from model.risk1 import Risk1
from model.risk2 import Risk2
from model.dmg2 import Dmg2

import results.djoin


import hlpr.plug
from hlpr.basic import *


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
ui_fp = os.path.join(os.path.dirname(__file__), 'model.ui')
assert os.path.exists(ui_fp)
FORM_CLASS, _ = uic.loadUiType(ui_fp)


class Modelling_Dialog(QtWidgets.QDialog, FORM_CLASS,  
                       hlpr.plug.QprojPlug):
    
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(Modelling_Dialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        

        self.iface = iface
        
        self.qproj_setup()
        
        self.connect_slots()
        
    def connect_slots(self):
        """connect ui slots to functions"""
        #======================================================================
        # general----------------
        #======================================================================
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        
        #connect to status label
        self.logger.statusQlab=self.progressText
        self.logger.statusQlab.setText('BuildDialog initialized')
        
        #======================================================================
        # setup-----------
        #======================================================================
        #control file
        def cf_browse():
            return self.browse_button(self.lineEdit_cf_fp, 
                                      prompt='Select Control File',
                                      qfd = QFileDialog.getOpenFileName)
            
        self.pushButton_cf.clicked.connect(cf_browse)
        
        #=======================================================================
        # #working directory
        #=======================================================================
        #browse button
        def wd_browse():
            return self.browse_button(self.lineEdit_wd, 
                                      prompt='Select Working Directory',
                                      qfd = QFileDialog.getExistingDirectory)
            
        self.pushButton_wd.clicked.connect(wd_browse)
        
        #open button
        def open_wd():
            wd = self.lineEdit_wd.text()
            if not os.path.exists(wd):
                os.makedirs(wd)
            force_open_dir(wd)
        
        self.pushButton_wd_open.clicked.connect(open_wd)
        

        #overwrite control
        self.checkBox_SSoverwrite.stateChanged.connect(self.set_overwrite)
        #=======================================================================
        # Join Geometry 
        #=======================================================================

        #vector geometry layer
        self.comboBox_JGfinv.setFilters(QgsMapLayerProxyModel.VectorLayer) 
        
        """not working"""
        self.comboBox_JGfinv.clear() #by default, lets have this be blank
        
        def upd_cid(): #change the 'cid' display when the finv selection changes
            return self.mfcb_connect(
                self.mFieldComboBox_JGfinv, self.comboBox_JGfinv.currentLayer(),
                fn_str = 'xid' )
        
        self.comboBox_JGfinv.layerChanged.connect(upd_cid)
        
        

        
        
        
        #======================================================================
        # risk level 1----------
        #======================================================================
        self.pushButton_r1Run.clicked.connect(self.run_risk1)
        
        #conditional check boxes
        def tog_jg(): #toggle thte join_geo option
            
            
            pstate = self.checkBox_r2rpa_2.isChecked()
            #if checked, enable the second box
            self.checkBox_r2ires_2.setDisabled(np.invert(pstate))
            self.checkBox_r2ires_2.setChecked(False) #clear the check
            
        self.checkBox_r2rpa_2.stateChanged.connect(tog_jg)
        
        #======================================================================
        # impacts level 2
        #======================================================================
        self.pushButton_i2run.clicked.connect(self.run_impact2)
        
        #======================================================================
        # risk level 2
        #======================================================================
        self.pushButton_r2Run.clicked.connect(self.run_risk2)
        
        #conditional check boxes
        def tog_jg2(): #toggle thte join_geo option
            
            
            pstate = self.checkBox_r2rpa.isChecked()
            #if checked, enable the second box
            self.checkBox_r2ires.setDisabled(np.invert(pstate))
            self.checkBox_r2ires.setChecked(False) #clear the check
            
        self.checkBox_r2rpa.stateChanged.connect(tog_jg2)
        
        #======================================================================
        # risk level 3
        #======================================================================
        self.pushButton_r3Run.clicked.connect(self.run_risk3)
        
        
        def r3_browse():
            return self.browse_button(self.lineEdit_r3cf, 
                                      prompt='Select SOFDA Control File',
                                      qfd = QFileDialog.getOpenFileName)
            
        
        self.pushButton_r3.clicked.connect(r3_browse)
        

        
        self.logger.info('Model ui connected')
        
        #======================================================================
        # dev
        #======================================================================
        """"
        to speed up testing.. manually configure the project
        """
        
        debug_dir =os.path.join(os.path.expanduser('~'), 'CanFlood', 'model')
        self.lineEdit_cf_fp.setText(os.path.join(debug_dir, 'CanFlood_scenario1.txt'))
        self.lineEdit_wd.setText(debug_dir)
        

        
        
        
    def select_output_folder(self):
        foldername = QFileDialog.getExistingDirectory(self, "Select Directory")
        print(foldername)
        if foldername is not "":
            self.lineEdit_wd.setText(os.path.normpath(foldername))
            self.lineEdit_wd_2.setText(os.path.normpath(foldername)) #i2. bar
            self.lineEdit_cf_1.setText(os.path.normpath(os.path.join(foldername, 'CanFlood_control_01.txt'))) #r1. browse
            self.lineEdit_cf_2.setText(os.path.normpath(os.path.join(foldername, 'CanFlood_control_01.txt')))
    
    def select_output_file(self):
        filename = QFileDialog.getOpenFileName(self, "Select File") 
        self.lineEdit_cf_1.setText(str(filename[0])) #r1. browse
        self.lineEdit_cf_2.setText(str(filename[0]))
        
    def set_run_pars(self): #setting generic parmaeters for a run
        self.wd= self.get_wd()
        self.cf_fp = self.get_cf_fp()
        self.tag = self.linEdit_Stag.text()
        
    #==========================================================================
    # run commands
    #==========================================================================
    def run_risk1(self):
        """
        risk T1 runner
        """
        #=======================================================================
        # variables
        #=======================================================================
        log = self.logger.getChild('run_risk1')
        cf_fp = self.get_cf_fp()
        out_dir = self.get_wd()
        tag = self.linEdit_Stag.text()
        res_per_asset = self.checkBox_r2rpa_2.isChecked()

        #=======================================================================
        # setup/execute
        #=======================================================================
        model = Risk1(cf_fp, out_dir=out_dir, logger=self.logger, tag=tag,
                      feedback=self.feedback).setup()
        
        res, res_df = model.run(res_per_asset=res_per_asset)
        
        log.info('user pressed RunRisk1')
        #======================================================================
        # plot
        #======================================================================
        if self.checkBox_r2ep_2.isChecked():
            fig = model.risk_plot()
            _ = model.output_fig(fig)
            
        
        #==========================================================================
        # output
        #==========================================================================
        out_fp = model.output_df(res, '%s_%s'%(model.resname, 'ttl'))
        
        out_fp2 = None
        if not res_df is None:
            out_fp2 = model.output_df(res_df, '%s_%s'%(model.resname, 'passet'))
            
        self.logger.push('Risk1 Complete')
        self.feedback.upd_prog(None) #set the progress bar back down to zero
        
        #=======================================================================
        # links
        #=======================================================================
        if self.checkBox_r2ires_2.isChecked():
            assert os.path.exists(out_fp2), 'need to generate results per asset'
            self.results_joinGeo(out_fp2, out_dir, tag)
        

            
        return
        
    def run_impact2(self):
        log = self.logger.getChild('run_impact2')
        cf_fp = self.get_cf_fp()
        out_dir = self.get_wd()
        tag = self.linEdit_Stag.text()

        #======================================================================
        # #build/run model
        #======================================================================
        model = Dmg2(cf_fp, out_dir = out_dir, logger = self.logger, tag=tag,
                     feedback=self.feedback).setup()
        
        #run the model        
        cres_df = model.run()
        

        #======================================================================
        # save reuslts
        #======================================================================
        out_fp = model.output_df(cres_df, model.resname)
        
        #update parameter file
        model.upd_cf()

        self.logger.push('Impacts2 complete')
        self.feedback.upd_prog(None) #set the progress bar back down to zero
        
        #======================================================================
        # links
        #======================================================================
        
        if self.checkBox_i2RunRisk.isChecked():
            self.logger.info('linking in Risk 2')
            self.run_risk2()
            
        
    
    def run_risk2(self):
        #======================================================================
        # get run vars
        #======================================================================
        log = self.logger.getChild('run_risk2')
        start = time.time()
        cf_fp = self.get_cf_fp()
        out_dir = self.get_wd()
        tag = self.linEdit_Stag.text()
        res_per_asset = self.checkBox_r2rpa.isChecked()
        

        #======================================================================
        # run the model
        #======================================================================
        model = Risk2(cf_fp, out_dir=out_dir, logger=self.logger, tag=tag,
                      feedback=self.feedback)._setup()
        
        res_ser, res_df = model.run(res_per_asset=res_per_asset)
        
        #======================================================================
        # plot
        #======================================================================
        if self.checkBox_r2plot.isChecked():
            fig = model.risk_plot()
            _ = model.output_fig(fig)
       
        #=======================================================================
        # output
        #=======================================================================
        model.output_df(res_ser, '%s_%s'%(model.resname, 'ttl'))
        
        out_fp2=''
        if not res_df is None:
            out_fp2= model.output_df(res_df, '%s_%s'%(model.resname, 'passet'))
        
        
        tdelta = (time.time()-start)/60.0
        self.logger.push('Risk2 complete in %.4f mins'%tdelta)
        self.feedback.upd_prog(None) #set the progress bar back down to zero
        #======================================================================
        # links
        #======================================================================
        if self.checkBox_r2ires.isChecked():
            assert os.path.exists(out_fp2), 'need to generate results per asset'
            self.results_joinGeo(out_fp2, out_dir, tag)


        return

        
    def run_risk3(self):
        raise Error('not implemented')
    
        self.feedback.upd_prog(None) #set the progress bar back down to zero
        
    def results_joinGeo(self, data_fp, wd, tag):
        """
        not a good way to have the user specify the 
        
        helper to execute results joiner
        
        passing all values exliclpity to rely on assertion checks in caller
        """
        log = self.logger.getChild('results_joinGeo')
        #=======================================================================
        # collect inputs
        #=======================================================================
        geo_vlay = self.comboBox_JGfinv.currentLayer()
        cid = self.mFieldComboBox_JGfinv.currentField() #user selected field
        crs = self.qproj.crs()
        #=======================================================================
        # check inputs
        #=======================================================================
        assert isinstance(geo_vlay, QgsVectorLayer), \
            'need to specify a geometry layer on the \'Setup\' tab to join results to'
            
        assert isinstance(crs, QgsCoordinateReferenceSystem)
        assert crs.isValid()
        
        #check cid
        assert isinstance(cid, str), 'bad index FieldName passed'
        if cid == '' or cid in self.invalid_cids:
            raise Error('user selected index FieldName \'%s\''%cid)
        
        assert cid in [field.name() for field in geo_vlay.fields()] 
        
        assert os.path.exists(data_fp), 'invalid data_fp'
        
        #=======================================================================
        # execute
        #=======================================================================
        #setup
        wrkr = results.djoin.Djoiner(logger=self.logger, 
                                     tag = tag,
                                     feedback=self.feedback,
                                     cid=cid, crs=crs,
                                     out_dir=wd)
        #execute
        res_vlay = wrkr.run(geo_vlay, data_fp, cid,
                 keep_fnl='all', #todo: setup a dialog to allow user to select any of the fields
                 )
        
        self.qproj.addMapLayer(res_vlay)
        
        #=======================================================================
        # wrap
        #=======================================================================

        
        self.feedback.upd_prog(None)
        log.push('run_joinGeo finished')
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        