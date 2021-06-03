"""
QGIS : 31802
"""

from qgis.core import QgsProject
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingUtils
from qgis.core import QgsPoint, QgsFeature, QgsGeometry, QgsVectorLayer
from qgis.core import QgsLineString, QgsMultiLineString
import processing
import math
        
class GenerateSpatialLayerFromLinesFile(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):

        self.addParameter(QgsProcessingParameterFile('Lines', 'VITM lines file', behavior=QgsProcessingParameterFile.File, fileFilter='All Files (*.*)', defaultValue=None))
        self.addParameter(QgsProcessingParameterVectorLayer('Network', 'Network layer', types=[QgsProcessing.TypeVectorLine], defaultValue=None))
            
    def processAlgorithm(self, parameters, context, model_feedback):
        
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)

        errors = []
        results = {}
        outputs = {}

        feedback.pushInfo('Preparing inputs...')
        
        line_file = parameters['Lines']
        network = parameters['Network']

        network_layer = QgsProcessingUtils.mapLayerFromString(network, context=context)
        crs = network_layer.crs().authid()

        node_coords = {}
        all_links_dict = {}
        for feat in network_layer.getFeatures():
            A = str(feat['A'])
            B = str(feat['B'])
            LINKCLASS = feat['LINKCLASS']

            if (A not in node_coords) or \
                (B not in node_coords):
                
                line = feat.geometry().constGet()

                if type(line) == QgsMultiLineString:
                    # Assume MultiLineString
                    linestring_count = 0
                    for l in line:
                        if linestring_count == 0:
                            A_node = QgsPoint(l[0].x(),l[0].y())
                        B_node = QgsPoint(l[-1].x(),l[-1].y())
                        linestring_count += 1
                elif type(line) == QgsLineString:
                    # Found LineString
                    A_node = QgsPoint(line[0].x(),line[0].y())
                    B_node = QgsPoint(line[-1].x(),line[-1].y())
                else:
                    feedback.pushInfo('Invalid geometry found. Terminating process.')
                    return results
                node_coords[A] = A_node
                node_coords[B] = B_node

            if A not in all_links_dict:
                all_links_dict[A] = {B:LINKCLASS}
            else:
                if B not in all_links_dict[A]:
                    all_links_dict[A][B] = LINKCLASS

        with open(line_file, "r") as f:
            linefile = f.read().split('\n')

        lines = QgsVectorLayer("LineString?crs="+crs+"&field=route_id:string&field=mode:integer&field=name:string&field=headway_AM:integer&field=headway_IP:integer&field=headway_PM:integer&field=headway_OP:integer&index=no","Lines","memory")
        pr = lines.dataProvider()

        rows_processed = 0
        total_rows = len([line for line in linefile if len([i for i in range(len(line)) if line.startswith('"', i)][:2]) != 0])

        feedback.pushInfo(str(total_rows) + ' lines found. Starting route generation.')
        feedback.pushInfo('')
        feedback.setProgress(1)
        for line in linefile:
            not_imported = False
            missing_nodes = []
            missing_links = []
            invalid_link_direction = []
            repeated_nodes = []
            invalid_linkc = {}
            ind = [i for i in range(len(line)) if line.startswith('"', i)]
            if len(ind) != 0:
                route_id = line[ind[0] + 1 : ind[1]]
                node_list = []
                new_nodes = line[line.find('N=') + 2 :].split(',')
                mode = line[line.find('MODE=')+5:].split(',')[0]
                name = line[ind[2] + 1 : ind[3]]
                headways = [line[line.find('HEADWAY['+str(per)+']=')+11:].split(',')[0] for per in range(1,5)]
                for j in range(len(new_nodes)-1,-1,-1):
                    if new_nodes[j].startswith('N='):
                        new_nodes[j] = new_nodes[j][2:]
                    if new_nodes[j].startswith('-'):
                        new_nodes[j] = new_nodes[j][1:]
                    if not new_nodes[j].isdigit():
                        del new_nodes[j]
                        continue
                    
                    try:
                        temp_node_coords = node_coords[new_nodes[j]]
                        node_list.append(new_nodes[j])
                        new_nodes[j] = temp_node_coords
                    except:
                        missing_nodes.append(new_nodes[j])
                        del new_nodes[j]

                node_list = node_list[::-1]
                for j in range(len(node_list) - 1):
                    if node_list[j + 1] == node_list[j]:
                        if str(node_list[j]) not in repeated_nodes:
                            repeated_nodes.append(str(node_list[j]))
                    elif node_list[j + 1] not in all_links_dict[node_list[j]]:
                        if node_list[j] not in all_links_dict[node_list[j + 1]]:
                            missing_links.append('A:'+str(node_list[j]) + ',B:' + str(node_list[j + 1]))
                        else:
                            if len(invalid_link_direction) == 0 or invalid_link_direction[-1][-1] != str(node_list[j]):
                                invalid_link_direction.append([str(node_list[j]),str(node_list[j + 1])])
                            else:
                                invalid_link_direction[-1] = invalid_link_direction[-1].append(str(node_list[j + 1]))
                    elif all_links_dict[node_list[j]][node_list[j + 1]] in [1, 45, 46]:
                        if str(all_links_dict[node_list[j]][node_list[j + 1]]) not in invalid_linkc:
                            invalid_linkc[str(all_links_dict[node_list[j]][node_list[j + 1]])] = [str(node_list[j]) + ',' + str(node_list[j + 1])]
                        else:
                            invalid_linkc[str(all_links_dict[node_list[j]][node_list[j + 1]])].append(str(node_list[j]) + ',' + str(node_list[j + 1]))

                try:
                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromPolyline(new_nodes))
                    feature.setAttributes([route_id,mode,name,*headways])
                    pr.addFeatures([feature])
                    lines.updateExtents()
                    missing_nodes_text = ' Route ' + route_id + ' imported excluding invalid nodes. Check for errors.'
                    missing_links_text = ' Check for missing links on route ' + route_id + '.'
                    repeated_nodes_text = ' Check for repeated nodes on route ' + route_id + '.'
                    invalid_link_direction_text = ' Check for invalid link directions on route ' + route_id + '.'
                    invalid_linkc_text = ' Check for invalid LINKCLASS on route ' + route_id + '.'
                except:
                    missing_nodes_text = ''
                    missing_links_text = ''
                    repeated_nodes_text = ''
                    invalid_link_direction_text = ''
                    invalid_linkc_text = ''
                    not_imported = True
                
                if len(missing_nodes) > 0:
                    errors.append('Error: Invalid node(s) found on row ' + str(rows_processed) + '.' + missing_nodes_text)
                    errors.append('Invalid nodes: ' + ', '.join(missing_nodes))
                    errors.append('')

                if len(invalid_link_direction) > 0:
                    errors.append('Error: Link(s) with invalid direction found on row ' + str(rows_processed) + '.' + invalid_link_direction_text)
                    for seq in invalid_link_direction:
                        errors.append('Invalid sequence: ' + ','.join(invalid_link_direction[seq]))
                    errors.append('')

                if len(repeated_nodes) > 0:
                    errors.append('Error: Adjacent repeated nodes found on row ' + str(rows_processed) + '.' + repeated_nodes_text)
                    errors.append('Repeated nodes: ' + ','.join(repeated_nodes))
                    errors.append('')
                    
                if len(missing_links) > 0:
                    errors.append('Error: Missing link(s) found on row ' + str(rows_processed) + '.' + missing_links_text)
                    errors.append('Missing links: ' + '/'.join(missing_links))
                    errors.append('')

                if len(invalid_linkc) > 0 :
                    errors.append('Error: Link(s) with an invalid LINKCLASS found on row ' + str(rows_processed) + '.' + missing_linkc_text)
                    for invalid_class in invalid_linkc:
                        errors.append('Invalid LINKCLASS '+invalid_class+': ' + '/'.join(invalid_linkc[invalid_class]))
                    errors.append('')                    
            
                if not_imported:
                    errors.append('Error: Unable to generate route for row ' + str(rows_processed) + '. Route ' + route_id + ' not imported.')
                    errors.append('')

                rows_processed += 1
            feedback.setProgress(math.ceil((float(rows_processed) / float(total_rows)) * 100))

        feedback.pushInfo('Processed ' + str(rows_processed) + ' / ' + str(total_rows) + ' lines')
        feedback.pushInfo('')
        
        QgsProject.instance().addMapLayer(lines)

        # Merge vector layers
        alg_params = {
            'CRS': QgsCoordinateReferenceSystem(crs),
            'LAYERS': ['Lines'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MergeVectorLayers'] = processing.run('native:mergevectorlayers', alg_params, context=context, is_child_algorithm=True)

        # Drop field(s)
        alg_params = {
            'COLUMN': ['layer','path'],
            'INPUT': outputs['MergeVectorLayers']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DropFields'] = processing.run('native:deletecolumn', alg_params, context=context, is_child_algorithm=True)

        # Load layer into project
        alg_params = {
            'INPUT': outputs['DropFields']['OUTPUT'],
            'NAME': 'LINE import'
        }
        outputs['LoadLayerIntoProject'] = processing.run('native:loadlayer', alg_params, context=context, is_child_algorithm=True)
        
        QgsProject.instance().removeMapLayer(lines.id())

        for error in errors:
            feedback.pushInfo(error)
            
        if len(errors) == 0:
            feedback.pushInfo('All links and nodes have been validated.')
            feedback.pushInfo('')

        return results

    def name(self):
        return 'Generate spatial layer from VITM lines file'

    def displayName(self):
        return 'Generate spatial layer from VITM lines file'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return GenerateSpatialLayerFromLinesFile()
