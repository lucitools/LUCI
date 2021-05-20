import arcpy
import configuration
import os
from LUCI_SEEA.lib.refresh_modules import refresh_modules

class RUSLE(object):

    class ToolValidator:
        """Class for validating a tool's parameter values and controlling the behavior of the tool's dialog."""
    
        def __init__(self, parameters):
            """Setup the Geoprocessor and the list of tool parameters."""
            self.params = parameters
    
        def initializeParameters(self):
            """Refine the properties of a tool's parameters.
            This method is called when the tool is opened."""
            return
        
        def updateParameters(self):
            """Modify the values and properties of parameters before internal validation is performed.
            This method is called whenever a parameter has been changed."""
            return
    
        def updateMessages(self):
            """Modify the messages created by internal validation for each tool parameter.
            This method is called after internal validation."""

            import LUCI_SEEA.lib.input_validation as input_validation
            refresh_modules(input_validation)
            
            input_validation.checkFilePaths(self)
    
    def __init__(self):
        self.label = u'Calculate soil loss (RUSLE)'
        self.canRunInBackground = False
        self.category = '3 RUSLE tools'

    def getParameterInfo(self):

        params = []

        # 0 Output__Success
        param = arcpy.Parameter()
        param.name = u'Output__Success'
        param.displayName = u'Output: Success'
        param.parameterType = 'Derived'
        param.direction = 'Output'
        param.datatype = u'Boolean'
        params.append(param)

        # 1 Run_system_checks
        param = arcpy.Parameter()
        param.name = u'Run_system_checks'
        param.displayName = u'Run_system_checks'
        param.parameterType = 'Derived'
        param.direction = 'Output'
        param.datatype = u'Boolean'
        param.value = u'True'
        params.append(param)

        # 2 Output_folder
        param = arcpy.Parameter()
        param.name = u'Output_folder'
        param.displayName = u'Output folder'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'Folder'
        params.append(param)

        # 3 Output_Layer_Soil_Loss
        param = arcpy.Parameter()
        param.name = u'Output_Layer_Soil_Loss'
        param.displayName = u'Soil loss (tons/ha/yr)'
        param.parameterType = 'Derived'
        param.direction = 'Output'
        param.datatype = u'Raster Layer'
        param.symbology = os.path.join(configuration.displayPath, "soilloss.lyr")
        params.append(param)

        # 4 Preprocess_folder
        param = arcpy.Parameter()
        param.name = u'Preprocess_folder'
        param.displayName = u'Preprocessed data folder'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'Folder'
        params.append(param)

        # 5 Rainfall erosivity
        param = arcpy.Parameter()
        param.name = u'Rainfall_erosivity'
        param.displayName = u'R-factor: Rainfall erosivity dataset'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'Raster Layer'
        params.append(param)

        # 6 LS-factor option
        param = arcpy.Parameter()
        param.name = u'LS_option'
        param.displayName = u'LS-factor: Method option'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'String'
        param.value = u'Calculate based on slope and length only'
        param.filter.list = [u'Calculate based on slope and length only', u'Include upslope contributing area']
        params.append(param)

        # 7 LSfactor: cutoff slope angle
        param = arcpy.Parameter()
        param.name = u'LSfactor_cutoff_angle'
        param.displayName = u'LS-factor: Cutoff slope angle (degrees)'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'Double'
        param.value = u'26.6'
        params.append(param)

        # 8 K-factor option
        param = arcpy.Parameter()
        param.name = u'Kfactor_option'
        param.displayName = u'K-factor: Soil erodibility option'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'String'
        param.value = u'Use preprocessed soil data'
        param.filter.list = [u'Use preprocessed soil data', u'Use local K-factor dataset']
        params.append(param)

        # 9 Soils
        param = arcpy.Parameter()
        param.name = u'Soils'
        param.displayName = u'K-factor: Soil erodibility dataset'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = [u'Feature Class', u'Raster Layer']
        params.append(param)

        # 10 Soil_linking_code
        param = arcpy.Parameter()
        param.name = u'Soil_linking_code'
        param.displayName = u'K-factor: Soil linking code'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'String'        
        params.append(param)

        # 11 C-factor option
        param = arcpy.Parameter()
        param.name = u'Cfactor_option'
        param.displayName = u'C-factor: Land cover option'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'String'
        param.value = u'Use preprocessed land cover data'
        param.filter.list = [u'Use preprocessed land cover data', u'Use local C-factor dataset']
        params.append(param)

        # 12 Land_cover
        param = arcpy.Parameter()
        param.name = u'Land_cover'
        param.displayName = u'C-factor: Cover factor dataset'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = [u'Feature Class', u'Raster Layer']
        params.append(param)

        # 13 Land_cover_linking_code
        param = arcpy.Parameter()
        param.name = u'Land_cover_linking_code'
        param.displayName = u'C-factor: Land cover linking code'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'String'
        params.append(param)

        # 14 Pfactor_dataset
        param = arcpy.Parameter()
        param.name = u'Pfactor_dataset'
        param.displayName = u'P-factor: Support practice dataset'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = 'Raster Layer'
        params.append(param)

        # 15 Save_factor_layers
        param = arcpy.Parameter()
        param.name = u'Save_factor_layers'
        param.displayName = u'Save factor layers?'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'Boolean'
        param.value = u'False'
        params.append(param)

        # 16 Rerun_tool
        param = arcpy.Parameter()
        param.name = u'Rerun_tool'
        param.displayName = u'Rerun tool (will continue previous run from the point where any errors occurred)'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'Boolean'
        param.value = u'False'
        params.append(param)

        return params

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateParameters()

    def updateMessages(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateMessages()

    def execute(self, parameters, messages):

        import LUCI_SEEA.tools.t_RUSLE as t_RUSLE
        refresh_modules(t_RUSLE)

        t_RUSLE.function(parameters)
