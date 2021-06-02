"""
Model exported as python.
Name : model
Group : 
With QGIS : 31802
"""

from qgis.core import QgsProcessing, QgsProcessingUtils
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsCoordinateReferenceSystem
import processing
import math


class Model(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('GTFSlayer', 'GTFS layer', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('LINElayer', 'LINE layer', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('Tolerance', 'Tolerance (metres)', type=QgsProcessingParameterNumber.Integer, defaultValue=300))

    def processAlgorithm(self, parameters, context, model_feedback):
        
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        outputs = {}
        
        tol = parameters['Tolerance']

        feedback.pushInfo('Preparing inputs...')
        feedback.pushInfo('')
        
        # Reproject GTFS layer
        alg_params = {
            'INPUT': parameters['GTFSlayer'],
            'OPERATION': '',
            'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:28355'),
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectGtfsLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, is_child_algorithm=True)

        # Reproject LINE layer
        alg_params = {
            'INPUT': parameters['LINElayer'],
            'OPERATION': '',
            'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:28355'),
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ReprojectLineLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, is_child_algorithm=True)

        # Refactor LINE route numbers
        alg_params = {
            'FIELD_LENGTH': 20,
            'FIELD_NAME': 'route_number',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,
            'FORMULA': 'if (right(route_id,1) = \'R\',route_id,concat(route_id,\'F\'))',
            'INPUT': outputs['ReprojectLineLayer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RefactorLineRouteNumbers'] = processing.run('native:fieldcalculator', alg_params, context=context, is_child_algorithm=True)

        # Extract LINE end-points
        alg_params = {
            'INPUT': outputs['RefactorLineRouteNumbers']['OUTPUT'],
            'VERTICES': '0,-1',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractLineEndpoints'] = processing.run('native:extractspecificvertices', alg_params, context=context, is_child_algorithm=True)

        # Split LINE by maximum length
        alg_params = {
            'INPUT': outputs['RefactorLineRouteNumbers']['OUTPUT'],
            'LENGTH': tol*2,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['SplitLineByMaximumLength'] = processing.run('native:splitlinesbylength', alg_params, context=context, is_child_algorithm=True)

        # Create LINE vertices along route
        alg_params = {
            'INPUT': outputs['SplitLineByMaximumLength']['OUTPUT'],
            'VERTICES': '0',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CreateLineVerticesAlongRoute'] = processing.run('native:extractspecificvertices', alg_params, context=context, is_child_algorithm=True)

        # Extract GTFS route numbers
        alg_params = {
            'FIELD_LENGTH': 20,
            'FIELD_NAME': 'route_number',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,
            'FORMULA': ' left( substr(route_id,3) ,strpos( substr(route_id,3),\'-\')-1)',
            'INPUT': outputs['ReprojectGtfsLayer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractGtfsRouteNumbers'] = processing.run('native:fieldcalculator', alg_params, context=context, is_child_algorithm=True)

        # Add geometry attributes
        alg_params = {
            'CALC_METHOD': 0,
            'INPUT': outputs['ExtractGtfsRouteNumbers']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AddGeometryAttributes'] = processing.run('qgis:exportaddgeometrycolumns', alg_params, context=context, is_child_algorithm=True)

        # Order by expression
        alg_params = {
            'ASCENDING': False,
            'EXPRESSION': '\"length\"',
            'INPUT': outputs['AddGeometryAttributes']['OUTPUT'],
            'NULLS_FIRST': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['OrderByExpression'] = processing.run('native:orderbyexpression', alg_params, context=context, is_child_algorithm=True)

        # Delete duplicates by attribute
        alg_params = {
            'FIELDS': ['route_number'],
            'INPUT': outputs['OrderByExpression']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DeleteDuplicatesByAttribute'] = processing.run('native:removeduplicatesbyattribute', alg_params, context=context, is_child_algorithm=True)

        # Extract GTFS end-points
        alg_params = {
            'INPUT': outputs['DeleteDuplicatesByAttribute']['OUTPUT'],
            'VERTICES': '0,-1',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractGtfsEndpoints'] = processing.run('native:extractspecificvertices', alg_params, context=context, is_child_algorithm=True)

        # Split GTFS by maximum length
        alg_params = {
            'INPUT': outputs['DeleteDuplicatesByAttribute']['OUTPUT'],
            'LENGTH': tol*2,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['SplitGtfsByMaximumLength'] = processing.run('native:splitlinesbylength', alg_params, context=context, is_child_algorithm=True)

        # Create GTFS vertices along route
        alg_params = {
            'INPUT': outputs['SplitGtfsByMaximumLength']['OUTPUT'],
            'VERTICES': '0',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CreateGtfsVerticesAlongRoute'] = processing.run('native:extractspecificvertices', alg_params, context=context, is_child_algorithm=True)

        # Merge end points
        alg_params = {
            'CRS': QgsCoordinateReferenceSystem('EPSG:28355'),
            'LAYERS': [outputs['ExtractGtfsEndpoints']['OUTPUT'],outputs['ExtractLineEndpoints']['OUTPUT']],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MergeEndPoints'] = processing.run('native:mergevectorlayers', alg_params, context=context, is_child_algorithm=True)
        
        # Merge points along route
        alg_params = {
            'CRS': QgsCoordinateReferenceSystem('EPSG:28355'),
            'LAYERS': [outputs['CreateGtfsVerticesAlongRoute']['OUTPUT'],outputs['CreateLineVerticesAlongRoute']['OUTPUT']],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MergePointsAlongRoute'] = processing.run('native:mergevectorlayers', alg_params, context=context, is_child_algorithm=True)

        unique_GTFS_routes = QgsProcessingUtils.mapLayerFromString(outputs['DeleteDuplicatesByAttribute']['OUTPUT'], context=context)
        unique_VITM_routes = QgsProcessingUtils.mapLayerFromString(outputs['RefactorLineRouteNumbers']['OUTPUT'], context=context)
        end_points = QgsProcessingUtils.mapLayerFromString(outputs['MergeEndPoints']['OUTPUT'], context=context)
        points_along_route = QgsProcessingUtils.mapLayerFromString(outputs['MergePointsAlongRoute']['OUTPUT'], context=context)
                
        matched_routes = []
        routes_not_in_VITM = []
        routes_not_in_GTFS = []
        additional_routes = []
        route_alignment_score = {}

        total_features = unique_GTFS_routes.featureCount()
        total_LINE_features = unique_VITM_routes.featureCount()
        counter = 1
        feedback.setProgress(1)
        
        feedback.pushInfo('Found ' + str(total_features) + ' GTFS routes and ' + str(total_LINE_features) + ' VITM routes...')
        feedback.pushInfo('')
        
        for route in unique_VITM_routes.getFeatures():
            routeID = route['route_number']
            trueID = routeID
            if trueID[-1] == 'F':
                trueID = trueID[:-1]
            unique_GTFS_routes.setSubsetString('"route_number" = \''+routeID[:-1]+'\'')
            filtered_features = unique_GTFS_routes.featureCount()
            if filtered_features == 0:
                if trueID not in routes_not_in_GTFS:
                    routes_not_in_GTFS.append(trueID)
            else:
                matched_routes.append(trueID)

        unique_GTFS_routes.setSubsetString('')
                
        for route in unique_GTFS_routes.getFeatures():
            routeID = route['route_number']
            unique_VITM_routes.setSubsetString('"route_number" IN (\''+routeID+'F\',\''+routeID+'R\')')
            filtered_features = unique_VITM_routes.featureCount()
            if filtered_features == 0:
                routes_not_in_VITM.append(routeID)

        unique_VITM_routes.setSubsetString('')

        feedback.pushInfo('GTFS routes not found in VITM:')
        feedback.pushInfo(', '.join(sorted(routes_not_in_VITM)))
        feedback.pushInfo('Total: ' + str(len(routes_not_in_VITM)))
        feedback.pushInfo('')        

        feedback.pushInfo('Total VITM routes not found in GTFS:')
        feedback.pushInfo(', '.join(sorted(routes_not_in_GTFS)))
        feedback.pushInfo('Total: ' + str(len(routes_not_in_GTFS)))
        feedback.pushInfo('')

        feedback.pushInfo('Processing matched routes...')
        feedback.pushInfo('Total: '+str(len(matched_routes)))
        feedback.pushInfo('')

        for route in unique_GTFS_routes.getFeatures():
            routeID = route['route_number']
            IDs = [routeID+'F',routeID+'R']
            counter += 1
            feedback.setProgress(math.ceil((float(counter) / float(total_features)) * 100))
            for ID in IDs:
                trueID = ID
                if trueID[-1] == 'F':
                    trueID = trueID[:-1]
                end_points.setSubsetString('"route_number" IN (\''+routeID+'\',\''+ID+'\')')
                filtered_features = end_points.featureCount()
                if filtered_features == 2:
                    continue

                # Cluster end points
                alg_params = {
                    'DBSCAN*': False,
                    'EPS': tol,
                    'FIELD_NAME': 'CLUSTER_ID',
                    'INPUT': outputs['MergeEndPoints']['OUTPUT'],
                    'MIN_SIZE': 2,
                    'SIZE_FIELD_NAME': 'CLUSTER_SIZE',
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['ClusterEndPoints'] = processing.run('native:dbscanclustering', alg_params, context=context, is_child_algorithm=True)
                
                cluster_ends = QgsProcessingUtils.mapLayerFromString(outputs['ClusterEndPoints']['OUTPUT'], context=context)
                
                points_along_route.setSubsetString('"route_number" IN (\''+routeID+'\',\''+ID+'\')')
                total_points_along_route = points_along_route.featureCount()
                
                # Cluster end points
                alg_params = {
                    'DBSCAN*': False,
                    'EPS': tol,
                    'FIELD_NAME': 'CLUSTER_ID',
                    'INPUT': outputs['MergePointsAlongRoute']['OUTPUT'],
                    'MIN_SIZE': 2,
                    'SIZE_FIELD_NAME': 'CLUSTER_SIZE',
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }
                outputs['ClusterPointsAlongRoute'] = processing.run('native:dbscanclustering', alg_params, context=context, is_child_algorithm=True)
                
                cluster_route = QgsProcessingUtils.mapLayerFromString(outputs['ClusterPointsAlongRoute']['OUTPUT'], context=context)
                
                in_cluster = 0
                for feat in cluster_route.getFeatures():
                    clusterID = feat['CLUSTER_ID']
                    if clusterID is not None:
                        in_cluster += 1

                ends_matched = 0
                for feat in cluster_ends.getFeatures():
                    clusterID = feat['CLUSTER_ID']
                    if clusterID is not None and clusterID > ends_matched:
                        ends_matched = clusterID

                route_alignment_score[trueID] = {'ends':str(ends_matched),'route':str(round(100 * float(in_cluster) / float(total_points_along_route)))}

        feedback.pushInfo('Route alignment scores:')
        for route in sorted(route_alignment_score.keys()):
            feedback.pushInfo(route + ': ' + route_alignment_score[route]['route'] + '% (' + route_alignment_score[route]['ends'] + ' ends matched)')
        feedback.pushInfo('')
        
        end_points.setSubsetString('')
                    
        return results

    def name(self):
        return 'Compare GTFS and LINE routes'

    def displayName(self):
        return 'Compare GTFS and LINE routes'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return Model()
