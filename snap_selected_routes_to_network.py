"""
QGIS : 31802
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingUtils, QgsField
from qgis.core import QgsLineString, QgsMultiLineString
from PyQt5.QtCore import QVariant
from qgis.core import edit
from qgis.utils import active_plugins
import processing
import math


class SnapSelectedRoutesToNetwork(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('Network', 'Network layer', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('Routes', 'Selected routes layer', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterField('RouteIDField', 'Route ID field', type=QgsProcessingParameterField.Any, parentLayerParameterName='Routes', allowMultiple=False, defaultValue='ROUTESHTNM'))
        self.addParameter(QgsProcessingParameterNumber('Buffer', 'Search buffer (metres)', type=QgsProcessingParameterNumber.Integer, defaultValue=20))
        self.addParameter(QgsProcessingParameterNumber('Strength', 'Breadth search cost penalty (1-999), i.e. relative weight assigned to using links within buffer', type=QgsProcessingParameterNumber.Integer, minValue=1, maxValue=999, defaultValue=700))
        self.addParameter(QgsProcessingParameterBoolean('Filter', 'Filter routes layer to selected', defaultValue=True))

    def processAlgorithm(self, parameters, context, model_feedback):

        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        outputs = {}

        if 'QNEAT3' not in active_plugins:
            feedback.pushInfo('Error: \'QNEAT3\' plugin not found. Please ensure you this installed by going to Plugins -> Manage and Install Plugins.')
            return results

        feedback.pushInfo('Preparing inputs...')
        feedback.pushInfo('')

        # Original routes filter
        orig_routes = QgsProcessingUtils.mapLayerFromString(parameters['Routes'], context=context)

        fid = 0
        with edit(orig_routes):
            orig_routes.addAttribute(QgsField('uniqueID', QVariant.Int))
            for feat in orig_routes.getFeatures():
                feat['uniqueID'] = fid
                orig_routes.updateFeature(feat)
                fid += 1
            
        fids = []
        for feat in orig_routes.selectedFeatures():
            fids.append(str(feat['uniqueID']))

        if len(fids) == 0:
            feedback.pushInfo('Error: No routes selected.')
            return results

        orig_qry = orig_routes.subsetString()
        if not parameters['Filter']:
            if len(orig_qry) > 0:
                orig_routes.setSubsetString('(' + orig_qry + ') AND uniqueID IN (' + ','.join(fids) + ')')
        else:
            orig_routes.setSubsetString('uniqueID IN (' + ','.join(fids) + ')')
        
        orig_routes.removeSelection()
        total_features = orig_routes.featureCount()
        
        if total_features == 0:
            feedback.pushInfo('Error: No features selected. Terminating.')
            orig_routes.setSubsetString(orig_qry)
            return results
        else:
            feedback.pushInfo(str(total_features) + ' features found.')
            feedback.pushInfo('')

        network_layer = QgsProcessingUtils.mapLayerFromString(parameters['Network'], context=context)
        crs = network_layer.crs().authid()

        feedback.pushInfo('CRS = '+crs)

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
            'JOIN_FIELDS': ['uniqueID'],
            'METHOD': 0,
            'NON_MATCHING': None,
            'PREDICATE': [0],
            'PREFIX': 'origroute_',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinAttributesByLocation'] = processing.run('native:joinattributesbylocation', alg_params, context=context, is_child_algorithm=True)

        new_layer = []
        counter = 1

        feedback.setProgress(1)
        for feat in orig_routes.getFeatures():
        
            fid = str(feat['uniqueID'])
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
                'FORMULA': 'if (origroute_uniqueID = '+fid+', '+str(strength)+', 1)',
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

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': 0.1,
            'END_CAP_STYLE': 0,
            'INPUT': outputs['MergeVectorLayers']['OUTPUT'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, is_child_algorithm=True)

        # Select by location
        alg_params = {
            'INPUT': parameters['Network'],
            'INTERSECT': outputs['Buffer']['OUTPUT'],
            'METHOD': 0,
            'PREDICATE': [6]
        }
        outputs['SelectByLocation'] = processing.run('native:selectbylocation', alg_params, context=context, is_child_algorithm=True)

        # Load layer into project
        alg_params = {
            'INPUT': outputs['MergeVectorLayers']['OUTPUT'],
            'NAME': 'Snapped routes'
        }
        outputs['LoadLayerIntoProject'] = processing.run('native:loadlayer', alg_params, context=context, is_child_algorithm=True)
        
        # Clear the filter on the input layer
        if not parameters['Filter']:
            orig_routes.setSubsetString(orig_qry)

        return results

    def name(self):
        return 'Snap Selected Vector to S-VITM Network'

    def displayName(self):
        return 'Snap Selected Vector to S-VITM Network'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return SnapSelectedRoutesToNetwork()