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

valid_links_dict = None
undirected_links_dict = None
all_seqs = None

def try_ensure_paths_valid(paths):

    for i in range(len(paths) - 1):
        if valid_path(paths[i]) and not valid_path(paths[i + 1]) or \
            not valid_path(paths[i]) and valid_path(paths[i + 1]):
            temp_path = reverse_path(paths[i])
            paths[i] = reverse_path(paths[i + 1])
            paths[i + 1] = temp_path
    
    return paths

def flatten_path(path):

    try:
        return [node for seq in path for node in seq[:-1]] + [path[-1][-1]]
    except:
        return path

def remove_list_containers(paths):

    # print('removing list containers',paths)
    new_paths = []
    for path in paths:
        if type(path[0]) == list:
            for p in path:
                new_paths.append(p)
        else:
            new_paths.append(path)
    
    return new_paths

def valid_path(path):

    path = flatten_path(path)

    for i in range(len(path) - 1):
        if path[i + 1] not in valid_links_dict[path[i]]:
            return False
    
    return True

def reverse_path(path):

    try:
        return [seq[::-1] for seq in path[::-1]]
    except:
        return path[::-1]

def both_directions(path):

    return path + reverse_path(path)

def final_node(path):

    path = flatten_path(path)

    return path[-1]

def first_node(path):

    path = flatten_path(path)

    return path[0]

def find_next_seq(seq, nodes_to_search):

    length = 0
    start_node = first_node(seq)
    while True:
        last_node = final_node(seq)
        if last_node in nodes_to_search:
            return seq
        next_nodes = undirected_links_dict[last_node]
        new_nodes = [node for node in next_nodes if node not in seq]
        if len(new_nodes) == 1:
            seq.append(new_nodes[0])
        elif len(new_nodes) == 0:
            if len(seq) > 2 and any(node == start_node for node in next_nodes):
                seq.append(first_node(seq))
            return seq
        else:
            return seq

def find_unique_segments(junction_nodes, orig_node, dest_node):

    nodes_to_search = list(set([orig_node] + junction_nodes + [dest_node]))
    all_nodes_to_search = nodes_to_search.copy()
    all_seqs = {'Loop':[],'Link':[]}
    found_nodes = [orig_node]
    all_nodes = [orig_node]
    nodes_to_search.remove(orig_node)
    while True:
        new_nodes = []
        temp_seq = []
        num_paths = len(found_nodes)
        for start_node in found_nodes:
            next_nodes = undirected_links_dict[start_node]
            for next_node in next_nodes:
                seq = find_next_seq([start_node, next_node], all_nodes_to_search)
                if final_node(seq) == first_node(seq):
                    if seq not in both_directions(all_seqs['Loop']):
                        all_seqs['Loop'].append(seq)
                elif final_node(seq) == dest_node:
                    if seq not in both_directions(all_seqs['Link']):
                        all_seqs['Link'].append(seq)
                        temp_seq.append(seq)
                elif final_node(seq) == orig_node:
                    None           
                elif final_node(seq) not in junction_nodes:
                    seq = seq+reverse_path(seq)[1:]
                    if seq not in all_seqs['Loop']:
                        all_seqs['Loop'].append(seq)
                else:
                    if seq not in both_directions(all_seqs['Link']):
                        all_seqs['Link'].append(seq)
                        temp_seq.append(seq)
                if seq in temp_seq and final_node(seq) not in all_nodes:
                    all_nodes.append(final_node(seq))
                    new_nodes.append(final_node(seq))
        found_nodes = new_nodes.copy()
        if len(nodes_to_search) == 0:
            return all_seqs
        for node in found_nodes:
            nodes_to_search.remove(node)

