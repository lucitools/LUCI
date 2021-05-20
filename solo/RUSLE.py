'''
LUCI RUSLE function
'''

import sys
import os
import configuration
import numpy as np
import arcpy
import math
from arcpy.sa import Reclassify, RemapRange, RemapValue, Raster, Slope, Con, IsNull, Float, Power, Sin, SetNull, Lookup
import LUCI_SEEA.lib.log as log
import LUCI_SEEA.lib.progress as progress
import LUCI_SEEA.lib.common as common
from LUCI_SEEA.lib.external import six # Python 2/3 compatibility module

from LUCI_SEEA.lib.refresh_modules import refresh_modules
refresh_modules([log, common])

def function(outputFolder, preprocessFolder, lsOption, slopeAngle, soilOption, soilData, soilCode, lcOption, landCoverData, landCoverCode, rData, saveFactors, supportData, rerun=False):

    try:
        # Set temporary variables
        prefix = os.path.join(arcpy.env.scratchGDB, "rusle_")

        supportCopy = prefix + "supportCopy"
        soilResample = prefix + "soilResample"
        lcResample = prefix + "lcResample"
        rainResample = prefix + "rainResample"
        supportResample = prefix + "supportResample"        
        soilClip = prefix + "soilClip"
        landCoverClip = prefix + "landCoverClip"
        rainClip = prefix + "rainClip"
        supportClip = prefix + "supportClip"
        DEMSlopeCut = prefix + "DEMSlopeCut"
        DEMSlopeRad = prefix + "DEMSlopeRad"
        upslopeArea = prefix + "upslopeArea"
        soilJoin = prefix + "soilJoin"
        lcJoin = prefix + "lcJoin"
        rFactor = prefix + "rFactor"
        lsFactor = prefix + "lsFactor"
        kFactor = prefix + "kFactor"
        cFactor = prefix + "cFactor"
        pFactor = prefix + "pFactor"
        soilLossInt = prefix + "soilLossInt"
        landCoverRas = prefix + "landCoverRas"
        soilRas = prefix + "soilRas"
        dataMask = prefix + "dataMask"

        # Get input study area mask
        files = common.getFilenames('preprocess', preprocessFolder)
        studyMask = files.studyareamask
        inputLC = files.lc_ras
        inputSoil = files.soil_ras
        DEMSlopePerc = files.slopeRawPer
        DEMSlope = files.slopeHydDeg
        hydFAC = files.hydFAC
        rawDEM = files.rawDEM
        streamInvRas = files.streamInvRas

        # Set output filenames
        files = common.getFilenames('rusle', outputFolder)
        soilLoss = files.soilloss

        if saveFactors:
            # if RUSLE factor layers are to be saved

            rFactor = files.rFactor
            lsFactor = files.lsFactor
            kFactor = files.kFactor
            cFactor = files.cFactor
            pFactor = files.pFactor

        reconOpt = common.getInputValue(preprocessFolder, 'Recondition_DEM')

        ####################
        ### Check inputs ###
        ####################

        codeBlock = 'Check if new inputs are in a projected coordinate systems'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            inputs = [rData]

            optInputs = [soilData, landCoverData, supportData]
            for data in optInputs:
                if data is not None:
                    inputs.append(data)

            for data in inputs:
                spatialRef = arcpy.Describe(data).spatialReference

                if spatialRef.Type == "Geographic":
                    # If any of the inputs are not in a projected coordinate system, the tool exits with a warning
                    log.error('Data: ' + str(data))
                    log.error('This data has a Geographic Coordinate System. It must have a Projected Coordinate System.')
                    sys.exit()

            log.info('All new inputs are in a projected coordinate system, proceeding.')

            progress.logProgress(codeBlock, outputFolder)
        
        try:

            # Set environment and extents to DEM            
            RawDEM = Raster(rawDEM)

            arcpy.env.extent = RawDEM
            arcpy.env.mask = RawDEM
            arcpy.env.cellSize = RawDEM
            arcpy.env.compression = "None"

            cellsizedem = float(arcpy.GetRasterProperties_management(rawDEM, "CELLSIZEX").getOutput(0))

            log.info("Calculation extent set to DEM data extent")            

        except Exception:
            log.error("Environment and extent conditions not set correctly")
            raise

        codeBlock = 'Convert any vector inputs to raster'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            if landCoverData is not None:
                lcFormat = arcpy.Describe(landCoverData).dataType

                if lcFormat in ['ShapeFile', 'FeatureClass']:

                    arcpy.PolygonToRaster_conversion(landCoverData, landCoverCode, landCoverRas, "CELL_CENTER", "", cellsizedem)
                    log.info('Land cover raster produced')

                else:
                    arcpy.CopyRaster_management(landCoverData, landCoverRas)

            if soilData is not None:
                soilFormat = arcpy.Describe(soilData).dataType

                if soilFormat in ['ShapeFile', 'FeatureClass']:

                    arcpy.PolygonToRaster_conversion(soilData, soilCode, soilRas, "CELL_CENTER", "", cellsizedem)
                    log.info('Soil raster produced')

                else:
                    arcpy.CopyRaster_management(soilData, soilRas)

            progress.logProgress(codeBlock, outputFolder)

        codeBlock = 'Resample down to DEM cell size'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            # Resample down to DEM cell size
            log.info("Resampling inputs down to DEM cell size")

            resampledRainTemp = arcpy.sa.ApplyEnvironment(rData)
            resampledRainTemp.save(rainResample)
            del resampledRainTemp

            if soilData is not None: 
                resampledSoilTemp = arcpy.sa.ApplyEnvironment(soilRas)
                resampledSoilTemp.save(soilResample)
                del resampledSoilTemp

                # Delete soil raster
                arcpy.Delete_management(soilRas)

            if landCoverData is not None:
                resampledLCTemp = arcpy.sa.ApplyEnvironment(landCoverRas)
                resampledLCTemp.save(lcResample)
                del resampledLCTemp

                # Delete land cover raster
                arcpy.Delete_management(landCoverRas)

            if supportData is not None:

                arcpy.CopyRaster_management(supportData, supportCopy)                
                resampledPTemp = arcpy.sa.ApplyEnvironment(supportCopy)
                resampledPTemp.save(supportResample)
                del resampledPTemp

                # Delete support raster
                arcpy.Delete_management(supportCopy)

            log.info("Inputs resampled")

            progress.logProgress(codeBlock, outputFolder)

        codeBlock = 'Clip inputs'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            log.info("Clipping inputs")

            arcpy.Clip_management(rainResample, "#", rainClip, studyMask, clipping_geometry="ClippingGeometry")

            # Delete resampled R-factor
            arcpy.Delete_management(rainResample)

            if soilData is not None: 
                arcpy.Clip_management(soilResample, "#", soilClip, studyMask, clipping_geometry="ClippingGeometry")

                # Delete resampled soil
                arcpy.Delete_management(soilResample)

            if landCoverData is not None:
                arcpy.Clip_management(lcResample, "#", landCoverClip, studyMask, clipping_geometry="ClippingGeometry")

                # Delete resampled land cover
                arcpy.Delete_management(lcResample)

            if supportData is not None:
                arcpy.Clip_management(supportResample, "#", supportClip, studyMask, clipping_geometry="ClippingGeometry")

                # Delete resampled support data
                arcpy.Delete_management(supportResample)

            log.info("Inputs clipped")

            progress.logProgress(codeBlock, outputFolder)

        codeBlock = 'Check against study area mask'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            inputs = [rainClip]

            optInputs = [soilClip, landCoverClip, supportClip]
            for data in optInputs:
                if arcpy.Exists(data):
                    inputs.append(data)

            for data in inputs:
                dataMask = common.extractRasterMask(data)
                common.checkCoverage(dataMask, studyMask, data)
                del dataMask

            progress.logProgress(codeBlock, outputFolder)

        ####################################
        ### Rainfall factor calculations ###
        ####################################

        codeBlock = 'Produce R-factor layer'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            # Copy resampled raster
            arcpy.CopyRaster_management(rainClip, rFactor)

            # Delete clipped R-factor
            arcpy.Delete_management(rainClip)

            log.info("R-factor layer produced")

            progress.logProgress(codeBlock, outputFolder)

        ######################################################
        ### Slope length and steepness factor calculations ###
        ######################################################

        codeBlock = 'Produce LS-factor layer'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            # Calculate the threshold slope angle in percent
            lsFactorRad = float(slopeAngle) * (math.pi / 180.0)
            riseRun = math.tan(lsFactorRad)
            cutoffPercent = riseRun * 100.0
            
            if lsOption == 'SlopeLength':

                log.info("Calculating LS-factor based on slope length and steepness only")

                # Produce slope cutoff raster
                DEMSlopeCutTemp = Con(Raster(DEMSlopePerc) > float(cutoffPercent), float(cutoffPercent), Raster(DEMSlopePerc))
                DEMSlopeCutTemp.save(DEMSlopeCut)
                del DEMSlopeCutTemp

                # Calculate the parts of the LS-factor equation separately
                lsCalcA = (cellsizedem / 22.0) ** 0.5
                lsCalcB = 0.065 + (0.045 * Raster(DEMSlopeCut)) + (0.0065 * Power(Raster(DEMSlopeCut), 2.0))

                # Calculate the LS-factor
                lsOrigTemp = lsCalcA * lsCalcB
                lsOrigTemp.save(lsFactor)

                # Delete temporary files
                del lsCalcB
                del lsOrigTemp
                arcpy.Delete_management(DEMSlopeCut)

                log.info("LS-factor layer produced")

            elif lsOption == 'UpslopeArea':                

                if reconOpt == 'false':
                    log.error('Cannot calculate LS-factor including upslope contributing area on unreconditioned DEM')
                    log.error('Rerun the preprocessing tool to recondition the DEM')
                    sys.exit()

                log.info("Calculating LS-factor including upslope contributing area")

                # Produce slope cutoff raster
                DEMSlopeCutTemp = Con(Raster(DEMSlope) > float(slopeAngle), float(slopeAngle), Raster(DEMSlope))
                DEMSlopeCutTemp.save(DEMSlopeCut)
                del DEMSlopeCutTemp

                # Convert from degrees to radian
                DEMSlopeRadTemp = Raster(DEMSlopeCut) * 0.01745
                DEMSlopeRadTemp.save(DEMSlopeRad)
                del DEMSlopeRadTemp

                # Currently hardcoded, but should have them as options in future
                m = 0.5
                n = 1.2

                upslopeAreaTemp = Raster(hydFAC) * float(cellsizedem)
                upslopeAreaTemp.save(upslopeArea)
                del upslopeAreaTemp

                lsFactorTemp = (m + 1) * Power(Raster(upslopeArea) / 22.1, float(m)) * Power(Sin(Raster(DEMSlopeRad)) / 0.09, float(n))
                lsFactorTemp.save(lsFactor)
                del lsFactorTemp

                # Delete temporary files
                arcpy.Delete_management(DEMSlopeCut)
                arcpy.Delete_management(DEMSlopeRad)
                arcpy.Delete_management(upslopeArea)

                log.info("LS-factor layer produced")

            progress.logProgress(codeBlock, outputFolder)

        ################################
        ### Soil factor calculations ###
        ################################

        codeBlock = 'Produce K-factor layer'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):
        
            if soilOption == 'PreprocessSoil':

                # Use the soil from the preprocessFolder
                arcpy.CopyRaster_management(inputSoil, soilClip)

                kTable = os.path.join(configuration.tablesPath, "rusle_hwsd.dbf")
                arcpy.JoinField_management(soilClip, "VALUE", kTable, "MU_GLOBAL")
                arcpy.CopyRaster_management(soilClip, soilJoin)

                # Delete temporary files
                arcpy.Delete_management(soilClip)

                kOrigTemp = Lookup(soilJoin, "K_Stewart")
                kOrigTemp.save(kFactor)

                # Delete temporary files
                del kOrigTemp
                arcpy.Delete_management(soilJoin)

            elif soilOption == 'LocalSoil':

                # User input is their own K-factor dataset
                kOrigTemp = Raster(soilClip)
                kOrigTemp.save(kFactor)

                # Delete temporary files
                del kOrigTemp
                arcpy.Delete_management(soilClip)

            else:
                log.error('Invalid soil erodibility option')
                sys.exit()
            
            log.info("K-factor layer produced")

            progress.logProgress(codeBlock, outputFolder)

        #################################
        ### Cover factor calculations ###
        #################################

        codeBlock = 'Produce C-factor layer'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            if lcOption == 'PrerocessLC':

                # Use LC from the preprocess folder

                arcpy.CopyRaster_management(inputLC, landCoverClip)

                cTable = os.path.join(configuration.tablesPath, "rusle_esacci.dbf")

                arcpy.JoinField_management(landCoverClip, "VALUE", cTable, "LC_CODE")
                arcpy.CopyRaster_management(landCoverClip, lcJoin)

                arcpy.Delete_management(landCoverClip)

                cOrigTemp = Lookup(lcJoin, "CFACTOR")
                cOrigTemp.save(cFactor)

                # Delete temporary files
                del cOrigTemp                
                arcpy.Delete_management(lcJoin)

            elif lcOption == 'LocalCfactor':

                # User input is their own C-factor dataset

                cOrigTemp = Raster(landCoverClip)
                cOrigTemp.save(cFactor)

                # Delete temporary files
                del cOrigTemp
                arcpy.Delete_management(landCoverClip)

            else:
                log.error('Invalid C-factor option')
                sys.exit()

            log.info("C-factor layer produced")

            progress.logProgress(codeBlock, outputFolder)

        #####################################
        ### Support practice calculations ###
        #####################################

        codeBlock = 'Produce P-factor layer'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            if supportData is not None:
                arcpy.CopyRaster_management(supportClip, pFactor)
                log.info("P-factor layer produced")

                # Delete temporary files
                arcpy.Delete_management(supportClip)

            progress.logProgress(codeBlock, outputFolder)

        ##############################
        ### Soil loss calculations ###
        ##############################

        codeBlock = 'Produce soil loss layer'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            if supportData is not None:
                soilLossTemp = Raster(rFactor) * Raster(lsFactor) * Raster(kFactor) * Raster(cFactor) * Raster(pFactor)

            else:
                soilLossTemp = Raster(rFactor) * Raster(lsFactor) * Raster(kFactor) * Raster(cFactor)

            if lsOption == 'UpslopeArea':
                soilLossTemp = soilLossTemp * Raster(streamInvRas)
                soilLossTemp.save(soilLoss)

            else:           
                soilLossTemp.save(soilLoss)

            log.info("RUSLE function completed successfully")

            progress.logProgress(codeBlock, outputFolder)

        return soilLoss        

    except Exception:
        arcpy.AddError("RUSLE function failed")
        raise

    finally:
        # Remove feature layers from memory
        try:
            for lyr in common.listFeatureLayers(locals()):
                arcpy.Delete_management(locals()[lyr])
                exec(lyr + ' = None') in locals()
        except Exception:
            pass
