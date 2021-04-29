'''
Preprocessing tool for LUCI. Generates hydrographical and topographical files
for use in other LUCI functions.
'''
import arcpy
from arcpy.sa import Con, Int, IsNull, Reclassify, RemapRange, RemapValue, Raster, Fill, Float, Hillshade, BooleanXOr
from arcpy.sa import FlowAccumulation, FlowDirection, ApplyEnvironment, Sink, SnapPourPoint, SetNull, StreamOrder, Slope
import os
import traceback
import stat
import math
import configuration
import sys

import LUCI_SEEA.lib.progress as progress
import LUCI_SEEA.lib.log as log
import LUCI_SEEA.lib.common as common
import LUCI_SEEA.solo.reconditionDEM as reconditionDEM
import LUCI_SEEA.lib.baseline as baseline

from LUCI_SEEA.lib.refresh_modules import refresh_modules
refresh_modules([log, common, reconditionDEM, baseline])


def function(outputFolder, DEM, studyAreaMask, streamInput, minAccThresh, majAccThresh,
             smoothDropBuffer, smoothDrop, streamDrop, reconDEM, rerun=False):

    try:
        # Set environment variables
        arcpy.env.compression = "None"
        arcpy.env.snapRaster = DEM
        arcpy.env.extent = DEM
        arcpy.env.cellSize = arcpy.Describe(DEM).meanCellWidth

        ########################
        ### Define filenames ###
        ########################

        files = common.getFilenames('preprocess', outputFolder)        

        rawDEM = files.rawDEM
        hydDEM = files.hydDEM
        hydFDR = files.hydFDR
        hydFDRDegrees = files.hydFDRDegrees
        hydFAC = files.hydFAC
        streamInvRas = files.streamInvRas # Inverse stream raster - 0 for stream, 1 for no stream
        streams = files.streams
        streamDisplay = files.streamDisplay
        multRaster = files.multRaster
        hydFACInt = files.hydFACInt
        slopeRawDeg = files.slopeRawDeg
        slopeRawPer = files.slopeRawPer
        slopeHydDeg = files.slopeHydDeg
        slopeHydPer = files.slopeHydPer

        ###############################
        ### Set temporary variables ###
        ###############################

        prefix = os.path.join(arcpy.env.scratchGDB, "base_")

        cellSizeDEM = float(arcpy.env.cellSize)

        burnedDEM = prefix + "burnedDEM"
        streamAccHaFile = prefix + "streamAccHa"
        rawFDR = prefix + "rawFDR"        
        allPolygonSinks = prefix + "allPolygonSinks"
        DEMTemp = prefix + "DEMTemp"
        hydFACTemp = prefix + "hydFACTemp"

        # Saved as .tif as did not save as ESRI grid on server
        streamsRasterFile = os.path.join(arcpy.env.scratchFolder, "base_") + "StreamsRaster.tif"

        ###############################
        ### Save DEM to base folder ###
        ###############################

        codeBlock = 'Save DEM'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            # Save DEM to base folder as raw DEM with no compression
            pixelType = int(arcpy.GetRasterProperties_management(DEM, "VALUETYPE").getOutput(0))

            if pixelType == 9: # 32 bit float
                arcpy.CopyRaster_management(DEM, rawDEM, pixel_type="32_BIT_FLOAT")
            else:
                log.info("Converting DEM to 32 bit floating type")
                arcpy.CopyRaster_management(DEM, DEMTemp)
                arcpy.CopyRaster_management(Float(DEMTemp), rawDEM, pixel_type="32_BIT_FLOAT")

                # Delete temporary DEM
                arcpy.Delete_management(DEMTemp)

            # Calculate statistics for raw DEM
            arcpy.CalculateStatistics_management(rawDEM)

            progress.logProgress(codeBlock, outputFolder)

        ################################
        ### Create multiplier raster ###
        ################################

        codeBlock = 'Create multiplier raster'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            Reclassify(rawDEM, "Value", RemapRange([[-999999.9, 999999.9, 1]]), "NODATA").save(multRaster)
            progress.logProgress(codeBlock, outputFolder)
        
        codeBlock = 'Calculate slope in percent'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            intSlopeRawPer = Slope(rawDEM, "PERCENT_RISE")
            intSlopeRawPer.save(slopeRawPer)
            del intSlopeRawPer

            log.info('Slope calculated in percent')

            progress.logProgress(codeBlock, outputFolder)

        if reconDEM is True:

            #######################
            ### Burn in streams ###
            #######################

            codeBlock = 'Burn in streams'
            if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

                # Recondition DEM (burning stream network in using AGREE method)
                log.info("Burning streams into DEM.")
                reconditionDEM.function(rawDEM, streamInput, smoothDropBuffer, smoothDrop, streamDrop, burnedDEM)
                log.info("Completed stream network burn in to DEM")

                progress.logProgress(codeBlock, outputFolder)

            ##################
            ### Fill sinks ###
            ##################

            codeBlock = 'Fill sinks'
            if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

                Fill(burnedDEM).save(hydDEM)

                log.info("Sinks in DEM filled")
                progress.logProgress(codeBlock, outputFolder)

            ######################
            ### Flow direction ###
            ######################

            codeBlock = 'Flow direction'
            if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

                FlowDirection(hydDEM, "NORMAL").save(hydFDR)
                log.info("Flow Direction calculated")
                progress.logProgress(codeBlock, outputFolder)

            #################################
            ### Flow direction in degrees ###
            #################################

            codeBlock = 'Flow direction in degrees'
            if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

                # Save flow direction raster in degrees (for display purposes)
                degreeValues = RemapValue([[1, 90], [2, 135], [4, 180], [8, 225], [16, 270], [32, 315], [64, 0], [128, 45]])
                Reclassify(hydFDR, "Value", degreeValues, "NODATA").save(hydFDRDegrees)
                progress.logProgress(codeBlock, outputFolder)

            #########################
            ### Flow accumulation ###
            #########################

            codeBlock = 'Flow accumulation'
            if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

                hydFACTemp = FlowAccumulation(hydFDR, "", "FLOAT")
                hydFACTemp.save(hydFAC)
                arcpy.sa.Int(Raster(hydFAC)).save(hydFACInt) # integer version
                log.info("Flow Accumulation calculated")

                progress.logProgress(codeBlock, outputFolder)


            #######################
            ### Calculate slope ###
            #######################

            codeBlock = 'Calculate slope on burned DEM'
            if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

                intSlopeHydDeg = Slope(hydDEM, "DEGREE")
                intSlopeHydDeg.save(slopeHydDeg)
                del intSlopeHydDeg

                intSlopeHydPer = Slope(hydDEM, "PERCENT_RISE")
                intSlopeHydPer.save(slopeHydPer)
                del intSlopeHydPer

                log.info('Slope calculated')

                progress.logProgress(codeBlock, outputFolder)

            ##########################
            ### Create stream file ###
            ##########################

            codeBlock = 'Create stream file'
            if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):
                
                # Create accumulation in metres
                streamAccHaFileInt = hydFACTemp * cellSizeDEM * cellSizeDEM / 10000.0
                streamAccHaFileInt.save(streamAccHaFile)
                del streamAccHaFileInt

                # Check stream initiation threshold reached
                streamYes = float(arcpy.GetRasterProperties_management(streamAccHaFile, "MAXIMUM").getOutput(0))

                if streamYes > float(minAccThresh):

                    reclassifyRanges = RemapRange([[-1000000, float(minAccThresh), 1],
                                                   [float(minAccThresh), 9999999999, 0]])

                    outLUCIstream = Reclassify(streamAccHaFile, "VALUE", reclassifyRanges)
                    outLUCIstream.save(streamInvRas)
                    del outLUCIstream
                    log.info("Stream raster for input to LUCI created")

                    # Create stream file for display
                    reclassifyRanges = RemapRange([[0, float(minAccThresh), "NODATA"],
                                        [float(minAccThresh), float(majAccThresh), 1],
                                        [float(majAccThresh), 99999999999999, 2]])

                    streamsRaster = Reclassify(streamAccHaFile, "Value", reclassifyRanges, "NODATA")
                    streamOrderRaster = StreamOrder(streamsRaster, hydFDR, "STRAHLER")
                    streamsRaster.save(streamsRasterFile)

                    # Create two streams feature classes - one for analysis and one for display
                    arcpy.sa.StreamToFeature(streamOrderRaster, hydFDR, streams, 'NO_SIMPLIFY')
                    arcpy.sa.StreamToFeature(streamOrderRaster, hydFDR, streamDisplay, 'SIMPLIFY')

                    # Rename grid_code column to 'Strahler'
                    for streamFC in [streams, streamDisplay]:

                        arcpy.AddField_management(streamFC, "Strahler", "LONG")
                        arcpy.CalculateField_management(streamFC, "Strahler", "!GRID_CODE!", "PYTHON_9.3")
                        arcpy.DeleteField_management(streamFC, "GRID_CODE")

                    del streamsRaster
                    del streamOrderRaster

                    log.info("Stream files created")

                else:

                    warning = 'No streams initiated'
                    log.warning(warning)
                    common.logWarnings(outputFolder, warning)

                    # Create LUCIStream file from multiplier raster (i.e. all cells have value of 1 = no stream)
                    arcpy.CopyRaster_management(multRaster, streamInvRas)

                progress.logProgress(codeBlock, outputFolder)

        codeBlock = 'Clip data, build pyramids and generate statistics'
        if not progress.codeSuccessfullyRun(codeBlock, outputFolder, rerun):

            try:
                # Generate pyramids and stats
                arcpy.BuildPyramidsandStatistics_management(outputFolder, "", "", "", "")
                log.info("Pyramids and Statistics calculated for all LUCI topographical information rasters")

            except Exception:
                log.info("Warning - could not generate all raster statistics")

            progress.logProgress(codeBlock, outputFolder)

        # Reset snap raster
        arcpy.env.snapRaster = None
        
    except Exception:
        log.error("Error in preprocessing operations")
        raise
