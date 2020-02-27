import arcpy
from arcpy.sa import Reclassify, RemapRange
import os
import sys
import shutil
import datetime # For writing current date/time to inputs.xml
import time # For logging warnings that are very close together
import xml.etree.cElementTree as ET

from LUCI_SEEA.lib.external import six # Python 2/3 compatibility module
import configuration
import LUCI_SEEA.lib.log as log

from LUCI_SEEA.lib.refresh_modules import refresh_modules
refresh_modules([log])

def addlayer(doc, dataSource, symbologyLayerFile, trans_ratio, groupLayerName, visible=True, layerName='', suffix=''):

    # trans_ratio is transparency ratio, 0 = no transparancy
    # symbologyLayerFile is layer containing symbology for newly generated dataSource
    # dataSource is layer generated by LUCI

    try:
        # Python 2
        if six.PY2:

            mxd = arcpy.mapping.MapDocument(doc)
            df = mxd.activeDataFrame

            # Create new layer
            addLayer = arcpy.mapping.Layer(dataSource)

            # Save mxd file if not being run from within ArcGIS
            layers = arcpy.mapping.ListLayers(mxd, groupLayerName, df)
            if len(layers) == 0:
                mxd.save()

            # Find group layer in existing layers
            targetGroupLayer = arcpy.mapping.ListLayers(mxd, groupLayerName, df)[0]

            # Add layer to group
            arcpy.mapping.AddLayerToGroup(df, targetGroupLayer, addLayer, "TOP")

            # Set this new layer as the layer to update
            updateLayer = arcpy.mapping.ListLayers(mxd, "", df)[1]

            # Update symbology
            if len(symbologyLayerFile) > 2:
                sourceLayer = arcpy.mapping.Layer(symbologyLayerFile)
                arcpy.mapping.UpdateLayer(df, updateLayer, sourceLayer, True)
                del sourceLayer

            updateLayer.transparency = float(trans_ratio)

            if layerName != '':
                updateLayer.name = layerName

            if not visible:
                updateLayer.visible = False

            arcpy.RefreshTOC()
            
            if doc != "CURRENT":
                mxd.save()

            del mxd, df, addLayer

            return updateLayer

        # Python 3
        if six.PY3:

            p = arcpy.mp.ArcGISProject(doc)
            m = p.listMaps()[0]

            '''
            # Create new layer
            layerName = os.path.basename(dataSource)

            # If there is a '.' in the layerName, get everything beforehand
            layerName = layerName.split('.')[0]
            
            # Determine if dataSource is raster or feature class
            dataType = arcpy.Describe(dataSource).dataType

            if dataType in ['ShapeFile']:
                tmpLyr = arcpy.MakeFeatureLayer_management(dataSource, layerName + suffix).getOutput(0)

            if dataType in ['RasterDataset']:
                tmpLyr = arcpy.MakeRasterLayer_management(dataSource, layerName + suffix).getOutput(0)

            arcpy.AddMessage('layerName: ' + str(layerName))
            # dataLayer = m.listLayers(layerName)[0]
            '''

            old_lyr = m.addDataFromPath(dataSource)

            if symbologyLayerFile[-10:] == 'ludata.lyr':
                arcpy.AddMessage('LUDATA')
                symbologyLayerFile += 'x'
                
            arcpy.management.ApplySymbologyFromLayer(old_lyr, symbologyLayerFile)

            tempLayerFile = os.path.join(arcpy.env.scratchFolder, "templayer.lyr")
            tempLayerFileX = os.path.join(arcpy.env.scratchFolder, "templayer.lyrx")

            arcpy.SaveToLayerFile_management(old_lyr, tempLayerFile, "RELATIVE")
            new_lyr_file = arcpy.mp.LayerFile(tempLayerFileX)

            new_lyr = new_lyr_file.listLayers()[0]
            old_lyr_name = old_lyr.name
            new_lyr.updateConnectionProperties(new_lyr.connectionProperties, old_lyr.connectionProperties)
            new_lyr.name = old_lyr_name
            new_lyr.transparency = float(trans_ratio)

            new_lyr_file.save()

            m.insertLayer(old_lyr, new_lyr_file)
            m.removeLayer(old_lyr)



            '''
            # Find group layer in existing layers
            groupLayer = m.listLayers(groupLayerName)[0]

            # Add layer to group
            m.addLayerToGroup(groupLayer, new_lyr, "TOP")
            # m.addLayer(dataLayer, "TOP")

            m = p.listMaps()[0]

            # Remove ungrouped layer from table of contents
            for lyr in m.listLayers():
                arcpy.AddMessage(lyr.longName)
                if lyr.longName == old_lyr_name:
                    m.removeLayer(new_lyr)
                    arcpy.AddMessage('Removed above layer')
            '''
            '''
            arcpy.AddMessage('symbologyLayerFile: ' + str(symbologyLayerFile))
            arcpy.ApplySymbologyFromLayer_management(dataLayer, symbologyLayerFile)

            # dataLayer = m.listLayers(layerName)[0]
            # if dataType in ['ShapeFile']:
            #    pass

                # Alternative way of applying symbology. ArcGIS Pro doesn't apply symbology well at the moment (v2.2.0) so neither of these ways work.
                # Update symbology
                lyrFile = arcpy.mp.LayerFile(symbologyLayerFile)
                m.addLayer(lyrFile, 'TOP')
                symbologyLayer = m.listLayers()[0]
                symbologyObj = symbologyLayer.symbology
                m.removeLayer(symbologyLayer)
                dataLayer.symbology = symbologyObj

            '''
            p.save()

            return new_lyr

    except Exception:
        log.error("Error occurred while loading in layer and updating symbology")
        raise

    finally:
        # Remove layers from memory
        try:
            arcpy.Delete_management(tmpLyr)
            del tmpLyr
        except Exception:
            pass