def sort_by_length(paths):

    paths_with_length = []
    for path in paths:
        flat_path = flatten_path(path)
        num_nodes = len(flat_path)
        length = 0
        for i in range(len(flat_path) - 1):
            try:
                length += undirected_links_dict[flat_path[i]][flat_path[i + 1]]
            except:
                found_seq = [seq for seq in both_directions(all_seqs['Link']) if first_node(seq) == flat_path[i] and final_node(seq) == flat_path[i + 1]][0]
                for j in range(len(found_seq) - 1):
                    length += undirected_links_dict[found_seq[j]][found_seq[j + 1]]
        paths_with_length.append((length, num_nodes, path))
    
    paths_with_length.sort(key=lambda x: x[0:2])

    paths = [tup[2] for tup in paths_with_length]

    return paths

def find_shortest_path(orig_node, dest_node, traversed_paths, shortest_number_of_nodes):

    node_tree = [[orig_node]]
    found_path = []
    shortest_path = None
    while True:
        new_tree = []
        for nodes in node_tree:
            new_nodes = [seq for seq in both_directions(all_seqs['Link']) if first_node(seq) == final_node(nodes)]
            new_nodes = list(set([final_node(seq) for seq in new_nodes if seq not in both_directions(traversed_paths)]))
            for new_node in new_nodes:
                if new_node not in nodes:
                    nodes_copy = nodes.copy()
                    nodes_copy.append(new_node)
                    if new_node == dest_node:
                        found_path.append(nodes_copy)
                    else:
                        new_tree.append(nodes_copy)
        if len(new_tree) == 0:
            if len(found_path) > 0:
                if shortest_number_of_nodes:
                    fewest_nodes = sorted([len(path) for path in found_path])[0]
                    found_path = [path for path in found_path if len(path) == fewest_nodes]
                found_path = sort_by_length(found_path)
                shortest_path = found_path[0]
            else:
                node_tree = sort_by_length(node_tree)
                shortest_path = node_tree[0]
            return shortest_path
        node_tree = new_tree

def consolidate_paths(direct_paths, other_branches, orig_node, dest_node):

    # end_node = final_node(route_shortest_path)

    consolidated_path = []
    if len(other_branches) > 0:
        # print('paths',direct_paths + [other_branches])
        paths = sort_by_length(direct_paths + [other_branches])
    else:
        paths = sort_by_length(direct_paths)
    
    # print('consolidating paths from',orig_node,'to', dest_node,':', paths)
    
    paths_ending_at_dest = [path for path in paths if final_node(path) == dest_node]
    paths_not_ending_at_dest = [path for path in paths if path not in paths_ending_at_dest]
    loops_at_dest = [loop for loop in all_seqs['Loop'] if first_node(loop) == dest_node]
    paths_beginning_at_dest = [path for path in both_directions(all_seqs['Link']) if first_node(path) == dest_node]
    paths_beginning_at_dest = [path for path in paths_beginning_at_dest if path not in both_directions(direct_paths + [other_branches])]
    # paths_beginning_at_last_node = [path for path in both_directions(all_seqs['Link']) if first_node(path) == end_node]
    # paths_beginning_at_last_node = [path for path in paths_beginning_at_last_node if path not in both_directions(direct_paths + [other_branches])]

    # print('paths ending at dest',paths_ending_at_dest)
    # print('paths not ending at dest',paths_not_ending_at_dest)
    # print('paths beginning at dest', paths_beginning_at_dest)
    # print('loops at dest',loops_at_dest)
    
    for path in paths_not_ending_at_dest:
        if first_node(path) == final_node(path):
            consolidated_path += path
        else:
            path = assert_dest_node(path, first_node(path))
            consolidated_path += path
            
    if len(paths_ending_at_dest) > 0:

        for i in range(len(paths_ending_at_dest)):
            if i % 2 == 1:
                paths_ending_at_dest[i] = reverse_path(paths_ending_at_dest[i])

        paths_ending_at_dest = try_ensure_paths_valid(paths_ending_at_dest)
        consolidated_path += paths_ending_at_dest

    consolidated_path = remove_list_containers(consolidated_path)

    # if len(paths_ending_at_dest) % 2 == 0:
    consolidated_path = assert_dest_node(consolidated_path, dest_node)

    # print('\nconsolidated path for segment',orig_node,'to',dest_node,':',consolidated_path)

    return consolidated_path

