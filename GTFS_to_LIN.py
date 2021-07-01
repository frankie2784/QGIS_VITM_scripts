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
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsFeatureRequest
from qgis.core import QgsLineString, QgsMultiLineString
from qgis.utils import active_plugins
import processing
import re


class GTFStoLIN(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMapLayer('GTFSNetwork', 'GTFS Network', defaultValue=None, types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterMapLayer('SVITMNetwork', 'S-VITM Network', defaultValue=None, types=[QgsProcessing.TypeVectorLine]))
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
        vitmLayerStr = parameters['SVITMNetwork']
        
        #Update filter for VITM network layer
        feedback.pushInfo('Done.\n\nAdjusting filters from VITM network layer...')
        vitmOrigQuery = vitmLayer.subsetString()
        feedback.pushInfo('Original filter: ' + vitmOrigQuery)
        switchBlock = {
        'Bus': 'LINKCLASS NOT IN (-1, 0, 1, 42, 43, 45, 46, 47, 48, 49)',
        'Tram': 'LINKCLASS NOT IN (-1, 0, 1, 42, 44, 45, 46, 47, 48, 49)',
        'Train': 'LINKCLASS NOT IN (-1, 0, 1, 43, 44, 45, 46, 47, 48, 49)',
        }
        vitmLayer.setSubsetString(switchBlock.get(parameters['TransportMode'], ''))
        
        #Check the input layers for lines (i.e. they aren't all filtered out)
        feedback.pushInfo('DOne.\n\nChecking input layers for valid inputs...')
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

        # Reproject layer
        feedback.pushInfo('Reprojecting GTFS layer into VITM CRS...')
        vitmCRS = vitmLayer.sourceCrs()
        alg_params = {
            'INPUT': parameters['GTFSNetwork'],
            'OPERATION': '',
            'TARGET_CRS': vitmCRS,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
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
        feedback.pushInfo('Done.\n\n\n\nCommencing pathfinding by route...')
        strength = parameters['Strength']
        for feat in gtfsLinesFeatures:
            
            line = feat.geometry().constGet()
            shortname = str(feat['shortname'])
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
            
            feedback.pushInfo('Processing Route ID: ' + shortname)
            
            #Set score (speed) parameters
            wkt = bufferFeature.geometry().asWkt()
            alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'SPEED',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Integer
            'FORMULA': 'if (within( $geometry, geom_from_wkt(\'' + wkt + '\')), ' + str(strength) + ', if( intersects( $geometry, geom_from_wkt( \'' + wkt + '\')), ' + str(strength / 5) + ', ' + str(strength / 10) + '))',
            'INPUT': vitmLayerStr,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Speed'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        #DEBUG load layer
        alg_params = {
            'INPUT': outputs['Speed']['OUTPUT'],
            'NAME': 'Debug Output'
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
