"""
QGIS : 31802
"""

from qgis.core import QgsProject, QgsProcessingAlgorithm, QgsMapLayerType, QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsProcessingUtils
from qgis.core import QgsProcessing
from qgis.utils import iface

class FilterTwoLayersToRoute(QgsProcessingAlgorithm):
    
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('Layer1', 'Layer 1', types=[QgsProcessing.TypeVectorLine], defaultValue='NEL_routes'))
        self.addParameter(QgsProcessingParameterField('RouteIDLayer1', 'Route ID field - Layer 1', type=QgsProcessingParameterField.Any, parentLayerParameterName='Layer1', allowMultiple=False, defaultValue='ROUTESHTNM'))
        self.addParameter(QgsProcessingParameterVectorLayer('Layer2', 'Layer 2', types=[QgsProcessing.TypeVectorLine], defaultValue='LINE import'))
        self.addParameter(QgsProcessingParameterField('RouteIDLayer2', 'Route ID field - Layer 2', type=QgsProcessingParameterField.Any, parentLayerParameterName='Layer2', allowMultiple=False, defaultValue='route_id'))
        self.addParameter(QgsProcessingParameterString('RouteID', 'Route ID', multiLine=False, defaultValue=''))

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)
        results = {}
        
        layer1 = QgsProcessingUtils.mapLayerFromString(parameters['Layer1'], context=context)
        layer2 = QgsProcessingUtils.mapLayerFromString(parameters['Layer2'], context=context)
        field1 = parameters['RouteIDLayer1']
        field2 = parameters['RouteIDLayer2']
        routeID = parameters['RouteID']
        
        layers = [layer1,layer2]
        fields = [field1,field2]
        routeIDs = ['\''+routeID+'\'','\'E'+routeID+'\'','\'W'+routeID+'\'','\'N'+routeID+'\'','\''+routeID+'R\'','\'E'+routeID+'R\'','\'W'+routeID+'R\'','\'N'+routeID+'R\'','\''+''.join(r for r in routeID if r.isdigit())+'\'',''.join(r for r in routeID if r.isdigit())]

        layer_features = [0,0]
        for i in range(2):
            for ID in routeIDs:
                try:
                    layers[i].setSubsetString(fields[i]+'='+ID)
                    filtered_features = layers[i].featureCount()
                    layer_features[i] = filtered_features
                    if filtered_features == 0:
                        continue
                    else:
                        break
                except:
                    None

        if sum(layer_features) == 0:
            feedback.pushInfo('Error: No routes found. Please ensure the route you entered is valid and available in the selected layers.')
            feedback.pushInfo('')
            return results
        
        canvas = iface.mapCanvas()
        
        if layer_features[0] == 0:
            feedback.pushInfo('Error: No routes found in layer 1. Please ensure the route you entered is valid and available in the selected layer.')
            feedback.pushInfo('')
            extent = layer2.extent()
            canvas.setExtent(extent)
            
        elif layer_features[1] == 0:
            feedback.pushInfo('Error: No routes found in layer 2. Please ensure the route you entered is valid and available in the selected layer.')
            feedback.pushInfo('')
            extent = layer1.extent()
            canvas.setExtent(extent)
        
        else:
            extent = layer1.extent()
            canvas.setExtent(extent)
            
        return results

    def name(self):
        return 'Filter two layers to route'

    def displayName(self):
        return 'Filter two layers to route'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return FilterTwoLayersToRoute()