def find_most_likely_path(orig_node, dest_node, traversed_paths, route_shortest_path):

    shortest_path = find_shortest_path(orig_node, dest_node, traversed_paths, True)
    
    if shortest_path != route_shortest_path:
        route_shortest_path_string = ','.join([str(node) for node in route_shortest_path])
        shortest_path_string = ','.join([str(node) for node in shortest_path[:2]])
        if shortest_path_string in route_shortest_path_string:
            return []

    if len(shortest_path) < 2:
        return []

    # print('\nshortest path',shortest_path)
    
    build_tree = []
    for i in range(len(shortest_path)):
        branch = False
        current_node = shortest_path[i]
        if i < len(shortest_path) - 1:
            next_node = shortest_path[i + 1]
            # print('\nnew segment',current_node,'to',next_node)
        else:
            if current_node not in route_shortest_path[:-1]:
                None
                # print('\nsearching past',current_node)
            else:
                continue
        paths = [seq for seq in both_directions(all_seqs['Link']) if first_node(seq) == current_node]
        paths = [seq for seq in paths if seq not in both_directions(traversed_paths)]
        # print('all paths starting from', current_node, ':', paths)
        other_branches = []
        direct_paths = []
        if len(paths) > 0:
            if i < len(shortest_path) - 1:
                direct_paths = [path for path in paths if final_node(path) == next_node]
                for path in direct_paths:
                    if path not in traversed_paths and reverse_path(path) not in traversed_paths:
                        traversed_paths.append(path)
                non_direct_paths = [path for path in paths if path not in direct_paths]
                if len(non_direct_paths) > 0:
                    branch = True
            else:
                next_node = final_node(paths[0])
                branch = True
            if branch:
                # print('\nbranching:',len(paths)-len(direct_paths),'branch(es) to nodes other than',next_node)
                other_branches = find_most_likely_path(current_node, next_node, traversed_paths, route_shortest_path)
                # print('other branches', current_node, next_node, other_branches)
        elif i < len(shortest_path) - 1 and next_node in route_shortest_path:
            direct_paths = [seq for seq in both_directions(all_seqs['Link']) if (first_node(seq) == current_node and final_node(seq) == next_node)]
            if len(direct_paths) > 0:
                direct_paths = [direct_paths[0]]
        if len(other_branches) == 0 and len(direct_paths) == 0:
            continue
        consolidated_paths = consolidate_paths(direct_paths, other_branches, current_node, next_node)
        for path in consolidated_paths:
            if path not in traversed_paths and reverse_path(path) not in traversed_paths:
                traversed_paths.append(path)
        build_tree += consolidated_paths
        
    return build_tree

def assert_dest_node(path, dest_node):

    end_node = final_node(path)
    if end_node != dest_node:
        shortest_path = find_shortest_path(end_node, dest_node, [], False)
        for i in range(len(shortest_path) - 1):
            current_node = shortest_path[i]
            next_node = shortest_path[i + 1]
            paths = [seq for seq in both_directions(all_seqs['Link']) if (first_node(seq) == current_node and final_node(seq) == next_node)]
            paths = sort_by_length(paths)
            path.append(paths[0])
    
    return path

def generate_node_sequence(junction_nodes, orig_node, dest_node):

    global all_seqs

    all_seqs = find_unique_segments(junction_nodes, orig_node, dest_node)

    if len(all_seqs['Link']) == 0:
        return []

    # print(all_seqs)

    traversed_paths = []
    route_shortest_path = find_shortest_path(orig_node, dest_node, traversed_paths, True)
    build_tree = find_most_likely_path(orig_node, dest_node, traversed_paths, route_shortest_path)

    if len(build_tree) == 0:
        return []
    
    build_tree = assert_dest_node(build_tree, dest_node)

    # print('build tree', build_tree)
    
    for loop in all_seqs['Loop']:

        if not valid_path(loop):
            loop = reverse_path(loop)

        for i in reversed(range(len(build_tree))):
            if first_node(loop) == first_node(build_tree[i]):
                build_tree.insert(i, loop)
                break
            elif first_node(loop) == final_node(build_tree[i]):
                build_tree.insert(i + 1, loop)
                break
    
    build_tree = flatten_path(build_tree)

    return build_tree

