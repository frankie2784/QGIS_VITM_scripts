"""
Model exported as python.
Name : generate_shp_from_osm
Group : 
With QGIS : 32203
"""

from qgis.core import QgsProcessing, QgsProcessingParameterField, QgsProcessingParameterString, QgsProcessingParameterNumber
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsCoordinateReferenceSystem
import processing


class Generate_shp_from_osm(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('osmleft', 'OSM left', types=[QgsProcessing.TypeVectorLine], defaultValue='osm_line left proper'))
        self.addParameter(QgsProcessingParameterString('leftcategories', 'Left categories', multiLine=False, defaultValue='CASE\r\nWHEN map_get("tags",\'bicycle\') = \'no\' THEN \'cycling not permitted\'\r\nWHEN map_get("tags",\'highway\') = \'cycleway\' and map_get("tags",\'foot\') = \'no\' THEN \'exclusive off-road track\'\r\nWHEN map_get("tags",\'highway\') = \'cycleway\' THEN \'shared off-road track\'\r\nWHEN map_get("tags",\'cyclestreet\') = \'yes\' THEN \'bike boulevard\'\r\nWHEN map_get("tags",\'highway\') = \'living_street\' THEN \'living street\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'track\' THEN \'separated lane\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'track\' and map_exist("tags",\'cycleway:right\') THEN \'separated lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'lane\' and (map_get("tags",\'cycleway:both:lane\') = \'exclusive\' or map_get("tags",\'cycleway:left:lane\') = \'exclusive\') and (strpos(array_to_string(map_akeys("tags")),\'left:buffer\') > 0 or strpos(array_to_string(map_akeys("tags")),\'both:buffer\') > 0) THEN \'buffered lane\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'lane\' and map_get("tags",\'cycleway:left:lane\') = \'exclusive\' and map_exist("tags",\'cycleway:right\') and strpos(array_to_string(map_akeys("tags")),\'left:buffer\') > 0 THEN \'buffered lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'lane\' and (map_get("tags",\'cycleway:both:lane\') = \'advisory\' or map_get("tags",\'cycleway:left:lane\') = \'advisory\') THEN \'advisory lane\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'lane\' and map_exist("tags",\'cycleway:right\') and map_get("tags",\'cycleway:left:lane\') = \'advisory\' THEN \'advisory lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'lane\' and (map_get("tags",\'cycleway:both:lane\') = \'exclusive\' or map_get("tags",\'cycleway:left:lane\') = \'exclusive\') THEN \'painted lane\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'lane\' and map_get("tags",\'cycleway:left:lane\') = \'exclusive\' and map_exist("tags",\'cycleway:right\') THEN \'painted lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'share_busway\' THEN \'shared busway\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'share_busway\' and map_exist("tags",\'cycleway:right\') THEN \'shared busway\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'shared_lane\' and (map_get("tags",\'cycleway:both:lane\') = \'pictogram\' or map_get("tags",\'cycleway:left:lane\') = \'pictogram\') THEN \'sharrows\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'shared_lane\' and map_exist("tags",\'cycleway:right\') and map_get("tags",\'cycleway:left:lane\') = \'pictogram\' THEN \'sharrows\'\r\nWHEN ((map_get("tags",\'bicycle\') = \'designated\' or map_get("tags",\'bicycle\') = \'yes\' or map_get("tags",\'bicycle\') = \'dismount\') and (map_get("tags",\'highway\') = \'footway\' or map_get("tags",\'highway\') = \'service\' or map_get("tags",\'highway\') = \'sidewalk\')) or (map_get("tags",\'highway\') = \'path\' and (not map_exist("tags",\'bicycle\') or not map_get("tags",\'bicycle\') = \'no\')) THEN \'shared off-road track\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'no\' THEN \'no lane\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'no\' and map_exist("tags",\'cycleway:right\') THEN \'no lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'separate\' THEN \'mapped separately\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'separate\' and map_exist("tags",\'cycleway:right\') THEN \'mapped separately\'\r\nWHEN map_get("tags",\'bicycle\') = \'use_sidepath\' THEN \'mapped separately\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'shoulder\' THEN \'shoulder cyclable\'\r\nWHEN map_get("tags",\'cycleway:left\') = \'shoulder\' and map_exist("tags",\'cycleway:right\') THEN \'shoulder cyclable\'\r\nWHEN map_get("tags",\'highway\') in (\'footway\',\'sidewalk\') THEN \'footway\'\r\nWHEN map_exist("tags",\'cycleway:both\') or map_exist("tags",\'cycleway:left\') THEN \'other cycleway\'\r\nWHEN map_get("tags",\'highway\') = \'pedestrian\' THEN \'pedestrian street\'\r\nELSE \'missing\'\r\nEND'))
        self.addParameter(QgsProcessingParameterVectorLayer('osmright', 'OSM right', types=[QgsProcessing.TypeVectorLine], defaultValue='osm_line right proper'))
        self.addParameter(QgsProcessingParameterString('rightcategories', 'Right categories', multiLine=False, defaultValue='CASE\r\nWHEN map_get("tags",\'bicycle\') = \'no\' THEN \'cycling not permitted\'\r\nWHEN map_get("tags",\'highway\') = \'cycleway\' and map_get("tags",\'foot\') = \'no\' THEN \'exclusive off-road track\'\r\nWHEN map_get("tags",\'highway\') = \'cycleway\' THEN \'shared off-road track\'\r\nWHEN map_get("tags",\'cyclestreet\') = \'yes\' THEN \'bike boulevard\'\r\nWHEN map_get("tags",\'highway\') = \'living_street\' THEN \'living street\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'track\' THEN \'separated lane\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'track\' and map_exist("tags",\'cycleway:left\') THEN \'separated lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'lane\' and (map_get("tags",\'cycleway:both:lane\') = \'exclusive\' or map_get("tags",\'cycleway:right:lane\') = \'exclusive\') and (strpos(array_to_string(map_akeys("tags")),\'both:buffer\') > 0 or strpos(array_to_string(map_akeys("tags")),\'right:buffer\') > 0) THEN \'buffered lane\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'lane\' and map_exist("tags",\'cycleway:left\') and strpos(array_to_string(map_akeys("tags")),\'right:buffer\') > 0 THEN \'buffered lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'lane\' and (map_get("tags",\'cycleway:both:lane\') = \'advisory\' or map_get("tags",\'cycleway:right:lane\') = \'advisory\') THEN \'advisory lane\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'lane\' and map_exist("tags",\'cycleway:left\') and map_get("tags",\'cycleway:right:lane\') = \'advisory\' THEN \'advisory lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'lane\' and (map_get("tags",\'cycleway:both:lane\') = \'exclusive\' or map_get("tags",\'cycleway:right:lane\') = \'exclusive\') THEN \'painted lane\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'lane\' and map_exist("tags",\'cycleway:left\') and map_get("tags",\'cycleway:right:lane\') = \'exclusive\' THEN \'painted lane\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'share_busway\' THEN \'shared busway\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'share_busway\' and map_exist("tags",\'cycleway:left\') THEN \'shared busway\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'shared_lane\' and (map_get("tags",\'cycleway:both:lane\') = \'pictogram\' or map_get("tags",\'cycleway:right:lane\') = \'pictogram\') THEN \'sharrows\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'shared_lane\' and map_exist("tags",\'cycleway:left\') and map_get("tags",\'cycleway:right:lane\') = \'pictogram\' THEN \'sharrows\'\r\nWHEN (map_get("tags",\'bicycle\') = \'designated\' or map_get("tags",\'bicycle\') = \'yes\' or map_get("tags",\'bicycle\') = \'dismount\') and (map_get("tags",\'highway\') = \'footway\' or map_get("tags",\'highway\') = \'path\' or map_get("tags",\'highway\') = \'service\') THEN \'shared off-road track\'\r\nWHEN (map_get("tags",\'oneway\') = \'yes\' and map_get("tags",\'oneway:bicycle\') = \'no\') and (map_get("tags",\'cycleway:both\') = \'no\' or map_get("tags",\'cycleway:right\') = \'no\') THEN \'no lane, cycling permitted in reverse direction\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'no\' THEN \'no lane\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'no\' and map_exist("tags",\'cycleway:left\') THEN \'no lane\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'separate\' and map_exist("tags",\'cycleway:left\') THEN \'mapped separately\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'separate\' THEN \'mapped separately\'\r\nWHEN map_get("tags",\'cycleway:right\') = \'shoulder\' and map_exist("tags",\'cycleway:left\') THEN \'shoulder cyclable\'\r\nWHEN map_get("tags",\'cycleway:both\') = \'shoulder\' THEN \'shoulder cyclable\'\r\nWHEN map_exist("tags",\'cycleway:both\') or map_exist("tags",\'cycleway:right\') THEN \'other cycleway\'\r\nELSE \'missing\'\r\nEND'))
        self.addParameter(QgsProcessingParameterVectorLayer('arealayer', 'Area filter layer', types=[QgsProcessing.TypeVectorPolygon], defaultValue='LGA_2021'))
        self.addParameter(QgsProcessingParameterField('areafilter', 'Area filter field', type=QgsProcessingParameterField.String, parentLayerParameterName='arealayer', allowMultiple=False, defaultValue='LGA_NAME21'))
        self.addParameter(QgsProcessingParameterString('inputvalue', 'Area filter value', multiLine=False, defaultValue=''))
        self.addParameter(QgsProcessingParameterNumber('buffersize', 'Buffer size (metres)', type=QgsProcessingParameterNumber.Integer, defaultValue=200))
        self.addParameter(QgsProcessingParameterNumber('offset', 'Offset (metres)', type=QgsProcessingParameterNumber.Integer, defaultValue=1))
        self.addParameter(QgsProcessingParameterString('OutputLayer', 'Output Layer', multiLine=False, defaultValue='OSM_to_SHP'))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(23, model_feedback)
        results = {}
        outputs = {}
        
        feedback.pushInfo('Creating overlay for filtering')
        # Extract by attribute
        alg_params = {
            'FIELD': parameters['areafilter'],
            'INPUT': parameters['arealayer'],
            'OPERATOR': 0,  # =
            'VALUE': parameters['inputvalue'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractByAttribute'] = processing.run('native:extractbyattribute', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': parameters['buffersize'],
            'END_CAP_STYLE': 0,  # Round
            'INPUT': outputs['ExtractByAttribute']['OUTPUT'],
            'JOIN_STYLE': 0,  # Round
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        feedback.pushInfo('Generating fields')
        feedback.pushInfo('Left cycleways')
        # left generate lane categories
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'tags',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # String
            'FORMULA': parameters['leftcategories'],
            'INPUT': parameters['osmleft'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftGenerateLaneCategories'] = processing.run('native:fieldcalculator', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}
        
        # Rename field
        alg_params = {
            'FIELD': 'tags',
            'INPUT': outputs['LeftGenerateLaneCategories']['OUTPUT'],
            'NEW_NAME': 'cycleway',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftRenameCyclewayField'] = processing.run('native:renametablefield', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo('Left road names')
        # left generate name
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'tags',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # String
            'FORMULA': 'map_get("tags",\'name\')',
            'INPUT': parameters['osmleft'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftGenerateName'] = processing.run('native:fieldcalculator', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Rename field
        alg_params = {
            'FIELD': 'tags',
            'INPUT': outputs['LeftGenerateName']['OUTPUT'],
            'NEW_NAME': 'name',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftRenameNameField'] = processing.run('native:renametablefield', alg_params, context=context, is_child_algorithm=True)
        
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo('Right cycleways')
        # right generate lane categories
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'tags',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # String
            'FORMULA': parameters['rightcategories'],
            'INPUT': parameters['osmright'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightGenerateLaneCategories'] = processing.run('native:fieldcalculator', alg_params, context=context, is_child_algorithm=True)
        
        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}
        
        # Rename field
        alg_params = {
            'FIELD': 'tags',
            'INPUT': outputs['RightGenerateLaneCategories']['OUTPUT'],
            'NEW_NAME': 'cycleway',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightRenameCyclewayField'] = processing.run('native:renametablefield', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo('Right road names')
        # right generate name
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'tags',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # String
            'FORMULA': 'map_get("tags",\'name\')',
            'INPUT': parameters['osmright'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightGenerateName'] = processing.run('native:fieldcalculator', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(9)
        if feedback.isCanceled():
            return {}

        # Rename field
        alg_params = {
            'FIELD': 'tags',
            'INPUT': outputs['RightGenerateName']['OUTPUT'],
            'NEW_NAME': 'name',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightRenameNameField'] = processing.run('native:renametablefield', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(10)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo('Filtering and clipping layers')  
        # Extract by expression
        alg_params = {
            'EXPRESSION': "cycleway not in ('missing','other cycleway','opposite side')",
            'INPUT': outputs['LeftRenameCyclewayField']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftExtractByExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(11)
        if feedback.isCanceled():
            return {}
        
        # Clip
        alg_params = {
            'INPUT': outputs['LeftExtractByExpression']['OUTPUT'],
            'OVERLAY': outputs['Buffer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftClip'] = processing.run('native:clip', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(12)
        if feedback.isCanceled():
            return {}
        
        # Join attributes by field value
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'FIELD': 'osm_id',
            'FIELDS_TO_COPY': ['name'],
            'FIELD_2': 'osm_id',
            'INPUT': outputs['LeftClip']['OUTPUT'],
            'INPUT_2': outputs['LeftRenameNameField']['OUTPUT'],
            'METHOD': 1,  # Take attributes of the first matching feature only (one-to-one)
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftJoinAttributesByFieldValue'] = processing.run('native:joinattributestable', alg_params, context=context, is_child_algorithm=True)
        
        feedback.setCurrentStep(13)
        if feedback.isCanceled():
            return {}

        # Extract by expression
        alg_params = {
            'EXPRESSION': "cycleway not in ('missing','other cycleway','opposite side')",
            'INPUT': outputs['RightRenameCyclewayField']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightExtractByExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(14)
        if feedback.isCanceled():
            return {}

        # Clip
        alg_params = {
            'INPUT': outputs['RightExtractByExpression']['OUTPUT'],
            'OVERLAY': outputs['Buffer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightClip'] = processing.run('native:clip', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(15)
        if feedback.isCanceled():
            return {}
        
        # Join attributes by field value
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'FIELD': 'osm_id',
            'FIELDS_TO_COPY': ['name'],
            'FIELD_2': 'osm_id',
            'INPUT': outputs['RightClip']['OUTPUT'],
            'INPUT_2': outputs['RightRenameNameField']['OUTPUT'],
            'METHOD': 1,  # Take attributes of the first matching feature only (one-to-one)
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightJoinAttributesByFieldValue'] = processing.run('native:joinattributestable', alg_params, context=context, is_child_algorithm=True)
        
        feedback.setCurrentStep(16)
        if feedback.isCanceled():
            return {}
        

        feedback.pushInfo('Reprojecting and offsetting layers')
        # # left reproject
        alg_params = {
            'INPUT': outputs['LeftJoinAttributesByFieldValue']['OUTPUT'],
            'OPERATION': '',
            'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:7899'),
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftReproject'] = processing.run('native:reprojectlayer', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(17)
        if feedback.isCanceled():
            return {}
        
        # left offset
        alg_params = {
            'DISTANCE': parameters['offset'],
            'INPUT': outputs['LeftReproject']['OUTPUT'],
            'JOIN_STYLE': 0,  # Round
            'MITER_LIMIT': 2,
            'SEGMENTS': 8,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['LeftOffset'] = processing.run('native:offsetline', alg_params, context=context, is_child_algorithm=True)
        
        feedback.setCurrentStep(18)
        if feedback.isCanceled():
            return {}
        
        # right reproject
        alg_params = {
            'INPUT': outputs['RightJoinAttributesByFieldValue']['OUTPUT'],
            'OPERATION': '',
            'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:7899'),
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightReproject'] = processing.run('native:reprojectlayer', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(19)
        if feedback.isCanceled():
            return {}
        
        # right offset
        alg_params = {
            'DISTANCE': parameters['offset']*-1,
            'INPUT': outputs['RightReproject']['OUTPUT'],
            'JOIN_STYLE': 0,  # Round
            'MITER_LIMIT': 2,
            'SEGMENTS': 8,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RightOffset'] = processing.run('native:offsetline', alg_params, context=context, is_child_algorithm=True)

        feedback.setCurrentStep(20)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo('Merging layers')
        # Merge vector layers
        alg_params = {
            'CRS': QgsCoordinateReferenceSystem('EPSG:7899'),
            'LAYERS': [outputs['LeftOffset']['OUTPUT'], outputs['RightOffset']['OUTPUT']],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MergeVectorLayers'] = processing.run('native:mergevectorlayers', alg_params, context=context, is_child_algorithm=True)
        
        feedback.setCurrentStep(21)
        if feedback.isCanceled():
            return {}
        
        # Drop field(s)
        alg_params = {
            'COLUMN': ['layer','path'],
            'INPUT': outputs['MergeVectorLayers']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DropFields'] = processing.run('native:deletecolumn', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(22)
        if feedback.isCanceled():
            return {}
        
        # Load layer into project
        alg_params = {
            'INPUT': outputs['DropFields']['OUTPUT'],
            'NAME': parameters['OutputLayer']
        }
        outputs['LoadLayerIntoProject'] = processing.run('native:loadlayer', alg_params, context=context, is_child_algorithm=True)

        
        return results

    def name(self):
        return 'generate_shp_from_osm'

    def displayName(self):
        return 'Generate SHP from OSM'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return Generate_shp_from_osm()