def strToBool(s):
    ''' Converts a true/false string to an actual Boolean'''
    
    if s == "True" or s == "true":
         return True
    elif s == "False" or s == "false":
         return False
    else:
         raise ValueError


def runSystemChecks(folder=None, rerun=False):

    import LUCI_SEEA.lib.progress as progress

    # Set overwrite output
    arcpy.env.overwriteOutput = True

    # Check spatial analyst licence is available
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
    else:
        raise RuntimeError("Spatial Analyst license not present or could not be checked out")

    ### Set workspaces so that temporary files are written to the LUCI scratch geodatabase ###
    if arcpy.ProductInfo() == "ArcServer":
        log.info('arcpy.env.scratchWorkspace on server: ' + str(arcpy.env.scratchWorkspace))

        # Set current workspace
        arcpy.env.workspace = arcpy.env.scratchGDB
    else:

        # If rerunning a tool, check if scratch workspace has been set. If it has, use it as it is (with temporary rasters and feature classes from the previous run).
        scratchGDB = None

        if rerun:
            xmlFile = progress.getProgressFilenames(folder).xmlFile

            if os.path.exists(xmlFile):
                scratchGDB = readXML(xmlFile, 'ScratchGDB')

                if not arcpy.Exists(scratchGDB):
                    log.error('Previous scratch GDB ' + str(scratchGDB) + ' does not exist. Tool cannot be rerun.')
                    log.error('Exiting tool')
                    sys.exit()

        if scratchGDB is None:

            # Set scratch path from values in user settings file if values present
            scratchPath = None
            try:
                if os.path.exists(configuration.userSettingsFile):

                    tree = ET.parse(configuration.userSettingsFile)
                    root = tree.getroot()
                    scratchPath = root.find("scratchPath").text

            except Exception:
                pass # If any errors occur, ignore them. Just use the default scratch path.

            # Set scratch path if needed
            if scratchPath is None:
                scratchPath = configuration.scratchPath

            # Create scratch path folder
            if not os.path.exists(scratchPath):
                os.makedirs(scratchPath)

            # Remove old date/time stamped scratch folders if they exist and if they do not contain lock ArcGIS lock files.
            for root, dirs, files in os.walk(scratchPath):
                for dir in dirs:

                    # Try to rename folder. If this is possible then no locks are held on it and it can then be removed.
                    try:
                        fullDirPath = os.path.join(scratchPath, dir)
                        renamedDir = os.path.join(scratchPath, 'ready_for_deletion')
                        os.rename(fullDirPath, renamedDir)
                    except Exception:
                        # import traceback
                        # log.warning(traceback.format_exc())
                        pass
                    else:
                        try:
                            shutil.rmtree(renamedDir)
                        except Exception:
                            # import traceback
                            # log.warning(traceback.format_exc())
                            pass

            # Create new date/time stamped scratch folder for the scratch GDB to live in
            dateTimeStamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            scratchGDBFolder = os.path.join(scratchPath, 'scratch_' + dateTimeStamp)
            if not os.path.exists(scratchGDBFolder):
                os.mkdir(scratchGDBFolder)

            # Create scratch GDB
            scratchGDB = os.path.join(scratchGDBFolder, 'scratch.gdb')
            if not os.path.exists(scratchGDB):
                arcpy.CreateFileGDB_management(os.path.dirname(scratchGDB), os.path.basename(scratchGDB))

            # Try to remove old scratch path if still exists
            try:
                shutil.rmtree(configuration.oldScratchPath, ignore_errors=True)
            except Exception:
                pass

        # Set scratch and current workspaces
        arcpy.env.scratchWorkspace = scratchGDB
        arcpy.env.workspace = scratchGDB

        # Scratch folder
        scratchFolder = arcpy.env.scratchFolder
        if not os.path.exists(scratchFolder):
            os.mkdir(scratchFolder)

        # Remove all in_memory data sets
        arcpy.Delete_management("in_memory")    

    # Check disk space for disk with scratch workspace
    freeSpaceGb = 3
    if getFreeDiskSpaceGb(arcpy.env.scratchWorkspace) < freeSpaceGb:
        log.warning("Disk containing scratch workspace has less than " + str(freeSpaceGb) + "Gb free space. This may cause this tool to fail.")


