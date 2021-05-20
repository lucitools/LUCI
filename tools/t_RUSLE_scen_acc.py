import arcpy
import os

import LUCI_SEEA.lib.log as log
import LUCI_SEEA.lib.common as common
import LUCI_SEEA.solo.RUSLE_scen_acc as RUSLE_scen_acc

from LUCI_SEEA.lib.refresh_modules import refresh_modules
refresh_modules([log, common, RUSLE_scen_acc])

def function(params):

    try:
        pText = common.paramsAsText(params)

        # Get inputs
        runSystemChecks = common.strToBool(pText[1])
        outputFolder = pText[5]
        yearAFolder = pText[6]
        yearBFolder = pText[7]
        slopeOption = pText[8]
        slopeAngle = pText[9]
        yearARain = pText[10]
        yearBRain = pText[11]
        yearASupport = pText[12]
        yearBSupport = pText[13]

        # Set option for LS-factor
        if slopeOption == 'Calculate based on slope and length only':
            lsOption = 'SlopeLength'

        elif slopeOption == 'Include upslope contributing area':
            lsOption = 'UpslopeArea'

        else:
            log.error('Invalid LS-factor option')
            sys.exit()
        
        # System checks and setup
        if runSystemChecks:
            common.runSystemChecks()

        # Create output folder
        if not os.path.exists(outputFolder):
            os.mkdir(outputFolder)

        # Set up logging output to file
        log.setupLogging(outputFolder)
        
        # Call RUSLE_scen_acc function
        RUSLE_scen_acc.function(outputFolder, yearAFolder, yearBFolder, lsOption, slopeAngle,
                                yearARain, yearBRain, yearASupport, yearBSupport)

        # Set up filenames for display purposes
        soilLossA = os.path.join(outputFolder, "soillossA")
        soilLossB = os.path.join(outputFolder, "soillossB")
        soilLossDiff = os.path.join(outputFolder, "soillossDiff")

        arcpy.SetParameter(2, soilLossA)
        arcpy.SetParameter(3, soilLossB)
        arcpy.SetParameter(4, soilLossDiff)

        log.info("RUSLE accounts operations completed successfully")

    except Exception:
        log.exception("RUSLE accounts tool failed")
        raise
