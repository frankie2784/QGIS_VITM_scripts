"""
QGIS : 31802
"""

from qgis.core import QgsProject, QgsProcessingAlgorithm, QgsMapLayerType

class ClearAllFiltersAndSelections(QgsProcessingAlgorithm):
    
    def initAlgorithm(self, config=None):
        None

    def processAlgorithm(self, parameters, context, model_feedback):
        results = {}

        for layer in QgsProject().instance().mapLayers().values():
            if layer.type() != QgsMapLayerType.RasterLayer:
                layer.setSubsetString('')
                layer.removeSelection()

        return results

    def name(self):
        return 'Clear all filters and selections'

    def displayName(self):
        return 'Clear all filters and selections'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return ClearAllFiltersAndSelections()