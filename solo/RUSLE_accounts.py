'''
LUCI RUSLE accounts function
'''

import sys
import os
import configuration
import numpy as np
import arcpy
from arcpy.sa import *
import LUCI_SEEA.lib.log as log
import LUCI_SEEA.lib.common as common
from LUCI_SEEA.lib.external import six # Python 2/3 compatibility module
import LUCI_SEEA.solo.RUSLE as RUSLE

from LUCI_SEEA.lib.refresh_modules import refresh_modules
refresh_modules([log, common, RUSLE])

def function(outputFolder, yearAFolder, yearBFolder, lsOption, slopeAngle, rData, soilData, soilCode,
             YearALCData, YearALCCode, YearBLCData, YearBLCCode, YearAPData, YearBPData, saveFactors):

    try:
        # Set temporary variables
        prefix = os.path.join(arcpy.env.scratchGDB, "rusleAcc_")

        clipA = prefix + "clipA"
        clipB = prefix + "clipB"
        lossA = prefix + "lossA"
        lossB = prefix + "lossB"
        diffLoss = prefix + "diffLoss"
        diffNullZero = prefix + "diffNullZero"

        # Set output filenames
        soilLossA = os.path.join(outputFolder, "soillossA")
        soilLossB = os.path.join(outputFolder, "soillossB")
        soilLossDiff = os.path.join(outputFolder, "soillossDiff")

        # Set soil option for both years
        soilOption = 'LocalSoil'

        # Set LC option for both years
        lcOption = 'LocalCfactor'
        
        ################################
        ### Running RUSLE for Year A ###
        ################################

        log.info('*****************************')
        log.info('Running RUSLE tool for Year A')
        log.info('*****************************')

        filesA = common.getFilenames('preprocess', yearAFolder)
        studyMaskA = filesA.studyareamask

        # Call RUSLE function for Year A        
        soilLoss = RUSLE.function(outputFolder, yearAFolder, lsOption, slopeAngle,
                                  soilOption, soilData, soilCode,
                                  lcOption, YearALCData, YearALCCode,
                                  rData, saveFactors, YearAPData)
        
        arcpy.CopyRaster_management(soilLoss, soilLossA)

        # Delete intermediate files
        arcpy.Delete_management(soilLoss)

        ################################
        ### Running RUSLE for Year B ###
        ################################

        log.info('*****************************')
        log.info('Running RUSLE tool for Year B')
        log.info('*****************************')

        filesB = common.getFilenames('preprocess', yearBFolder)
        studyMaskB = filesB.studyareamask

        # Call RUSLE function for Year B
        soilLoss = RUSLE.function(outputFolder, yearBFolder, lsOption, slopeAngle,
                                  soilOption, soilData, soilCode,
                                  lcOption, YearBLCData, YearBLCCode,
                                  rData, saveFactors, YearBPData)

        arcpy.CopyRaster_management(soilLoss, soilLossB)

        # Delete intermediate files
        arcpy.Delete_management(soilLoss)

        #######################################################
        ### Calculate differences between Year A and Year B ###
        #######################################################

        log.info('*************************************************')
        log.info('Calculating differences between Year A and Year B')
        log.info('*************************************************')

        # Copy soil loss layers to temporary files
        arcpy.CopyRaster_management(soilLossA, lossA)
        arcpy.CopyRaster_management(soilLossB, lossB)

        diffTemp = Raster(lossB) - Raster(lossA)
        diffTemp.save(diffLoss)
        del diffTemp

        log.info('Removing the areas of zero difference')
        diffNullTemp = SetNull(diffLoss, diffLoss, "VALUE = 0")
        diffNullTemp.save(diffNullZero)
        del diffNullTemp

        arcpy.CopyRaster_management(diffNullZero, soilLossDiff)

        log.info("RUSLE accounts function completed successfully")

    except Exception:
        arcpy.AddError("RUSLE accounts function failed")
        raise

    finally:
        # Remove feature layers from memory
        try:
            for lyr in common.listFeatureLayers(locals()):
                arcpy.Delete_management(locals()[lyr])
                exec(lyr + ' = None') in locals()
        except Exception:
            pass
