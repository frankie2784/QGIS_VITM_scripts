"""
QGIS : 31802
"""

from qgis.core import QgsProject
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterPoint
from qgis.core import QgsProcessingUtils
from qgis.core import QgsPoint, QgsFeature, QgsGeometry, QgsVectorLayer
from qgis.core import QgsLineString, QgsMultiLineString
import processing
import csv
import pathlib

invalid_links = []
nodes_xy = None
node_seq = None
searched_nodes = None

def find_next_node(layer, current_node):
    global node_seq, nodes_xy, invalid_links
    prev_node = -1
    while True:
        for feature in layer.getFeatures():
            if (str(feature['A']),str(feature['B'])) not in invalid_links:
                if ((feature['A'] == current_node) and \
                    (feature['B'] not in searched_nodes)) or \
                    ((feature['B'] == current_node) and \
                    (feature['A'] not in searched_nodes)):
                    if prev_node != -1:
                        node_seq = node_seq[:prev_node]
                        nodes_xy = nodes_xy[:prev_node]
                    if feature['A'] == current_node:
                        return feature['B']
                    else:
                        return feature['A']
        current_node = node_seq[prev_node-1]
        prev_node -= 1

class GenerateNodeSequenceFromSelectedLinks(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):

        proj_path = QgsProject.instance().readPath("./")
        self.addParameter(QgsProcessingParameterVectorLayer('Links', 'Selected links layer', types=[QgsProcessing.TypeVectorLine], defaultValue='/Users/frankiemacbook/Documents/GitHub/NELupdate/VITM-Links.gpkg|layername=VITM-Links'))
        self.addParameter(QgsProcessingParameterString('Route', 'Route ID', optional=True, multiLine=False, defaultValue=None))
        self.addParameter(QgsProcessingParameterBoolean('Rail', 'Is rail route', defaultValue=False))
        self.addParameter(QgsProcessingParameterPoint('Origpoint', 'Identify route origin with mouse (click ... then click near beginning of route on the map)', optional=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('Orignode', 'Or manually enter origin node (overrides field above)', type=QgsProcessingParameterNumber.Integer, optional=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterPoint('Destpoint', 'Identify route destination using mouse', optional=True, defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('Destnode', 'Manually enter destination node', optional=True, type=QgsProcessingParameterNumber.Integer, defaultValue=None))
        self.addParameter(QgsProcessingParameterBoolean('Reverse', 'Add reverse (R) route', defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean('Validate', 'Validate links', defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean('Output', 'Output route as separate spatial layer and CSV', defaultValue=True))
        self.addParameter(QgsProcessingParameterString('Path', 'CSV layer output', optional=True, multiLine=False, defaultValue=proj_path + '/output.csv'))

            
    def processAlgorithm(self, parameters, context, model_feedback):
        global node_seq, searched_nodes, nodes_xy, invalid_links
        
        feedback = QgsProcessingMultiStepFeedback(1, model_feedback)

        results = {}
        outputs = {}

        route = parameters['Route']
        if route == '':
            route = 'route'
        reverse = parameters['Reverse']
        path = parameters['Path']
        is_rail = parameters['Rail']
        output_separate_layer = parameters['Output']
        validate_links = parameters['Validate']
                        
        # Extract selected links_layer.getFeatures()
        alg_params = {
            'INPUT': parameters['Links'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtractSelectedFeatures'] = processing.run('native:saveselectedfeatures', alg_params, context=context, is_child_algorithm=True)
        
        links_layer = QgsProcessingUtils.mapLayerFromString(outputs['ExtractSelectedFeatures']['OUTPUT'], context=context)
        crs = links_layer.crs().authid()
        
        project_crs = QgsProject.instance().crs().authid()
        sourceCrs = QgsCoordinateReferenceSystem(int(project_crs.split(':')[1]))
        destCrs = QgsCoordinateReferenceSystem(int(crs.split(':')[1]))
        tr = QgsCoordinateTransform(sourceCrs, destCrs, QgsProject.instance())

        orig_node = parameters['Orignode']
        orig_point = parameters['Origpoint']
        if orig_point is not None:
            orig_point = (float(orig_point.split(',')[0]), float(orig_point.split(',')[1].split(' ')[0]))
            orig_point = QgsPoint(orig_point[0], orig_point[1])
            orig_point.transform(tr)

        dest_node = parameters['Destnode']
        dest_point = parameters['Destpoint']
        if dest_point is not None:
            dest_point = (float(dest_point.split(',')[0]), float(dest_point.split(',')[1].split(' ')[0]))
            dest_point = QgsPoint(dest_point[0], dest_point[1])
            dest_point.transform(tr)

        end_nodes_in_layer = [False,False]
        undirected_links_dict = {}
        node_coords = {}
        link_classes = {}
        invalid_link_class = False
        for feature in links_layer.getFeatures():
            if validate_links:
                if is_rail:
                    if feature['LINKCLASS'] != 42:
                        invalid_link_class = True
                else:
                    if feature['LINKCLASS'] in [-1, 1, 42, 45, 46]:
                        invalid_link_class = True
            if invalid_link_class:
                if feature['LINKCLASS'] not in link_classes:
                    link_classes[feature['LINKCLASS']] = [(str(feature['A']), str(feature['B']))]
                else:
                    link_classes[feature['LINKCLASS']].append((str(feature['A']), str(feature['B'])))
            else:
                if (feature['A'] not in node_coords) or \
                    (feature['B'] not in node_coords):
                    
                    line = feature.geometry().constGet()

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

                if feature['A'] not in node_coords:
                    undirected_links_dict[feature['A']] = [feature['B']]
                    node_coords[feature['A']] = A_node
                else:
                    if feature['B'] not in undirected_links_dict[feature['A']]:   
                        undirected_links_dict[feature['A']].append(feature['B'])
                if feature['B'] not in node_coords:
                    node_coords[feature['B']] = B_node
                    undirected_links_dict[feature['B']] = [feature['A']]
                else:
                    if feature['A'] not in undirected_links_dict[feature['B']]:
                        undirected_links_dict[feature['B']].append(feature['A'])

                if orig_node != 0:
                    if (feature['A'] == orig_node) or \
                    (feature['B'] == orig_node):
                        end_nodes_in_layer[0] = True
                if dest_node is not None:
                    if (feature['A'] == dest_node) or \
                    (feature['B'] == dest_node):
                        end_nodes_in_layer[1] = True
            invalid_link_class = False

        if validate_links:
            
            invalid_links = [l for c in link_classes for l in link_classes[c]]

            if len(link_classes) > 0:
                link_classes_text = ''
                for link in link_classes:
                    link_classes_text += 'LINKCLASS = ' + str(link) + ': (' + '), ('.join([','.join(l) for l in link_classes[link]]) + ') '
                feedback.pushInfo('Warning: At least one of the selected links contains an invalid LINKCLASS. Invalid links: '+link_classes_text+'. Attempting routing without these links.')
                feedback.pushInfo('')

        node_string = '('+','.join(str(node) for node in node_coords)+')'
        
        # FILTER LINKS
        alg_params = {
            'EXPRESSION': 'A in '+node_string+' and B in '+node_string,
            'INPUT': parameters['Links'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['FilterLinks'] = processing.run('native:extractbyexpression', alg_params, context=context, is_child_algorithm=True)

        filtered_network = QgsProcessingUtils.mapLayerFromString(outputs['FilterLinks']['OUTPUT'], context=context)

        all_links_dict = {}
        for feature in filtered_network.getFeatures():
            if feature['A'] not in all_links_dict:
                all_links_dict[feature['A']] = [feature['B']]
            else:
                if feature['B'] not in all_links_dict[feature['A']]:
                    all_links_dict[feature['A']].append(feature['B'])
            
        total_node_num = len(node_coords)

        if total_node_num < 2:
            feedback.pushInfo('Error: No route found. Please ensure you have selected route links on the network layer and that all selected links are valid.')
            feedback.pushInfo('')
            return results

        all_links = []
        for start_node in undirected_links_dict:
            for end_node in undirected_links_dict[start_node]:
                if ((start_node,end_node) not in all_links) and \
                    ((end_node,start_node) not in all_links):
                    all_links.append((start_node,end_node))

        terminal_nodes = [node for node in undirected_links_dict if len(undirected_links_dict[node]) == 1]
        junction_nodes = [node for node in undirected_links_dict if len(undirected_links_dict[node]) > 2]

        connected_links = []
        current_length = 0
        new_length = 0
        while True:
            if new_length > 0:
                if new_length == current_length or \
                    new_length == len(undirected_links_dict):
                    break
                else:
                    current_length = new_length
            for nodes in all_links:
                if len(connected_links) == 0:
                    connected_links.append(nodes[0])
                    connected_links.append(nodes[1])
                else:
                    if nodes[0] in connected_links and \
                        nodes[1] not in connected_links:
                        connected_links.append(nodes[1])
                    elif nodes[1] in connected_links and \
                        nodes[0] not in connected_links:
                        connected_links.append(nodes[0])
            new_length = len(connected_links)

        if len(connected_links) != len(undirected_links_dict):
            feedback.pushInfo('Error: This route is discontinuous. Terminal nodes: '+','.join(str(node) for node in terminal_nodes)+'. A unique route cannot be found. Please check selected links and try again.')
            return results
        
        if len(terminal_nodes) > 2:
            feedback.pushInfo('Error: This route has more than two terminii. Terminal nodes: '+','.join(str(node) for node in terminal_nodes)+'. A unique route cannot be found. Please check for missing or redundant links and try again.')
            return results

        if len(junction_nodes) > 0:
            feedback.pushInfo('Error: Sorry this route is self-intersecting. Intersecting nodes: '+','.join(str(node) for node in junction_nodes)+'. A unique route cannot be found. Please check selected links and try again.')
            return results

        dist_orig_to_terminii = []
        dist_dest_to_terminii = []
        for node in terminal_nodes:
            if orig_point is not None:
                dist_orig_to_terminii.append((node_coords[node].distance(orig_point), node))
            if dest_point is not None:
                dist_dest_to_terminii.append((node_coords[node].distance(dest_point), node))

        dist_orig_to_terminii.sort(key=lambda x: x[0])
        dist_dest_to_terminii.sort(key=lambda x: x[0])
        
        new_orig_node = None
        new_dest_node = None
        if len(dist_orig_to_terminii) > 0 and \
            not end_nodes_in_layer[0]:
            new_orig_node = dist_orig_to_terminii[0][1]
        elif end_nodes_in_layer[0]:
            new_orig_node = orig_node
        
        if len(dist_dest_to_terminii) > 0 and \
            not end_nodes_in_layer[1]:
            new_dest_node = dist_dest_to_terminii[0][1]
        elif end_nodes_in_layer[1]:
            new_dest_node = dest_node

        if new_orig_node is not None:
            if new_orig_node != orig_node:
                orig_node = new_orig_node
                feedback.pushInfo('Setting origin node as closest terminal node to mouse selection: ' + str(orig_node) + '.')
            if new_dest_node is None:
                dest_node = [node for node in terminal_nodes if node != orig_node][0]
                feedback.pushInfo('Setting destination node: ' + str(dest_node) + '.')
        if new_dest_node is not None:
            if new_dest_node != dest_node:
                dest_node = new_dest_node
                feedback.pushInfo('Setting destination node as closest terminal node to mouse selection: ' + str(dest_node) + '.')
            if new_orig_node is None:
                orig_node = [node for node in terminal_nodes if node != dest_node][0]
                feedback.pushInfo('Setting origin node: ' + str(orig_node) + '.')
        if new_orig_node is not None and \
            new_orig_node == new_dest_node:
            feedback.pushInfo('Error: Sorry the input origin and destination nodes are the same: '+str(new_dest_node)+'. A unique route cannot be found. Please check selected nodes and try again.')
            feedback.pushInfo('')
            return results
        if new_orig_node is None and \
            new_dest_node is None:
            orig_node = terminal_nodes[0]
            dest_node = terminal_nodes[1]
            feedback.pushInfo('Warning: No valid origin and destination nodes provided. Using ' + str(orig_node) + ' and ' + str(dest_node) + ' as origin and destination nodes.')

        feedback.pushInfo('')

        current_node = orig_node
        node_seq = [current_node]
        searched_nodes = [current_node]
        nodes_xy = [node_coords[current_node]]
        nodes_captured = 1
        while True:
            next_node = find_next_node(links_layer, current_node)
            node_seq.append(next_node)
            searched_nodes.append(next_node)
            nodes_xy.append(node_coords[next_node])
            
            nodes_captured += 1
                
            if next_node == dest_node:
                break
            current_node = next_node
        
        if len(node_seq) < 2:
            feedback.pushInfo('Error: No route found.')
            feedback.pushInfo('')
            return results

        link_seq = []
        for i in range(len(node_seq)-1):
            link_seq.append((node_seq[i],node_seq[i+1]))

        missing_links = [(str(x),str(y)) for (x,y) in all_links if (((x,y) not in link_seq) and ((y,x) not in link_seq))]
        missing_links_text = '('+'), ('.join([','.join(link) for link in missing_links])+')'

        if nodes_captured != total_node_num:
            feedback.pushInfo('Warning: Shortest path does not include all selected links. Missing links: '+missing_links_text+'. These links may have been selected by mistake. Please check route connectivity and that the shortest path found is the one expected.')
            feedback.pushInfo('')

        if validate_links:
            
            directional_links_not_found = []

            for i in range(len(node_seq) - 1):
                
                if node_seq[i] not in all_links_dict:
                    directional_links_not_found.append((str(node_seq[i]),str(node_seq[i+1])))
                elif node_seq[i+1] not in all_links_dict[node_seq[i]]:
                    directional_links_not_found.append((str(node_seq[i]), str(node_seq[i+1])))
                
            directional_links_not_found_text = '('+'), ('.join([','.join(link) for link in directional_links_not_found])+')'
            
            if len(directional_links_not_found) > 0:
                feedback.pushInfo('Warning: This route includes links with a directionality (A -> B) that does not exist in the network. Invalid links: '+directional_links_not_found_text+'. Please check the route includes valid directional links only.')
                feedback.pushInfo('')
                return results

            if reverse:

                directional_links_not_found = []

                for i in range(len(node_seq) - 1):

                    if node_seq[::-1][i] not in all_links_dict:
                        directional_links_not_found.append((str(node_seq[::-1][i]),str(node_seq[::-1][i+1])))
                    elif node_seq[::-1][i+1] not in all_links_dict[node_seq[::-1][i]]:
                        directional_links_not_found.append((str(node_seq[::-1][i]), str(node_seq[::-1][i+1])))

                directional_links_not_found_text = '('+'), ('.join([','.join(link) for link in directional_links_not_found])+')'
                
                if len(directional_links_not_found) > 0:
                    feedback.pushInfo('Warning: The reverse route includes links with a directionality (A -> B) that does not exist in the network. Invalid links: '+directional_links_not_found_text+'. Please check the route includes valid directional links only.')
                    feedback.pushInfo('')
                    return results

        cols = ['ID','Sequence','Node']
        LIN_output = [cols]
        counter = 1
        for node in node_seq:
            LIN_output.append([route,counter,node])
            counter += 1
        if reverse:
            counter = 1
            for node in node_seq[::-1]:
                LIN_output.append([route+'R',counter,node])
                counter += 1

        for lin in LIN_output:
            feedback.pushInfo(', '.join([str(l) for l in lin]))
        feedback.pushInfo('')
        
        feedback.pushInfo(route)
        feedback.pushInfo(','.join(str(node) for node in node_seq))
        feedback.pushInfo('')

        if reverse:
            feedback.pushInfo(route+'R')
            feedback.pushInfo(','.join(str(node) for node in node_seq[::-1]))
            feedback.pushInfo('')

        try:
            import pandas as pd
            pd.DataFrame(LIN_output[2:],columns=LIN_output[1]).to_clipboard(index=False)
            feedback.pushInfo('Table copied to clipboard (for pasting directly into Excel)')
            feedback.pushInfo('')
        except:
            None

        if output_separate_layer:

            lines = QgsVectorLayer("LineString?crs="+crs+"&field=route_id:string&field=sequence:integer&field=A:integer&field=B:integer&index=no",'Lines',"memory")
            pr = lines.dataProvider()

            feat_range = max(1,len(nodes_xy)-2)
            for i in range(feat_range):
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPolyline(nodes_xy[i:i+2]))
                feature.setAttributes([route,i,node_seq[i],node_seq[i+1]])
                pr.addFeatures([feature])
                lines.updateExtents()
            if reverse:
                nodes_xy = nodes_xy[::-1]
                for i in range(feat_range):
                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromPolyline(nodes_xy[i:i+2]))
                    feature.setAttributes([route+'R',i,node_seq[i],node_seq[i+1]])
                    pr.addFeatures([feature])
                    lines.updateExtents()
            
            QgsProject.instance().addMapLayer(lines)

            # Merge vector layers
            alg_params = {
                'CRS': QgsCoordinateReferenceSystem(crs),
                'LAYERS': ['Lines'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['MergeVectorLayers'] = processing.run('native:mergevectorlayers', alg_params, context=context, is_child_algorithm=True)

            # Load layer into project
            alg_params = {
                'INPUT': outputs['MergeVectorLayers']['OUTPUT'],
                'NAME': 'Imported LINE routes'
            }
            outputs['LoadLayerIntoProject'] = processing.run('native:loadlayer', alg_params, context=context, is_child_algorithm=True)        

            QgsProject.instance().removeMapLayer(lines.id())

            if path is not None:
                p = pathlib.Path(path.rsplit('/',1)[0])
                p.mkdir(parents=True, exist_ok=True)
                with open(path, 'w', newline="") as f:
                    writer = csv.writer(f)
                    writer.writerows(LIN_output)
            
        return results

    def name(self):
        return 'Generate node sequence from selected links'

    def displayName(self):
        return 'Generate node sequence from selected links'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return GenerateNodeSequenceFromSelectedLinks()
