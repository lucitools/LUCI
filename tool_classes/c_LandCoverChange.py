import arcpy
import configuration
import os
from LUCI.lib.refresh_modules import refresh_modules

class LandCoverChange(object):

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

            import LUCI.lib.input_validation as input_validation
            refresh_modules(input_validation)
            
            input_validation.checkFilePaths(self)
    
    def __init__(self):
        self.label = u'Land extent account tool'
        self.canRunInBackground = False

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

        # 3 Output_Land_Cover
        param = arcpy.Parameter()
        param.name = u'Output_Land_Cover'
        param.displayName = u'Land Cover Change'
        param.parameterType = 'Derived'
        param.direction = 'Output'
        param.datatype = u'Feature Class'
        param.symbology = os.path.join(configuration.displayPath, "RelativeChange.lyr")
        params.append(param)

        # 4 Land_cover_option
        param = arcpy.Parameter()
        param.name = u'Land_cover_option'
        param.displayName = u'Land cover input option'
        param.parameterType = 'Required'
        param.direction = 'Input'
        param.datatype = u'String'
        param.value = u'One shapefile with multiple fields'
        param.filter.list = [u'One shapefile with multiple fields', u'Two separate shapefiles']        
        params.append(param)

        # 5 Input_land_cover
        param = arcpy.Parameter()
        param.name = u'Input_land_cover'
        param.displayName = u'Land cover dataset: one file with multiple fields'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'Feature Class'
        params.append(param)

        # 6 Opening_land_cover
        param = arcpy.Parameter()
        param.name = u'Opening_land_cover'
        param.displayName = u'Land cover dataset: opening land cover shapefile'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'Feature Class'
        params.append(param)

        # 7 Closing_land_cover
        param = arcpy.Parameter()
        param.name = u'Closing_land_cover'
        param.displayName = u'Land cover dataset: closing land cover shapefile'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'Feature Class'
        params.append(param)

        # 8 Opening_field
        param = arcpy.Parameter()
        param.name = u'Opening_field'
        param.displayName = u'Opening year land cover field'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'String'
        params.append(param)

        # 9 Closing_field
        param = arcpy.Parameter()
        param.name = u'Closing_field'
        param.displayName = u'Closing year land cover field'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'String'
        params.append(param)

        # 10 Land_cover_table
        param = arcpy.Parameter()
        param.name = u'Land_cover_table'
        param.displayName = u'Land cover label table'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'Table'
        params.append(param)

        # 11 Land_cover_field
        param = arcpy.Parameter()
        param.name = u'Land_cover_field'
        param.displayName = u'Land cover linking field'
        param.parameterType = 'Optional'
        param.direction = 'Input'
        param.datatype = u'String'
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

        import LUCI.tools.t_landcoverchange as t_landcoverchange
        refresh_modules(t_landcoverchange)

        t_landcoverchange.function(parameters)