def paramsAsText(params):

    paramsText = []
    for param in params:
        paramsText.append(param.valueAsText)

    return paramsText


def listFeatureLayers(localVars):

    layersToDelete = []
    for v in localVars:
        if isinstance(localVars[v], arcpy.mapping.Layer):
            layersToDelete.append(v)

    return layersToDelete


def getFreeDiskSpaceGb(dirname):

    """Return folder/drive free space (in megabytes)."""

    import ctypes
    import platform

    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(dirname), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value / 1024 / 1024 / 1024
    else:
        st = os.statvfs(dirname)
        return st.f_bavail * st.f_frsize / 1024 / 1024 / 1024


def checkLicenceLevel(licenceLevel):

    if licenceLevel == 'Basic':
        product = 'arcview'
    elif licenceLevel == 'Standard':
        product = 'arceditor'
    elif licenceLevel == 'Advanced':
        product = 'arcinfo'
    else:
        log.error('Licence level ' + str(licenceLevel) + ' not valid.')
        sys.exit()

    if arcpy.CheckProduct(product).strip() in ["Available", "AlreadyInitialized"]:
        return True
    else:
        return False


def indentXML(elem, level=0, more_sibs=False):

    ''' Taken from https://stackoverflow.com/questions/749796/pretty-printing-xml-in-python '''

    i = "\n"
    if level:
        i += (level - 1) * '  '
    num_kids = len(elem)
    if num_kids:
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
            if level:
                elem.text += '  '
        count = 0
        for kid in elem:
            indentXML(kid, level + 1, count < num_kids - 1)
            count += 1
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
            if more_sibs:
                elem.tail += '  '
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
            if more_sibs:
                elem.tail += '  '


def addPath(obj, folder):

    ''' Joins the folder path onto each of the objects' properties '''

    for attr, filename in six.iteritems(obj.__dict__):

        # Add file name to folder path
        filename = os.path.join(folder, filename)
        
        # Re-set the object's attribute value
        setattr(obj, attr, filename)

    return obj

def extractRasterMask(raster):

    # Takes a raster and returns its mask as a polygon

    # Set overwrite output
    arcpy.env.overwriteOutput = True

    prefix = os.path.join(arcpy.env.scratchGDB, "mask_")
    rasterMask = prefix + "rasmask"
    polyMask = prefix + "polymask"

    maskTemp = Reclassify(raster, "Value", RemapRange([[-999999.9, 999999.9, 1]]), "NODATA")
    maskTemp.save(rasterMask)

    arcpy.RasterToPolygon_conversion(rasterMask, polyMask, "NO_SIMPLIFY", "VALUE")

    return polyMask

def checkCoverage(maskA, maskB):

    # Checks the coverage between mask A and mask B

    # Set temporary variables
    prefix = os.path.join(arcpy.env.scratchGDB, "cover_")
    maskACoverage = prefix + "maskACoverage"

    percOut = 0

    if checkLicenceLevel('Advanced') or arcpy.ProductInfo() == "ArcServer":

        # Calculate total area of the coverage (study area or contributing area)
        arcpy.AddField_management(maskB, "Area_ha", "DOUBLE")
        exp = "!SHAPE.AREA@HECTARES!"
        arcpy.CalculateField_management(maskB, "Area_ha", exp, "PYTHON_9.3")

        maskBVal = 0
        for row in arcpy.da.SearchCursor(maskB, ["Area_ha"]):        
            maskBVal += float(row[0])

        # Use symmetrical difference to find which areas in maskA and maskB do not overlap
        arcpy.SymDiff_analysis(maskA, maskB, maskACoverage)

        # Check if there are non-overlapping areas in the land use and coverage
        rows = [row for row in arcpy.da.SearchCursor(maskACoverage, "*")]
        numFeatures = len(rows)

        if numFeatures != 0: # There is a discrepancy between mask A and mask B

            # Calculate the area of the polygons in the discrepancy
            arcpy.AddField_management(maskACoverage, "Sliver", "DOUBLE")
            exp = "!SHAPE.AREA@HECTARES!"
            arcpy.CalculateField_management(maskACoverage, "Sliver", exp, "PYTHON_9.3")

            area = 0
            for row in arcpy.da.SearchCursor(maskACoverage, ["Sliver"]):
                area += float(row[0])

            # Calculate percentage of the coverage area that the discrepancy covers
            percOut = area / maskBVal * 100

    else:
        log.warning('Coverage discrepancies between soil, land use, and coverage extent not checked as advanced license not present.')
        log.warning('Please ensure the soil and land use shapefile cover at least 97.5 percent of the coverage extent')

    return percOut

