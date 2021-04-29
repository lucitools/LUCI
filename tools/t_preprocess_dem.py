'''
t_baseline.py generates the hydrological and topographical models, and the land use/soil scenario information
which are used as input to LUCI functions.

Multiple Arc tools use this script with different numbers of input parameters.
These different versions are specified by the "Tool level" parameter, which can have the values
"core" and "rav".
'''

import arcpy
import os
import sys
import traceback
import configuration

import LUCI_SEEA.lib.log as log
import LUCI_SEEA.lib.progress as progress
import LUCI_SEEA.lib.common as common
import LUCI_SEEA.lib.baseline as baseline
import LUCI_SEEA.solo.preprocess_dem as preprocess_dem

from LUCI_SEEA.lib.refresh_modules import refresh_modules
from LUCI_SEEA.lib.external import six # Python 2/3 compatibility module
refresh_modules([log, common, baseline, preprocess_dem])

def function(params):

    try:
        ###################
        ### Read inputs ###
        ###################

        pText = common.paramsAsText(params)

        outputFolder = pText[1]        
        inputDEM = common.fullPath(pText[2])
        inputStudyAreaMask = pText[3]
        inputLC = pText[4]
        lcCode = pText[5]
        inputSoil = pText[6]
        soilCode = pText[7]
        reconDEM = common.strToBool(pText[8])
        inputStreamNetwork = pText[9]
        streamAccThresh = pText[10]
        riverAccThresh = pText[11]
        smoothDropBuffer = pText[12]
        smoothDrop = pText[13]
        streamDrop = pText[14]
        rerun = common.strToBool(pText[15])

        log.info('Inputs read in')

        ###########################
        ### Tool initialisation ###
        ###########################

        # Create Baseline folder
        if not os.path.exists(outputFolder):
            os.mkdir(outputFolder)

        # Set up logging output to file
        log.setupLogging(outputFolder)

        # Run system checks
        common.runSystemChecks(outputFolder, rerun)

        # Set up progress log file
        progress.initProgress(outputFolder, rerun)

        # Write input params to XML
        common.writeParamsToXML(params, outputFolder, 'PreprocessDEM')

        log.info('Tool initialised')

        ########################
        ### Define filenames ###
        ########################

        files = common.getFilenames('preprocess', outputFolder)
        studyAreaMask = files.studyareamask
        outputLCras = files.lc_ras
        outputLCvec = files.lc_vec
        outputSoilras = files.soil_ras
        outputSoilvec = files.soil_vec

        ###############################
        ### Set temporary variables ###
        ###############################

        prefix = os.path.join(arcpy.env.scratchGDB, 'base_')

        DEMTemp = prefix + 'DEMTemp'
        clippedDEM = prefix + 'clippedDEM'
        clippedLC = prefix + 'clippedLC'
        clippedSoil = prefix + 'clippedSoil'
        clippedStreamNetwork = prefix + 'clippedStreamNetwork'

        studyAreaMaskTemp = prefix + "studyAreaMaskTemp"
        studyAreaMaskBuff = prefix + "studyAreaMaskBuff"
        studyAreaMaskDiss = prefix + "studyAreaMaskDiss"

        log.info('Temporary variables set')

        # Check formats of inputs
        lcFormat = arcpy.Describe(inputLC).dataType
        soilFormat = arcpy.Describe(inputSoil).dataType

        ###################
        ### Data checks ###
        ###################
        
        codeBlock = 'Data checks 1'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            inputFiles = [inputDEM, inputStudyAreaMask, inputLC, inputSoil]
            if inputStreamNetwork is not None:
                inputFiles.append(inputStreamNetwork)

            for file in inputFiles:
                common.checkSpatialRef(file)

            # Set environment variables
            arcpy.env.snapRaster = inputDEM
            arcpy.env.cellSize = inputDEM
            arcpy.env.compression = "None"

            cellsizedem = float(arcpy.GetRasterProperties_management(inputDEM, "CELLSIZEX").getOutput(0))

            # Get spatial references of DEM and study area mask
            DEMSpatRef = arcpy.Describe(inputDEM).SpatialReference
            maskSpatRef = arcpy.Describe(inputStudyAreaMask).SpatialReference

            # Reproject study area mask if it does not have the same coordinate system as the DEM
            if not common.equalProjections(DEMSpatRef, maskSpatRef):

                warning = "Study area mask does not have the same coordinate system as the DEM"
                log.warning(warning)
                common.logWarnings(outputFolder, warning)

                warning = "Mask coordinate system is " + maskSpatRef.Name + " while DEM coordinate system is " + DEMSpatRef.Name
                log.warning(warning)
                common.logWarnings(outputFolder, warning)

                warning = "Reprojecting study area mask to DEM coordinate system"
                log.warning(warning)
                common.logWarnings(outputFolder, warning)

                arcpy.Project_management(inputStudyAreaMask, studyAreaMaskTemp, DEMSpatRef)
                arcpy.CopyFeatures_management(studyAreaMaskTemp, studyAreaMask)
            else:
                arcpy.CopyFeatures_management(inputStudyAreaMask, studyAreaMask)

            # If DEM is large, clip it to a large buffer around the study area mask (~5km)
            inputDEM = baseline.clipLargeDEM(inputDEM, studyAreaMask)

            rasterInputFiles = []
            fcInputFiles = []

            # Sort land cover and soil into appropriate arrays based on data type
            if lcFormat in ['RasterDataset', 'RasterLayer']:
                rasterInputFiles.append(inputLC)
                outputLC = os.path.join(outputFolder, 'landcover')

            elif lcFormat in ['ShapeFile', 'FeatureClass']:
                fcInputFiles.append(inputLC)
                outputLC = os.path.join(outputFolder, 'landcover.shp')

            if soilFormat in ['RasterDataset', 'RasterLayer']:
                rasterInputFiles.append(inputSoil)
                outputSoil = os.path.join(outputFolder, 'soil')

            elif soilFormat in ['ShapeFile', 'FeatureClass']:
                fcInputFiles.append(inputSoil)
                outputSoil = os.path.join(outputFolder, 'soil.shp')

            if reconDEM is True and inputStreamNetwork is None:
                log.error('Cannot recondition the DEM without an input stream network')
                log.error('Please provide an input stream network')
                sys.exit()

            # If the user has provided a stream network, add it to the list of inputs to check
            if inputStreamNetwork is not None:
                fcInputFiles.append(inputStreamNetwork)

            # Check that the inputs contain data
            for ras in rasterInputFiles:
                if ras is not None:

                    # Check file size
                    fileSizeGB = baseline.checkRasterSizeGB(ras)

                    if fileSizeGB < 1.0:
                        baseline.checkInputRaster(ras, outputFolder)

                    else:
                        log.warning("Cannot check if raster is empty or all NoData because it is too large")
                        log.warning("Please ensure this raster is not empty or all NoData: " + str(ras))

            for fc in fcInputFiles:
                if fc is not None:
                    baseline.checkInputFC(fc, outputFolder)

            # Check that the land cover and soil FCs have the linking codes specified by the user
            if lcFormat in ['ShapeFile', 'FeatureClass']:
                if len(arcpy.ListFields(inputLC, lcCode)) != 1:
                    log.error('Field ' + lcCode + 'does not exist in feature class ' + inputLC)
                    sys.exit()

            if soilFormat in ['ShapeFile', 'FeatureClass']:
                if len(arcpy.ListFields(inputSoil, soilCode)) != 1:
                    log.error('Field ' + soilCode + 'does not exist in feature class ' + inputSoil)
                    sys.exit()

            progress.logProgress(codeBlock, outputFolder)

        ###############################
        ### Tidy up study area mask ###
        ###############################

        codeBlock = 'Tidy up study area mask'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            # Check how many polygons are in the mask shapefile
            numPolysInMask = int(arcpy.GetCount_management(studyAreaMask).getOutput(0))
            if numPolysInMask > 1:

                # Reduce multiple features where possible
                arcpy.Union_analysis(studyAreaMask, studyAreaMaskDiss, "ONLY_FID", "", "NO_GAPS")
                arcpy.Dissolve_management(studyAreaMaskDiss, studyAreaMask, "", "", "SINGLE_PART", "DISSOLVE_LINES")

            # Buffer study area mask
            baseline.bufferMask(inputDEM, studyAreaMask, outputStudyAreaMaskBuff=studyAreaMaskBuff)
            log.info('Study area mask buffered')

            progress.logProgress(codeBlock, outputFolder)
        
        #######################
        ### Clip input data ###
        #######################

        codeBlock = 'Clip inputs'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            baseline.clipInputs(outputFolder,
                                studyAreaMaskBuff,
                                inputDEM,
                                inputLC,
                                inputSoil,
                                inputStreamNetwork,
                                outputDEM=clippedDEM,
                                outputLC=clippedLC,
                                outputSoil=clippedSoil,
                                outputStream=clippedStreamNetwork)

            progress.logProgress(codeBlock, outputFolder)

        ##############################################
        ### Coverage checks on soil and land cover ###
        ##############################################

        codeBlock = 'Do coverage checks on clipped land cover and soil'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            # Do coverage checks on land cover and soil and copy to outputFolder
            if lcFormat in ['RasterDataset', 'RasterLayer']:

                lcMask = common.extractRasterMask(clippedLC)
                common.checkCoverage(lcMask, studyAreaMaskBuff, inputLC)                

                arcpy.CopyRaster_management(clippedLC, outputLCras)

            elif lcFormat in ['ShapeFile', 'FeatureClass']:
                lcMask = common.dissolvePolygon(clippedLC)
                common.checkCoverage(lcMask, studyAreaMaskBuff, inputLC)

                arcpy.CopyFeatures_management(clippedLC, outputLCvec)

            if soilFormat in ['RasterDataset', 'RasterLayer']:

                soilMask = common.extractRasterMask(clippedSoil)
                common.checkCoverage(soilMask, studyAreaMaskBuff, inputLC)

                arcpy.CopyRaster_management(clippedSoil, outputSoilras)

            elif soilFormat in ['ShapeFile', 'FeatureClass']:

                soilMask = common.dissolvePolygon(clippedSoil)
                common.checkCoverage(soilMask, studyAreaMaskBuff, inputSoil)

                arcpy.CopyFeatures_management(clippedSoil, outputSoilvec)

            progress.logProgress(codeBlock, outputFolder)

        ######################################
        ### Convert LC and soil to rasters ###
        ######################################

        # For the RUSLE tool, the LC and soil must be in raster format

        codeBlock = 'Convert land cover and soil to rasters'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            if lcFormat in ['ShapeFile', 'FeatureClass']:
                arcpy.PolygonToRaster_conversion(clippedLC, lcCode, outputLCras, "CELL_CENTER", "", cellsizedem)
                log.info('Land cover raster produced')

            if soilFormat in ['ShapeFile', 'FeatureClass']:
                arcpy.PolygonToRaster_conversion(clippedSoil, soilCode, outputSoilras, "CELL_CENTER", "", cellsizedem)
                log.info('Soil raster produced')

            # Delete intermediate files
            arcpy.Delete_management(clippedLC)
            arcpy.Delete_management(clippedSoil)

            progress.logProgress(codeBlock, outputFolder)

        ###########################
        ### Run HydTopo process ###
        ###########################

        log.info("*** Preprocessing DEM ***")
        preprocess_dem.function(outputFolder,
                                clippedDEM,
                                studyAreaMask,
                                clippedStreamNetwork,
                                streamAccThresh,
                                riverAccThresh,
                                smoothDropBuffer,
                                smoothDrop,
                                streamDrop,
                                reconDEM,
                                rerun)

    except Exception:
        arcpy.SetParameter(0, False)
        log.exception("Preprocessing DEM functions did not complete")
        raise
