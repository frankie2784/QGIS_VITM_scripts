"""
Model exported as python.
Name : Isochrone coverage
Group : 
With QGIS : 32203
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterFeatureSink
import processing


class Model(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('inputlayer', 'Input layer', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('coveragethreshold0100', '% coverage threshold (0-100)', type=QgsProcessingParameterNumber.Double, minValue=0, maxValue=100, defaultValue=50))
        self.addParameter(QgsProcessingParameterField('geographytoaggregate', 'Geography to aggregate', type=QgsProcessingParameterField.Any, parentLayerParameterName='inputlayer', allowMultiple=False, defaultValue='LGA_NAME21'))
        self.addParameter(QgsProcessingParameterField('coveragefield', '% coverage field', type=QgsProcessingParameterField.Numeric, parentLayerParameterName='inputlayer', allowMultiple=True, defaultValue='40mins_pc;50mins_pc;60mins_pc'))
        self.addParameter(QgsProcessingParameterFeatureSink('Out', 'OUT', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        
        num_iters = len(parameters['coveragefield'])
        feedback = QgsProcessingMultiStepFeedback(1 + 5*num_iters, model_feedback)
        results = {}
        outputs = {}

        # Total MB
        alg_params = {
            'CATEGORIES_FIELD_NAME': parameters['geographytoaggregate'],
            'INPUT': parameters['inputlayer'],
            'VALUES_FIELD_NAME': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['TotalMb'] = processing.run('qgis:statisticsbycategories', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        outputs['JoinAttributesByFieldValue'] = outputs['TotalMb']
        
        step_counter = 2
        for field in parameters['coveragefield']:
            # Extract by attribute
            alg_params = {
                'FIELD': field,
                'INPUT': parameters['inputlayer'],
                'OPERATOR': 3,  # ≥
                'VALUE': parameters['coveragethreshold0100'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['ExtractByAttribute'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(step_counter)
            if feedback.isCanceled():
                return {}
            
            step_counter += 1
            
            # Filtered MB
            alg_params = {
                'CATEGORIES_FIELD_NAME': parameters['geographytoaggregate'],
                'INPUT': outputs['ExtractByAttribute']['OUTPUT'],
                'VALUES_FIELD_NAME': '',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['FilteredMb'] = processing.run('qgis:statisticsbycategories', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(step_counter)
            if feedback.isCanceled():
                return {}
                
            step_counter += 1

            # Join attributes by field value
            alg_params = {
                'DISCARD_NONMATCHING': False,
                'FIELD': parameters['geographytoaggregate'],
                'FIELDS_TO_COPY': ['count'],
                'FIELD_2': parameters['geographytoaggregate'],
                'INPUT': outputs['JoinAttributesByFieldValue']['OUTPUT'],
                'INPUT_2': outputs['FilteredMb']['OUTPUT'],
                'METHOD': 1,  # Take attributes of the first matching feature only (one-to-one)
                'PREFIX': f'{field[:-3]}_',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['JoinAttributesByFieldValue'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(step_counter)
            if feedback.isCanceled():
                return {}

            step_counter += 1
            
            # Field calculator
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': f'{field[:-3]}_count',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 0,  # Float
                'FORMULA': f'if(\"{field[:-3]}_count\" is NULL,0,\"{field[:-3]}_count\")',
                'INPUT': outputs['JoinAttributesByFieldValue']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['JoinAttributesByFieldValue'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(step_counter)
            if feedback.isCanceled():
                return {}

            step_counter += 1
            
            # Field calculator
            alg_params = {
                'FIELD_LENGTH': 0,
                'FIELD_NAME': f'{field[:-3]}_%_mb_covered',
                'FIELD_PRECISION': 0,
                'FIELD_TYPE': 0,  # Float
                'FORMULA': f'round(100*\"{field[:-3]}_count\" / \"count\",2)',
                'INPUT': outputs['JoinAttributesByFieldValue']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['JoinAttributesByFieldValue'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

            feedback.setCurrentStep(step_counter)
            if feedback.isCanceled():
                return {}

            step_counter += 1
            
        # Field calculator
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'count',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 1,  # Integer
            'FORMULA': 'count',
            'INPUT': outputs['JoinAttributesByFieldValue']['OUTPUT'],
            'OUTPUT': parameters['Out']
        }
        outputs['JoinAttributesByFieldValue'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            
        results['Out'] = outputs['JoinAttributesByFieldValue']['OUTPUT']
        return results

    def name(self):
        return 'Isochrone coverage'

    def displayName(self):
        return 'Isochrone coverage'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return Model()