class GenerateNodeSequenceFromSelectedLinks(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):

        proj_path = QgsProject.instance().readPath("./")
        self.addParameter(QgsProcessingParameterVectorLayer('Links', 'Selected links layer', types=[QgsProcessing.TypeVectorLine], defaultValue='/Users/frankiemacbook/OneDrive - VicGov/GitHub/VITM-ref-case-update/NEL routes/VITM-Links.gpkg|layername=VITM-Links'))
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
        
        global valid_links_dict, undirected_links_dict

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
                    undirected_links_dict[feature['A']] = {feature['B']:line.length()}
                    node_coords[feature['A']] = A_node
                else:
                    if feature['B'] not in undirected_links_dict[feature['A']]:   
                        undirected_links_dict[feature['A']][feature['B']] = line.length()
                if feature['B'] not in node_coords:
                    node_coords[feature['B']] = B_node
                    undirected_links_dict[feature['B']] = {feature['A']:line.length()}
                else:
                    if feature['A'] not in undirected_links_dict[feature['B']]:
                        undirected_links_dict[feature['B']][feature['A']] = line.length()

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

        valid_links_dict = {}
        for feature in filtered_network.getFeatures():
            line = feature.geometry().constGet()
            if feature['A'] not in valid_links_dict:
                valid_links_dict[feature['A']] = [feature['B']]
            else:
                if feature['B'] not in valid_links_dict[feature['A']]:
                    valid_links_dict[feature['A']].append(feature['B'])
            
        total_node_num = len(node_coords)

        if total_node_num < 2:
            feedback.pushInfo('Error: No route found. Please ensure you have selected route links on the network layer and that all selected links are valid.')
            feedback.pushInfo('')
            return results

        all_segs = []
        for start_node in undirected_links_dict:
            for end_node in undirected_links_dict[start_node]:
                if ((start_node,end_node) not in all_segs) and \
                    ((end_node,start_node) not in all_segs):
                    all_segs.append((start_node,end_node))

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
            for nodes in all_segs:
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
            feedback.pushInfo('Error: This route is discontinuous. Terminal nodes: ' + ','.join(str(node) for node in terminal_nodes) + '. A unique route cannot be found. Please check selected links and try again.')
            feedback.pushInfo('')
            return results
        
        if len(terminal_nodes) > 2 and \
            (all(o is None for o in [orig_node, orig_point]) or \
            all(d is None for d in [dest_node, dest_point])):
            feedback.pushInfo('Error: This route has more than two terminii. Terminal nodes: '+','.join(str(node) for node in terminal_nodes)+'. A unique route cannot be found. If the intended route includes diversions or loops, please identify both origin and destination nodes. If this appears to be an error, a redundant link may have been included. Please check selected links and try again.')
            feedback.pushInfo('')
            return results

        dist_orig_to_terminii = []
        dist_dest_to_terminii = []
        for node in node_coords:
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
                feedback.pushInfo('Setting origin node as closest node to mouse selection: ' + str(orig_node) + '.')
            if new_dest_node is None:
                dest_node = [node for node in terminal_nodes if node != orig_node][0]
                feedback.pushInfo('Setting destination node: ' + str(dest_node) + '.')
        if new_dest_node is not None:
            if new_dest_node != dest_node:
                dest_node = new_dest_node
                feedback.pushInfo('Setting destination node as closest node to mouse selection: ' + str(dest_node) + '.')
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

        node_seqs = {}
        nodes_xy = {}
        link_seq = {}
        missing_links = {}
        suffix = {'forward':'','reverse':'R'}

        forward_seq = generate_node_sequence(junction_nodes, orig_node, dest_node)

        node_seqs['forward'] = forward_seq

        if reverse:
            reverse_seq = generate_node_sequence(junction_nodes, dest_node, orig_node)
            node_seqs['reverse'] = reverse_seq
        
        for seq in node_seqs:

            nodes_xy[seq] = []
            for node in node_seqs[seq]:
                nodes_xy[seq].append(node_coords[node])

            if len(seq) < 2:
                feedback.pushInfo('Error: No sequence found for the '+seq+' route. Please check selected links.')
                feedback.pushInfo('')
                return results

            link_seq[seq] = []
            for i in range(len(node_seqs[seq])-1):
                link_seq[seq].append((node_seqs[seq][i],node_seqs[seq][i+1]))

            missing_links[seq] = [(str(x), str(y)) for (x, y) in all_segs if (((x, y) not in link_seq[seq]) and ((y, x) not in link_seq[seq]))]
            missing_links_text = '(' + '), ('.join([','.join(link) for link in missing_links[seq]]) + ')'
                
            if len(set(node_seqs[seq])) != total_node_num:
                feedback.pushInfo('Error: Shortest path in '+seq+' route does not include all selected links. Missing links: '+missing_links_text+'. These links may have been selected by mistake. Please check selected links and try again.')
                feedback.pushInfo('')
                return results
            
        cols = ['ID','Sequence','Node']
        LIN_output = [cols]
        for seq in node_seqs:
            counter = 1
            for node in node_seqs[seq]:
                LIN_output.append([route+suffix[seq],counter,node])
                counter += 1

        for lin in LIN_output:
            feedback.pushInfo(', '.join([str(l) for l in lin]))
        feedback.pushInfo('')
        
        for seq in node_seqs:
            feedback.pushInfo(route+suffix[seq])
            feedback.pushInfo(','.join(str(node) for node in node_seqs[seq]))
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

            for seq in node_seqs:
                for i in range(len(nodes_xy[seq]) - 1):
                    A = nodes_xy[seq][i]
                    B = nodes_xy[seq][i+1]
                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromPolyline([A,B]))
                    feature.setAttributes([route+suffix[seq],i,node_seqs[seq][i],node_seqs[seq][i+1]])
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
        
        if validate_links:

            directional_links_not_found = {}

            for seq in node_seqs:

                directional_links_not_found[seq] = []

                for i in range(len(node_seqs[seq]) - 1):
                    
                    if node_seqs[seq][i] not in valid_links_dict:
                        directional_links_not_found[seq].append((str(node_seqs[seq][i]),str(node_seqs[seq][i+1])))
                    elif node_seqs[seq][i+1] not in valid_links_dict[node_seqs[seq][i]]:
                        directional_links_not_found[seq].append((str(node_seqs[seq][i]), str(node_seqs[seq][i+1])))
                    
                directional_links_not_found_text = '('+'), ('.join([','.join(link) for link in directional_links_not_found[seq]])+')'
                
                if len(directional_links_not_found[seq]) > 0:
                    feedback.pushInfo('Warning: The '+seq+' route includes links with a directionality (A -> B) that does not exist in the network. Invalid links: '+directional_links_not_found_text+'. Please check the route includes valid directional links only.')
                    feedback.pushInfo('')

            all_flags = [link_classes]
            for seq in node_seqs:
                all_flags.append(directional_links_not_found[seq])
                all_flags.append(missing_links[seq])
            
            if all(len(x) == 0 for x in all_flags):
                feedback.pushInfo('All links validated.')
                feedback.pushInfo('')
                if len(junction_nodes) > 0:
                    feedback.pushInfo('This route contains at least one junction, some assumptions about the correct travel sequence along the route have been made. Please check the output node sequence is as expected.')
                    feedback.pushInfo('')
            else:
                feedback.pushInfo('Errors found. Please check log for details.')
                feedback.pushInfo('')

        return results

    def name(self):
        return 'Generate node sequence from selected links - v2 (beta)'

    def displayName(self):
        return 'Generate node sequence from selected links - v2 (beta)'

    def group(self):
        return ''

    def groupId(self):
        return ''

    def createInstance(self):
        return GenerateNodeSequenceFromSelectedLinks()