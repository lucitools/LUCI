# -*- coding: utf-8 -*-
import arcpy
import os
import sys

import configuration
try:
    reload(configuration)  # Python 2.7
except NameError:
    try:
        import importlib # Python 3.4
        importlib.reload(configuration)
    except Exception:
    	arcpy.AddError('Could not load configuration module')
    	sys.exit()

# Load and refresh the refresh_modules module
from LUCI_SEEA.lib.external.six.moves import reload_module
import LUCI_SEEA.lib.refresh_modules as refresh_modules
reload_module(refresh_modules)
from LUCI_SEEA.lib.refresh_modules import refresh_modules

import LUCI_SEEA.lib.input_validation as input_validation
refresh_modules(input_validation)

############################################
### Aggregation and disaggregation tools ###
############################################

# Create data aggregation grid
import LUCI_SEEA.tool_classes.c_CreateDataAggregationGrid as c_CreateDataAggregationGrid
refresh_modules(c_CreateDataAggregationGrid)
CreateDataAggregationGrid = c_CreateDataAggregationGrid.CreateDataAggregationGrid

# Aggregate data
import LUCI_SEEA.tool_classes.c_AggregateData as c_AggregateData
refresh_modules(c_AggregateData)
AggregateData = c_AggregateData.AggregateData

###################
### Other tools ###
###################

import LUCI_SEEA.tool_classes.c_PreprocessDEM as c_PreprocessDEM
refresh_modules(c_PreprocessDEM)
PreprocessDEM = c_PreprocessDEM.PreprocessDEM

import LUCI_SEEA.tool_classes.c_RUSLE as c_RUSLE
refresh_modules(c_RUSLE)
RUSLE = c_RUSLE.RUSLE

import LUCI_SEEA.tool_classes.c_RUSLEAccounts as c_RUSLEAccounts
refresh_modules(c_RUSLEAccounts)
RUSLEAccounts = c_RUSLEAccounts.RUSLEAccounts

import LUCI_SEEA.tool_classes.c_RUSLEAccScen as c_RUSLEAccScen
refresh_modules(c_RUSLEAccScen)
RUSLEAccScen = c_RUSLEAccScen.RUSLEAccScen

import LUCI_SEEA.tool_classes.c_LandAccounts as c_LandAccounts
refresh_modules(c_LandAccounts)
LandAccounts = c_LandAccounts.LandAccounts

import LUCI_SEEA.tool_classes.c_PAspeciesRichness as c_PAspeciesRichness
refresh_modules(c_PAspeciesRichness)
PAspeciesRichness = c_PAspeciesRichness.PAspeciesRichness

import LUCI_SEEA.tool_classes.c_ChangeUserSettings as c_ChangeUserSettings
refresh_modules(c_ChangeUserSettings)
ChangeUserSettings = c_ChangeUserSettings.ChangeUserSettings

import LUCI_SEEA.tool_classes.c_StatsZonal as c_StatsZonal
refresh_modules(c_StatsZonal)
StatsZonal = c_StatsZonal.CalculateZonal

import LUCI_SEEA.tool_classes.c_StatsExtent as c_StatsExtent
refresh_modules(c_StatsExtent)
StatsExtent = c_StatsExtent.CalculateExtent

##########################
### Toolbox definition ###
##########################

class Toolbox(object):

    def __init__(self):
        self.label = u'LUCI freely available'
        self.alias = u'LUCI'
        self.tools = [CreateDataAggregationGrid, AggregateData, RUSLE, RUSLEAccounts, RUSLEAccScen, LandAccounts, PAspeciesRichness, ChangeUserSettings, PreprocessDEM, StatsZonal, StatsExtent]
