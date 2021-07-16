"""
Model exported as python.
Name : model
Group : 
With QGIS : 32000
"""

from qgis.core import QgsProcessing, QgsProcessingUtils
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterMapLayer
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsGeometry, QgsPointXY
import processing, math


class Model(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMapLayer('LineLayer', 'Line Layer', defaultValue=None, types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterMapLayer('IntersectingLines', 'Intersecting Lines', defaultValue=None, types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterNumber('MinimumIntersectionAngle', 'Minimum Intersection Angle', type=QgsProcessingParameterNumber.Double, minValue=0, maxValue=90, defaultValue=45))
        self.addParameter(QgsProcessingParameterDistance('MinimumIntersectingDistance', 'Minimum Intersecting Distance', parentParameterName='LineLayer', minValue=0, defaultValue=0))
        self.addParameter(QgsProcessingParameterFeatureSink('OUTPUT', 'Segmented Lines', type=QgsProcessing.TypeVectorLine, createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        outputs = {}
        
        intersectingAsLayer = QgsProcessingUtils.mapLayerFromString(parameters['IntersectingLines'], context=context)
        intersectingCRS = intersectingAsLayer.sourceCrs()
        
        # Reproject lines layer to same CRS as intersecting layer
        alg_params = {
            'INPUT': parameters['LineLayer'],
            'OPERATION': '',
            'TARGET_CRS': intersectingCRS,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LineLayer'] = processing.run('native:reprojectlayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        linesAsLayer = QgsProcessingUtils.mapLayerFromString(outputs['LineLayer']['OUTPUT'], context=context)
        
        for lineFeat in linesAsLayer.getFeatures():
            lineGeometry = lineFeat.geometry()
            lineGeometryEngine = QgsGeometry.createGeometryEngine(lineGeometry.constGet())
            lineGeometryEngine.prepareGeometry()
            validInts = []
            
            feedback.pushInfo("Finding intersections along " + lineFeat['layer'])
            for intFeat in intersectingAsLayer.getFeatures():
                
                intFeatGeometry = intFeat.geometry()
                if lineGeometryEngine.intersects(intFeatGeometry.constGet()):
                    feedback.pushInfo("Found intersection.")
                    
                    # Get the intersection location(s)
                    ints = lineGeometryEngine.intersection(intFeatGeometry.constGet())
                    
                    # Get the distance to the intersecting location
                    lineDistInt = lineFeat.geometry().distance(QgsGeometry.fromPointXY(QgsPointXY(ints)))
                    intDistLine = intFeat.geometry().distance(lineGeometry)
                    
                    # Get the angle of the lines at that location
                    thetaLine = lineGeometry.interpolateAngle(lineDistInt)
                    thetaInt = intFeatGeometry.interpolateAngle(intDistLine)
                    
                    # Determine the intersection angle
                    theta = abs(thetaLine - thetaInt)*180/math.pi
                    if theta > 180:
                        theta = abs(180 - theta)
                    
                    # Add the intersecting point to the point array if it meets the conditions
                    if theta >= parameters['MinimumIntersectionAngle']:
                        validInts.append(ints)
                    
            feedback.pushInfo("Intersection count for " + lineFeat['layer'] + ": " + str(len(validInts)))
            if feedback.isCanceled():
                return {}
            
        return {}

        # Line intersections
        alg_params = {
            'INPUT': parameters['LineLayer'],
            'INPUT_FIELDS': [''],
            'INTERSECT': parameters['IntersectingLines'],
            'INTERSECT_FIELDS': [''],
            'INTERSECT_FIELDS_PREFIX': '',
            'OUTPUT': parameters['SegmentedLines']
        }
        outputs['LineIntersections'] = processing.run('native:lineintersections', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['OUTPUT'] = outputs['LineIntersections']['OUTPUT']
        return results

    def name(self):
        return 'Segment by Intersection'

    def displayName(self):
        return 'Segment by Intersection'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return Model()
