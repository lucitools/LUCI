import arcpy
import os
import sys
import shutil
import datetime # For writing current date/time to inputs.xml
import time # For logging warnings that are very close together
import xml.etree.cElementTree as ET

from LUCI.lib.external import six # Python 2/3 compatibility module
import configuration
import LUCI.lib.log as log

from LUCI.lib.refresh_modules import refresh_modules
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

    import LUCI.lib.progress as progress

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

