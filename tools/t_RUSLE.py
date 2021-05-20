import arcpy
import os

import LUCI_SEEA.lib.log as log
import LUCI_SEEA.lib.common as common
import LUCI_SEEA.lib.progress as progress
import LUCI_SEEA.solo.RUSLE as RUSLE

from LUCI_SEEA.lib.refresh_modules import refresh_modules
refresh_modules([log, common, RUSLE])

def function(params):

    try:
        pText = common.paramsAsText(params)

        # Get inputs
        runSystemChecks = common.strToBool(pText[1])
        outputFolder = pText[2]
        preprocessFolder = pText[4]

        # R-factor
        rData = pText[5]

        # LS-factor
        slopeOption = pText[6]
        slopeAngle = pText[7]

        # K-factor
        kOption = pText[8]
        soilData = pText[9]
        soilCode = pText[10]

        # C-factor
        cOption = pText[11]
        landCoverData = pText[12]
        landCoverCode = pText[13]

        # P-factor
        supportData = pText[14]

        saveFactors = common.strToBool(pText[15])

        # Rerun parameter may not present when tool run as part of a batch run tool. If it is not, set rerun to False.
        try:
            rerun = common.strToBool(pText[16])
        except IndexError:
            rerun = False
        except Exception:
            raise

        # Create output folder
        if not os.path.exists(outputFolder):
            os.mkdir(outputFolder)

        # System checks and setup
        if runSystemChecks:
            common.runSystemChecks(outputFolder, rerun)

        # Set up logging output to file
        log.setupLogging(outputFolder)

        # Set up progress log file
        progress.initProgress(outputFolder, rerun)

        # Write input params to XML
        common.writeParamsToXML(params, outputFolder)

        # Set option for LS-factor
        if slopeOption == 'Calculate based on slope and length only':
            lsOption = 'SlopeLength'

        elif slopeOption == 'Include upslope contributing area':
            lsOption = 'UpslopeArea'

        else:
            log.error('Invalid LS-factor option')
            sys.exit()

        # Set soilOption for K-factor
        if kOption == 'Use preprocessed soil data':
            soilOption = 'PreprocessSoil'

        elif kOption == 'Use local K-factor dataset':
            soilOption = 'LocalSoil'

        else:
            log.error('Invalid soil erodibility option')
            sys.exit()

        # Set lcOption for C-factor
        if cOption == 'Use preprocessed land cover data':
            lcOption = 'PrerocessLC'

        elif cOption == 'Use local C-factor dataset':
            lcOption = 'LocalCfactor'

        else:
            log.error('Invalid C-factor option')
            sys.exit()

        # Call RUSLE function
        soilLoss = RUSLE.function(outputFolder, preprocessFolder, lsOption, slopeAngle, soilOption, soilData, soilCode,
                                  lcOption, landCoverData, landCoverCode, rData, saveFactors, supportData,
                                  rerun)

        # Set up filenames for display purposes
        soilLoss = os.path.join(outputFolder, "soilloss")

        arcpy.SetParameter(3, soilLoss)

        return soilLoss

        log.info("RUSLE operations completed successfully")

    except Exception:
        log.exception("RUSLE tool failed")
        raise
