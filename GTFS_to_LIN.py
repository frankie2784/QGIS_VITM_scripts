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
from qgis.core import QgsProcessingUtils
from qgis.core import QgsCoordinateReferenceSystem
import processing


class Model(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterMapLayer('GTFSNetwork', 'GTFS Network', defaultValue=None, types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterMapLayer('SVITMNetwork', 'S-VITM Network', defaultValue=None, types=[QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFile('HeadwayCSVFile', 'Headways', optional=True, behavior=QgsProcessingParameterFile.File, fileFilter='CSV Files (*.csv)', defaultValue=None))
        self.addParameter(QgsProcessingParameterEnum('TransportMode', 'Transport Mode', options=['Bus','Tram','Train'], allowMultiple=False, usesStaticStrings=False, defaultValue=[]))
        self.addParameter(QgsProcessingParameterString('RouteSuffix', 'Route Suffix', multiLine=False, defaultValue='_'))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        outputs = {}
        
        #Load input layers into memory
        feedback.pushInfo('Loading input layers into memory...')
        gtfsLayer = QgsProcessingUtils.mapLayerFromString(parameters['GTFSNetwork'], context=context)
        vitmLayer = QgsProcessingUtils.mapLayerFromString(parameters['SVITMNetwork'], context=context)
        
        #Update filter for VITM network layer
        feedback.pushInfo('Adjusting filters from VITM network layer...')
        vitmOrigQuery = vitmLayer.subsetString()
        feedback.pushInfo('Original filter: ' + vitmOrigQuery)
        switchBlock = {
        'Bus': 'LINKCLASS NOT IN (-1, 0, 1, 42, 43, 45, 46, 47, 48, 49)',
        'Tram': 'LINKCLASS NOT IN (-1, 0, 1, 42, 44, 45, 46, 47, 48, 49)',
        'Train': 'LINKCLASS NOT IN (-1, 0, 1, 43, 44, 45, 46, 47, 48, 49)',
        }
        vitmLayer.setSubsetString(switchBlock.get(parameters['TransportMode'], ''))
        
        #Check the input layers for lines (i.e. they aren't all filtered out)
        feedback.pushInfo('Checking input layers for valid inputs...')
        if gtfsLayer.featureCount() == 0:
            feedback.pushInfo('ERROR: No features found in GTFS input layer. exiting...')
            vitmLayer.setSubsetString(vitmOrigQuery)
            return
        if vitmLayer.featureCount() == 0:
            feedback.pushInfo('ERROR: No features found in VITM network layer. exiting...')
            vitmLayer.setSubsetString(vitmOrigQuery)
            return
        vitmReqAttr = ['A', 'B', 'LINKCLASS']
        if all( i in vitmLayer.attributeAliases() for i in vitmReqAttr):
            feedback.pushInfo('Input layer checks passed.')
        else:
            feedback.pushInfo('ERROR: VITM network requires A, B and LINKCLASS attributes.')
            vitmLayer.setSubsetString(vitmOrigQuery)
            feedback.pushInfo('Available attributes: ' + ', '.join(vitmLayer.attributeAliases()))
            return

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
        gtfsReprojected = outputs['ReprojectLayer']['OUTPUT']
        
        
        
        return results

    def name(self):
        return 'Generate LIN from GTFS'

    def displayName(self):
        return 'Generate LIN from GTFS'

    def group(self):
        return 'VITM'

    def groupId(self):
        return ''

    def createInstance(self):
        return Model()
