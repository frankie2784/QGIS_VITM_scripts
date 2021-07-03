"""
Name : Generate LIN from Network
Group : VITM
With QGIS : 32000
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterMapLayer
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterEnum
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingUtils
from qgis.core import QgsAggregateCalculator
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest
from qgis.core import QgsLineString, QgsMultiLineString
from qgis.analysis import QgsVectorLayerDirector
from qgis.utils import active_plugins
import processing, re, math

def getStartCoordinates(feat):
    line = feat.geometry().constGet()
    if type(line) == QgsLineString:
        # Assume LineString
        x = line[0].x()
        y = line[0].y()
    elif type(line) == QgsMultiLineString:
        # Found MultiLineString
        linestring_count = 0
        for l in line:
            x = l[0].x()
            y = l[0].y()
            break
    return (x, y)

def getDistance(x1, y1, x2, y2):
    return math.sqrt(pow(x2 - x1, 2) + pow(y2 - y1, 2))

def generateNodeList(networkLayer, lineLayer):
    outList = []
    terminusNode = 0
    
    #Get the starting coordinates of the route
    for f in lineLayer.getFeatures():
        x, y = getStartCoordinates(f)
        break
    
    # copy A, B values into list and;
    aList = []
    bList = []
    for feat in networkLayer.getFeatures():
        aList.append(int(feat['A']))
        bList.append(int(feat['B']))
        
    # determine start node
    distFromStart = 1000000.0
    for feat in networkLayer.getFeatures():
        if aList.count(int(feat['A'])) == 1:
            testX, testY = getStartCoordinates(feat)
            testDistance = getDistance(x, y, testX, testY)
            if testDistance < distFromStart:
                distFromStart = testDistance
                nextNode = int(feat['A'])
    
    #build the N list
    while len(aList) > 0:
        #find the next node in aList
        outList.append(str(nextNode))
        while nextNode in bList:
            i = bList.index(nextNode)
            aList.pop(i)
            bList.pop(i)
            
        while nextNode in aList:
            i = aList.index(nextNode)
            aList.pop(i)
            testNext = bList.pop(i)
            if aList.count(testNext) <= 1:
                nextNode = testNext
                break
    
    outList.append(str(nextNode))
    return ','.join(outList)
    
class GTFStoLIN(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMapLayer('GTFSNetwork', 'GTFS Network', defaultValue=None, types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterMapLayer('SVITMNetwork', 'S-VITM Network', defaultValue=None, types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterNumber('CentralNode', 'Central (CBD) Node', type=QgsProcessingParameterNumber.Integer, defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber('VITMMode', 'Cube Mode ID', type=QgsProcessingParameterNumber.Integer, defaultValue=0))
        self.addParameter(QgsProcessingParameterFile('HeadwayCSVFile', 'Headways', optional=True, behavior=QgsProcessingParameterFile.File, fileFilter='CSV Files (*.csv)', defaultValue=None))
        self.addParameter(QgsProcessingParameterEnum('TransportMode', 'Transport Mode', options=['Bus','Tram','Train'], allowMultiple=False, usesStaticStrings=False, defaultValue=[]))
        self.addParameter(QgsProcessingParameterString('RoutePrefix', 'Route Prefix', multiLine=False, defaultValue='MR_'))
        self.addParameter(QgsProcessingParameterNumber('Buffer', 'Search buffer (metres)', type=QgsProcessingParameterNumber.Integer, defaultValue=20))
        self.addParameter(QgsProcessingParameterNumber('Strength', 'Breadth search cost penalty (1-999), i.e. relative weight assigned to using links within buffer', type=QgsProcessingParameterNumber.Integer, minValue=1, maxValue=999, defaultValue=700))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        outputs = {}
        
        #Check that required plugin is installed
        if 'QNEAT3' not in active_plugins:
            feedback.pushInfo('Error: \'QNEAT3\' plugin not found. Please ensure you this installed by going to Plugins -> Manage and Install Plugins.\n')
            return results
        
        #Load input layers into memory
        feedback.pushInfo('Loading input layers into memory...')
        gtfsLayer = QgsProcessingUtils.mapLayerFromString(parameters['GTFSNetwork'], context=context)
        vitmLayer = QgsProcessingUtils.mapLayerFromString(parameters['SVITMNetwork'], context=context)
        userA2 = 'GTFS' # Data source
        modeID = str(parameters['VITMMode'])
        oneway = 'T'
        circular = 'F'
        vehicleType = '0'
        fareSystem = '1'        
        
        #Update filter for VITM network layer
        feedback.pushInfo('Done.\n\nAdjusting filters from VITM network layer...')
        vitmOrigQuery = vitmLayer.subsetString()
        feedback.pushInfo('Original filter: ' + vitmOrigQuery)
        switchBlock = {
        'Bus': 'LINKCLASS NOT IN (-1, 0, 1, 42, 43, 45, 46, 47, 48, 49)',
        'Tram': 'LINKCLASS NOT IN (-1, 0, 1, 42, 44, 45, 46, 47, 48, 49)',
        'Train': 'LINKCLASS IN (42)',
        }
        vitmLayer.setSubsetString(switchBlock.get(parameters['TransportMode'], ''))
        
        #Check the input layers for lines (i.e. they aren't all filtered out)
        feedback.pushInfo('Done.\n\nChecking input layers for valid inputs...')
        if gtfsLayer.featureCount() == 0:
            feedback.pushInfo('ERROR: No features found in GTFS input layer. exiting...')
            vitmLayer.setSubsetString(vitmOrigQuery)
            return results
        if vitmLayer.featureCount() == 0:
            feedback.pushInfo('ERROR: No features found in VITM network layer. exiting...')
            vitmLayer.setSubsetString(vitmOrigQuery)
            return results
        vitmReqAttr = ['A', 'B', 'LINKCLASS']
        if all( i in vitmLayer.attributeAliases() for i in vitmReqAttr):
            feedback.pushInfo('Done.\n')
        else:
            feedback.pushInfo('ERROR: VITM network requires A, B and LINKCLASS attributes.\n')
            vitmLayer.setSubsetString(vitmOrigQuery)
            feedback.pushInfo('Available attributes: ' + ', '.join(vitmLayer.attributeAliases()))
            return results

        # Create spatial index on the VITM layer
        feedback.pushInfo('Done.\n\nCreating spatial index...')
        alg_params = {
            'INPUT': parameters['SVITMNetwork']
        }
        outputs['SVITMSpatialIndex'] = processing.run('native:createspatialindex', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Reproject layer
        feedback.pushInfo('Done.\n\nReprojecting GTFS layer into VITM CRS...')
        vitmCRS = vitmLayer.sourceCrs()
        alg_params = {
            'INPUT': parameters['GTFSNetwork'],
            'OPERATION': '',
            'TARGET_CRS': vitmCRS,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Get the coordinates of the central node, if provided
        if parameters['CentralNode'] != 0:
            feedback.pushInfo('Done.\n\nGetting coordinates of the central node...')
            alg_params = {
            'FIELD': 'A',
            'INPUT': outputs['SVITMSpatialIndex']['OUTPUT'],
            'OPERATOR': 0,  # =
            'VALUE': parameters['CentralNode'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['ExtractByAttribute'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Get the start point of the first line
            centralLinksFeatures = QgsProcessingUtils.mapLayerFromString(outputs['ExtractByAttribute']['OUTPUT'], context=context).getFeatures()
            for feat in centralLinksFeatures:
                line = feat.geometry().constGet()
                if type(line) == QgsLineString:
                    # Assume LineString
                    cbd_node = str(line[0].x()) + ',' + str(line[0].y())
                elif type(line) == QgsMultiLineString:
                    # Found MultiLineString
                    linestring_count = 0
                    for l in line:
                        if linestring_count == 0:
                            cbd_node = str(l[0].x()) + ',' + str(l[0].y())
                        linestring_count += 1
                else:
                    feedback.pushInfo('Invalid geometry for feature: unsetting central point.')
                    parameters['CentralNode'] = 0
                    continue
        
        #Add the Route Shortname to the attribute table
        feedback.pushInfo('Done.\n\nExtracting route shortnames...')
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'shortname',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # String
            'FORMULA': ' regexp_replace(\"route_id\",\'\\\\d+-([a-zA-Z0-9]+)-.+\',\'' + parameters['RoutePrefix'] + '\\\\1\')',
            'INPUT': outputs['ReprojectLayer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AddShortname'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        #Add the Line Lengths to the attribute table
        feedback.pushInfo('Done.\n\nExteracting line lengths...')
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'route_length',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Integer
            'FORMULA': ' to_int( $length ) ',
            'INPUT': outputs['AddShortname']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AddLength'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        #Filter for longest line for each route
        feedback.pushInfo('Done.\n\nExteracting longest lines by route...')
        alg_params = {
            'EXPRESSION': ' if (to_int( $length ) = maximum( route_length, shortname), true, false) ',
            'INPUT': outputs['AddLength']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractByExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Delete duplicates by attribute
        alg_params = {
            'FIELDS': ['shortname'],
            'INPUT': outputs['ExtractByExpression']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DeleteDuplicatesByAttribute'] = processing.run('native:removeduplicatesbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        #Add the search buffer
        feedback.pushInfo('Done.\n\nCreating search buffer...')
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': parameters['Buffer'],
            'END_CAP_STYLE': 0,
            'INPUT': outputs['DeleteDuplicatesByAttribute']['OUTPUT'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['BufferedGTFS'] = processing.run('native:buffer', alg_params, context=context, is_child_algorithm=True)
        
        #Convert routes to feature lists
        sortRequest = QgsFeatureRequest()
        sortRequest.setOrderBy(QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause('shortname', ascending=True)]))
        gtfsBuffered = QgsProcessingUtils.mapLayerFromString(outputs['BufferedGTFS']['OUTPUT'], context=context)
        gtfsBufferedFeatures = gtfsBuffered.getFeatures(sortRequest)
        gtfsLines = QgsProcessingUtils.mapLayerFromString(outputs['DeleteDuplicatesByAttribute']['OUTPUT'], context=context)
        gtfsLinesFeatures = gtfsLines.getFeatures(sortRequest)
        
        #Commence pathfinding loop
        feedback.setProgress(1)
        feedback.pushInfo('Done.\n\n**********\n\nCommencing pathfinding by route...')
        strength = parameters['Strength']
        output_layer = []
        for feat in gtfsLinesFeatures:
            
            line = feat.geometry().constGet()
            shortname = str(feat['shortname'])
            longname = str(feat['route_name'])
            userA1 = str(feat['shortname']) + '-' + longname[:1] + '_' + str(longname.split(' - ')[1])[:1]
            
            gtfsBuffered.setSubsetString('"shortname" = \'' + shortname + '\'')
            for f in gtfsBuffered.getFeatures():
                bufferFeature = f
            
            #Get endpoints of route
            if type(line) == QgsLineString:
                # Assume LineString
                start_point = str(line[0].x()) + ',' + str(line[0].y())
                end_point = str(line[-1].x()) + ',' + str(line[-1].y())
            elif type(line) == QgsMultiLineString:
                # Found MultiLineString
                linestring_count = 0
                for l in line:
                    if linestring_count == 0:
                        start_point = str(l[0].x()) + ',' + str(l[0].y())
                    end_point = str(l[-1].x()) + ',' + str(l[-1].y())
                    linestring_count += 1
            else:
                feedback.pushInfo('Invalid geometry for feature: Skipping route ID ' + shortname)
                continue

            if start_point == end_point:
                feedback.pushInfo('Invalid geometry for feature: Skipping route ID ' + shortname)
                continue
            
            # Adjust the start / end based on the central node
            if parameters['CentralNode'] != 0:
                x_cbd, y_cbd = cbd_node.split(',')
                x_start, y_start = start_point.split(',')
                x_end, y_end = end_point.split(',')
                dist_start = getDistance(float(x_cbd), float(y_cbd), float(x_start), float(y_start))
                dist_end = getDistance(float(x_cbd), float(y_cbd), float(x_end), float(y_end))
                if (dist_start < dist_end):
                    temp = start_point
                    start_point = end_point
                    end_point = temp
            
            feedback.pushInfo('Processing Route ID: ' + shortname)
            
            #Extract S-VITM network only around the buffer feature
            bbox = bufferFeature.geometry().boundingBox().buffered(1000)
            alg_params = {
                'CLIP': False,
                'EXTENT': str(bbox.xMinimum()) + ',' + str(bbox.xMaximum()) + ',' + str(bbox.yMinimum()) + ',' + str(bbox.yMaximum()) + ' [' + vitmCRS.authid() + ']',
                'INPUT': outputs['SVITMSpatialIndex']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['ExtractclipByExtent'] = processing.run('native:extractbyextent', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            #Set score (speed) parameters
            wkt = bufferFeature.geometry().asWkt()
            alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'SPEED',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Integer
            'FORMULA': 'if (within( $geometry, geom_from_wkt(\'' + wkt + '\')), ' + str(strength) + ', if( intersects( $geometry, geom_from_wkt( \'' + wkt + '\')), ' + str(strength / 10) + ', 1))',
            'INPUT': outputs['ExtractclipByExtent']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Speed'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
            # BEGIN : INBOUND ROUTE *******************************************
            try:
                # Find inbound route
                alg_params = {
                    'DEFAULT_DIRECTION': QgsVectorLayerDirector.DirectionForward,
                    'DEFAULT_SPEED': 5,
                    'DIRECTION_FIELD': '',
                    'END_POINT': end_point,
                    'ENTRY_COST_CALCULATION_METHOD': 0,
                    'INPUT': outputs['Speed']['OUTPUT'],
                    'SPEED_FIELD': 'SPEED',
                    'START_POINT': start_point,
                    'STRATEGY': 1,
                    'TOLERANCE': 0,
                    'VALUE_BACKWARD': '',
                    'VALUE_BOTH': '',
                    'VALUE_FORWARD': '',
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['ShortestPathPointToPoint'] = processing.run('qneat3:shortestpathpointtopoint', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            except:
                feedback.pushInfo('The routing engine was unable to find a suitable route.')
                
            # Add route parameters to the output
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'NAME',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + shortname + '\'',
                'INPUT': outputs['ShortestPathPointToPoint']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'LONGNAME',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + longname + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'USERA1',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + userA1 + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'USERA2',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + userA2 + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'MODE',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 1, # Integer
                'FORMULA': str(modeID),
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'ONEWAY',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + oneway + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'CIRCULAR',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + circular + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            # TODO: add headways from input if provided
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'HEADWAY',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'0,0,0,0\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'VEHICLETYPE',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 1, # Integer
                'FORMULA': str(vehicleType),
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'FARESYSTEM',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 1, # Integer
                'FORMULA': str(fareSystem),
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Remove unneeded parameters
            alg_params = {
                'COLUMN': ['start_id', 'start_coordinates', 'start_entry_cost', 'end_id', 'end_coordinates', 'end_exit_cost', 'cost_on_graph', 'total_cost'],
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['DropFields'] = processing.run('native:deletecolumn', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            # Add N value list
            #   Step 1: Create buffer around VITM route
            alg_params = {
                'DISSOLVE': True,
                'DISTANCE': 1,
                'END_CAP_STYLE': 0,  # Round
                'INPUT': outputs['DropFields']['OUTPUT'],
                'JOIN_STYLE': 0,  # Round
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['NListStep'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 2: Select links that are fully enclosed by buffer
            alg_params = {
                'INPUT': outputs['ExtractclipByExtent']['OUTPUT'],
                'INTERSECT': outputs['NListStep']['OUTPUT'],
                'PREDICATE': [6],  # are within
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['NListStep'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 3: Add N list to ouput
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'N',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + generateNodeList(QgsProcessingUtils.mapLayerFromString(outputs['NListStep']['OUTPUT'], context=context), QgsProcessingUtils.mapLayerFromString(outputs['DropFields']['OUTPUT'], context=context)) + '\'',
                'INPUT': outputs['DropFields']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Determine score based on sqkm area of shape created by joining routes together
            #   Step 1: convert GTFS line to layer
            alg_params = {
                'FIELD': 'shortname',
                'INPUT': outputs['DeleteDuplicatesByAttribute']['OUTPUT'],
                'OPERATOR': 0,  # =
                'VALUE': shortname,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['ExtractByAttribute'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 2: Merge layers together
            alg_params = {
                'CRS': vitmCRS,
                'LAYERS': [outputs['ExtractByAttribute']['OUTPUT'], outputs['DropFields']['OUTPUT']],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Overlap'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 3: convert to smallest polygons
            alg_params = {
                'INPUT': outputs['Overlap']['OUTPUT'],
                'KEEP_FIELDS': False,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Overlap'] = processing.run('native:polygonize', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 4: Extract the area of the shapes
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'area',
                'FIELD_PRECISION': 3,
                'FIELD_TYPE': 0,  # Float
                'FORMULA': '$area',
                'INPUT': outputs['Overlap']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Overlap'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            (area, success) = QgsProcessingUtils.mapLayerFromString(outputs['Overlap']['OUTPUT'], context=context).aggregate(5, 'area')
            #   Step 5: Add value to output
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'score',
                'FIELD_PRECISION': 3,
                'FIELD_TYPE': 0,  # Float
                'FORMULA': str(area) + ' / $length',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            #Append output to output list
            output_layer.append(outputs['FieldCalculator']['OUTPUT'])
                
            # BEGIN : OUTBOUND ROUTE *******************************************
            try:
                # Find inbound route
                alg_params = {
                    'DEFAULT_DIRECTION': QgsVectorLayerDirector.DirectionForward,
                    'DEFAULT_SPEED': 5,
                    'DIRECTION_FIELD': '',
                    'END_POINT': start_point,
                    'ENTRY_COST_CALCULATION_METHOD': 0,
                    'INPUT': outputs['Speed']['OUTPUT'],
                    'SPEED_FIELD': 'SPEED',
                    'START_POINT': end_point,
                    'STRATEGY': 1,
                    'TOLERANCE': 0,
                    'VALUE_BACKWARD': '',
                    'VALUE_BOTH': '',
                    'VALUE_FORWARD': '',
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['ShortestPathPointToPoint'] = processing.run('qneat3:shortestpathpointtopoint', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            except:
                feedback.pushInfo('The routing engine was unable to find a suitable route.')
                
            # Add route parameters to the output
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'NAME',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + shortname + 'R\'',
                'INPUT': outputs['ShortestPathPointToPoint']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'LONGNAME',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + longname + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'USERA1',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + userA1 + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'USERA2',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + userA2 + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'MODE',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 1, # Integer
                'FORMULA': str(modeID),
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'ONEWAY',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + oneway + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'CIRCULAR',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + circular + '\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            # TODO: add headways from input if provided
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'HEADWAY',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'0,0,0,0\'',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'VEHICLETYPE',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 1, # Integer
                'FORMULA': str(vehicleType),
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'FARESYSTEM',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 1, # Integer
                'FORMULA': str(fareSystem),
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Remove unneeded parameters
            alg_params = {
                'COLUMN': ['start_id', 'start_coordinates', 'start_entry_cost', 'end_id', 'end_coordinates', 'end_exit_cost', 'cost_on_graph', 'total_cost'],
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['DropFields'] = processing.run('native:deletecolumn', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
    
            # Add N value list
            #   Step 1: Create buffer around VITM route
            alg_params = {
                'DISSOLVE': True,
                'DISTANCE': 1,
                'END_CAP_STYLE': 0,  # Round
                'INPUT': outputs['DropFields']['OUTPUT'],
                'JOIN_STYLE': 0,  # Round
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['NListStep'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 2: Select links that are fully enclosed by buffer
            alg_params = {
                'INPUT': outputs['ExtractclipByExtent']['OUTPUT'],
                'INTERSECT': outputs['NListStep']['OUTPUT'],
                'PREDICATE': [6],  # are within
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['NListStep'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 3: Add N list to ouput
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': 'N',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 2, # String
                'FORMULA': '\'' + generateNodeList(QgsProcessingUtils.mapLayerFromString(outputs['NListStep']['OUTPUT'], context=context), QgsProcessingUtils.mapLayerFromString(outputs['DropFields']['OUTPUT'], context=context)) + '\'',
                'INPUT': outputs['DropFields']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Determine score based on sqkm area of shape created by joining routes together
            #   Step 1: convert GTFS line to layer
            alg_params = {
                'FIELD': 'shortname',
                'INPUT': outputs['DeleteDuplicatesByAttribute']['OUTPUT'],
                'OPERATOR': 0,  # =
                'VALUE': shortname,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['ExtractByAttribute'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 2: Merge layers together
            alg_params = {
                'CRS': vitmCRS,
                'LAYERS': [outputs['ExtractByAttribute']['OUTPUT'], outputs['DropFields']['OUTPUT']],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Overlap'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 3: convert to smallest polygons
            alg_params = {
                'INPUT': outputs['Overlap']['OUTPUT'],
                'KEEP_FIELDS': False,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Overlap'] = processing.run('native:polygonize', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            #   Step 4: Extract the area of the shapes
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'area',
                'FIELD_PRECISION': 3,
                'FIELD_TYPE': 0,  # Float
                'FORMULA': '$area',
                'INPUT': outputs['Overlap']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Overlap'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            (area, success) = QgsProcessingUtils.mapLayerFromString(outputs['Overlap']['OUTPUT'], context=context).aggregate(5, 'area')
            #   Step 5: Add value to output
            alg_params = {
                'FIELD_LENGTH': 10,
                'FIELD_NAME': 'score',
                'FIELD_PRECISION': 3,
                'FIELD_TYPE': 0,  # Float
                'FORMULA': str(area) + ' / $length',
                'INPUT': outputs['FieldCalculator']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            #Append output to output list
            output_layer.append(outputs['FieldCalculator']['OUTPUT'])

        #Make sure output has valid features
        if len(output_layer) == 0:
            feedback.pushInfo('Error: No features in final output. Terminating process.')
            return results
        
        #Merge output_layer list into one vector layer
        alg_params = {
            'CRS': vitmCRS,
            'LAYERS': output_layer,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MergeVectorLayers'] = processing.run('native:mergevectorlayers', alg_params, context=context, is_child_algorithm=True)
        
        # Load layer into project
        alg_params = {
            'INPUT': outputs['MergeVectorLayers']['OUTPUT'],
            'NAME': 'Snapped routes'
        }
        outputs['LoadLayerIntoProject'] = processing.run('native:loadlayer', alg_params, context=context, is_child_algorithm=True)

        return results

    def name(self):
        return 'Generate LIN from GTFS'

    def displayName(self):
        return 'Generate LIN from GTFS'

    def group(self):
        return 'VITM'

    def groupId(self):
        return 'VITM'

    def createInstance(self):
        return GTFStoLIN()
