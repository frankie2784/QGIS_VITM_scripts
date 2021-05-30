"""
QGIS : 31802
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsProcessingUtils
from qgis.core import QgsFeatureRequest
from qgis.core import QgsLineString, QgsMultiLineString
import processing
from qgis.utils import active_plugins
import math


class SnapAllRoutesToNetwork(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('Network', 'Network layer', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('Routes', 'Routes layer', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterField('RouteIDField', 'Route ID field', type=QgsProcessingParameterField.Any, parentLayerParameterName='Routes', allowMultiple=False, defaultValue='ROUTESHTNM'))
        self.addParameter(QgsProcessingParameterNumber('Buffer', 'Search buffer (metres)', type=QgsProcessingParameterNumber.Integer, defaultValue=20))
        self.addParameter(QgsProcessingParameterNumber('Strength', 'Breadth search cost penalty (1-999), i.e. relative weight assigned to using links within buffer', type=QgsProcessingParameterNumber.Integer, minValue=1, maxValue=999, defaultValue=700))

    def processAlgorithm(self, parameters, context, model_feedback):
        
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        
        results = {}
        outputs = {}

        if 'QNEAT3' not in active_plugins:
            feedback.pushInfo('Error: \'QNEAT3\' plugin not found. Please ensure you this installed by going to Plugins -> Manage and Install Plugins.')
            return results
            
        feedback.pushInfo('Preparing inputs...')

        network_layer = QgsProcessingUtils.mapLayerFromString(parameters['Network'], context=context)
        crs = network_layer.crs().authid()

        feedback.pushInfo('CRS = ' + crs)
        
        buffer = parameters['Buffer']
        strength = parameters['Strength']
        route_id_field = parameters['RouteIDField']

        # FILTER LINKCLASS
        alg_params = {
            'EXPRESSION': 'NOT array_contains(array(-1,1,42,45,46), LINKCLASS)',
            'INPUT': parameters['Network'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FilterLinkclass'] = processing.run('native:extractbyexpression', alg_params, context=context, is_child_algorithm=True)

        # Create spatial index
        alg_params = {
            'INPUT': outputs['FilterLinkclass']['OUTPUT']
        }
        outputs['CreateSpatialIndex'] = processing.run('native:createspatialindex', alg_params, context=context, is_child_algorithm=True)

        # Reproject layer
        alg_params = {
            'INPUT': parameters['Routes'],
            'OPERATION': '',
            'TARGET_CRS': QgsCoordinateReferenceSystem(crs),
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, is_child_algorithm=True)

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': buffer,
            'END_CAP_STYLE': 0,
            'INPUT': outputs['ReprojectLayer']['OUTPUT'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, is_child_algorithm=True)

        # Join attributes by location
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'INPUT': outputs['CreateSpatialIndex']['OUTPUT'],
            'JOIN': outputs['Buffer']['OUTPUT'],
            'JOIN_FIELDS': ['fid'],
            'METHOD': 0,
            'NON_MATCHING': None,
            'PREDICATE': [0],
            'PREFIX': 'origroute_',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinAttributesByLocation'] = processing.run('native:joinattributesbylocation', alg_params, context=context, is_child_algorithm=True)

        routes_layer = QgsProcessingUtils.mapLayerFromString(outputs['ReprojectLayer']['OUTPUT'], context=context)

        # set order by field & get features
        request = QgsFeatureRequest()
        clause = QgsFeatureRequest.OrderByClause(route_id_field, ascending=True)
        orderby = QgsFeatureRequest.OrderBy([clause])
        request.setOrderBy(orderby)
        features = routes_layer.getFeatures(request)
        
        total_features = routes_layer.featureCount()

        if total_features == 0:
            feedback.pushInfo('Error: No features found. Terminating.')
            return results
        else:
            feedback.pushInfo(str(total_features) + ' features found. Starting routing operation.')
            feedback.pushInfo('')

        new_layer = []
        counter = 1

        feedback.setProgress(1)
        for feat in features:
        
            fid = str(feat['fid'])
            route_id = str(feat[route_id_field])

            line = feat.geometry().constGet()

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
                feedback.pushInfo('Invalid geometry for feature ' + str(counter) + ': Skipping route ID ' + route_id)
                continue

            if start_point == end_point:
                feedback.pushInfo('Invalid geometry for feature ' + str(counter) + ': Skipping route ID ' + route_id)
                continue
            
            feedback.pushInfo('Processing feature ' + str(counter) + ' of ' + str(total_features) + ': Route ID ' + route_id)

            # SPEED
            alg_params = {
                'FIELD_LENGTH': 3,
                'FIELD_NAME': 'SPEED',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 1,
                'FORMULA': 'if (origroute_fid = '+fid+', '+str(strength)+', 1)',
                'INPUT': outputs['JoinAttributesByLocation']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['Speed'] = processing.run('native:fieldcalculator', alg_params, context=context, is_child_algorithm=True)

            try:
                # Shortest path (point to point)
                alg_params = {
                    'DEFAULT_DIRECTION': 2,
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
                outputs['ShortestPathPointToPoint'] = processing.run('qneat3:shortestpathpointtopoint', alg_params, context=context, is_child_algorithm=True)
                
                # Field calculator
                alg_params = {
                    'FIELD_LENGTH': 20,
                    'FIELD_NAME': 'route_id',
                    'FIELD_PRECISION': 0,
                    'FIELD_TYPE': 2,
                    'FORMULA': '\''+route_id+'\'',
                    'INPUT': outputs['ShortestPathPointToPoint']['OUTPUT'],
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['FieldCalculator'] = processing.run('native:fieldcalculator', alg_params, context=context, is_child_algorithm=True)

                new_layer.append(outputs['FieldCalculator']['OUTPUT'])
            except:
                feedback.pushInfo('The routing engine was unable to find a suitable route. Skipping feature ' + str(counter))

            counter += 1
            feedback.setProgress(math.ceil((float(counter) / float(total_features)) * 100))

        if len(new_layer) == 0:
            feedback.pushInfo('Error: No features in final output. Terminating process.')
            return results

        # Merge vector layers
        alg_params = {
            'CRS': QgsCoordinateReferenceSystem(crs),
            'LAYERS': new_layer,
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
        return 'Snap all routes to network'

    def displayName(self):
        return 'Snap all routes to network'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return SnapAllRoutesToNetwork()