def listEnvironmentSettings():

    environments = arcpy.ListEnvironments()

    # Sort the environment names
    environments.sort()

    for environment in environments:
        # Format and print each environment and its current setting.
        # (The environments are accessed by key from arcpy.env.)
        log.info("{0:<30}: {1}".format(environment, arcpy.env[environment]))

def readXML(XMLfile, nodeNameList, showErrors=True):

    ''' 
    Fetches values of nodes from an XML file.
    These nodes must live as children of the top level node (typically <data>).

    nodeNameList can either be a list of node names (strings) or a single node name (i.e. a string, no list brackets needed).
    '''

    try:
        # Open file for reading
        try:
            tree = ET.parse(XMLfile)
        except IOError:
            if showErrors:
                arcpy.AddError("XML File \"" + XMLfile + "\" does not exist or cannot be opened")
            raise

        root = tree.getroot()

        # Handle nodeNameList being a single node name (a string)
        if type(nodeNameList) is not list:
            nodeNameList = [nodeNameList]

        valueList = []
        for nodeName in nodeNameList:

            # Find value of node in XML file
            node = root.find(nodeName)
            if node is None:
                value = ''
            else:
                value = node.text
            valueList.append(value)

        if len(valueList) == 0:
            return None
        elif len(valueList) == 1:
            return valueList[0]
        else:
            return valueList

    except Exception:
        if showErrors:
            arcpy.AddError("Data not read from XML file")
        raise

def writeXML(XMLfile, nodeNameValueList):

    ''' 
    Writes nodename/value pairs to an XML file. The file is created if it does not alredy exist.
    These nodes must live as children of the top level node (typically <data>).

    nodeNameValueList should have the format [(nodename, value), (nodename, value), ...]
    '''

    def createElement(parent, name):

        try:
            found = False
            for child in parent.getchildren():
                if child.tag == name:
                    found = True
            if not found:
                parent.append(ET.Element(name))

        except Exception:
            log.error("Could not create element " + name)
            raise


    def setElementValue(parent, name, value, attrib=None):

        try:
            elem = findElement(parent, name)
            elem.text = value

            if attrib is not None:
                elem.set('displayName', attrib)

        except Exception:
            log.error("Could not set value for element " + name)
            raise


    def findElement(parent, name):

        try:
            elem = None
            for child in parent.getchildren():
                if child.tag == name:
                    elem = child
            return elem

        except Exception:
            log.error("Could not find element " + name)
            raise

    # WriteXML main function code
    try:
        # Create file if does not exist
        try:
            if not os.path.exists(XMLfile):
                root = ET.Element("data")
                tree = ET.ElementTree(root)
                tree.write(XMLfile, encoding="utf-8", xml_declaration=True)
            else:
                # Open file for reading
                tree = ET.parse(XMLfile)
                root = tree.getroot()

        except Exception:
            log.error("Problem creating or opening XML file")
            raise

        # Loop through node/value list
        for nodeNameValue in nodeNameValueList:

            nodeName = nodeNameValue[0]
            value = nodeNameValue[1]

            if len(nodeNameValue) == 3:
                attrib = nodeNameValue[2]

            else:
                attrib = None

            # Check if node exists
            node = findElement(root, nodeName)
            if node is None:
                createElement(root, nodeName) # Create new node

            setElementValue(root, nodeName, value, attrib)

        try:
            # Make XML file more human-readable
            indentXML(root)

            # Save the XML file
            tree.write(XMLfile, encoding='utf-8', xml_declaration=True)

        except Exception:
            log.error("Problem saving XML file")
            raise     

    except Exception:
        log.error("Data not written to XML file")
        raise

def writeParamsToXML(params, folder, toolName=None):


    xmlFile = os.path.join(folder, 'inputs.xml')
    paramValueList = []

    # Adding date and time to list
    dateTime = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    paramValueList.append(('DateTimeRun', dateTime, 'Date/time ran'))

    if toolName is not None:
        paramValueList.append(('ToolName', toolName, 'Tool name'))

    for param in params:
        paramValueList.append((param.name, param.valueAsText, param.displayName))

    writeXML(xmlFile, paramValueList)