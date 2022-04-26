# Authors: see git history
#
# Copyright (c) 2010 Authors
# Licensed under the GNU GPL version 3.0 or later.  See the file LICENSE for details.

import networkx as nx
from shapely.geometry import Point

import inkex

from ...svg import get_correction_transform
from ...svg.tags import INKSCAPE_LABEL


def find_path(graph, starting_node, ending_node):
    """Find a path through the graph that sews every edge."""

    # This is done in two steps.  First, we find the shortest path from the
    # start to the end.  We remove it from the graph, and proceed to step 2.
    #
    # Then, we traverse the path node by node.  At each node, we follow any
    # branchings with a depth-first search.  We travel down each branch of
    # the tree, inserting each seen branch into the tree.  When the DFS
    # hits a dead-end, as it back-tracks, we also add the seen edges _again_.
    # Repeat until there are no more edges left in the graph.
    #
    # Visiting the edges again on the way back allows us to set up
    # "underpathing".
    path = nx.shortest_path(graph, starting_node, ending_node)

    # Copy the graph so that we can remove the edges as we visit them.
    # This also converts the directed graph into an undirected graph in the
    # case that "preserve_order" is set.
    graph = nx.Graph(graph)
    graph.remove_edges_from(list(zip(path[:-1], path[1:])))

    final_path = []
    prev = None
    for node in path:
        if prev is not None:
            final_path.append((prev, node))
        prev = node

        for n1, n2, edge_type in list(nx.dfs_labeled_edges(graph, node)):
            if n1 == n2:
                # dfs_labeled_edges gives us (start, start, "forward") for
                # the starting node for some reason
                continue

            if edge_type == "forward":
                final_path.append((n1, n2))
                graph.remove_edge(n1, n2)
            elif edge_type == "reverse":
                final_path.append((n2, n1))
            elif edge_type == "nontree":
                # a "nontree" happens when there exists an edge from n1 to n2
                # but n2 has already been visited.  It's a dead-end that runs
                # into part of the graph that we've already traversed.  We
                # do still need to make sure that edge is sewn, so we travel
                # down and back on this edge.
                #
                # It's possible for a given "nontree" edge to be listed more
                # than once so we'll deduplicate.
                if (n1, n2) in graph.edges:
                    final_path.append((n1, n2))
                    final_path.append((n2, n1))
                    graph.remove_edge(n1, n2)

    return final_path


def add_jumps(graph, elements, preserve_order):
    """Add jump stitches between elements as necessary.

    Jump stitches are added to ensure that all elements can be reached.  Only the
    minimal number and length of jumps necessary will be added.
    """

    if preserve_order:
        # For each sequential pair of elements, find the shortest possible jump
        # stitch between them and add it.  The directions of these new edges
        # will enforce stitching the elements in order.

        for element1, element2 in zip(elements[:-1], elements[1:]):
            potential_edges = []

            nodes1 = get_nodes_on_element(graph, element1)
            nodes2 = get_nodes_on_element(graph, element2)

            for node1 in nodes1:
                for node2 in nodes2:
                    point1 = graph.nodes[node1]['point']
                    point2 = graph.nodes[node2]['point']
                    potential_edges.append((point1, point2))

            if potential_edges:
                edge = min(potential_edges, key=lambda p1_p2: p1_p2[0].distance(p1_p2[1]))
                graph.add_edge(str(edge[0]), str(edge[1]), jump=True)
    else:
        # networkx makes this super-easy!  k_edge_agumentation tells us what edges
        # we need to add to ensure that the graph is fully connected.  We give it a
        # set of possible edges that it can consider adding (avail).  Each edge has
        # a weight, which we'll set as the length of the jump stitch.  The
        # algorithm will minimize the total length of jump stitches added.
        for jump in nx.k_edge_augmentation(graph, 1, avail=list(possible_jumps(graph))):
            graph.add_edge(*jump, jump=True)

    return graph


def possible_jumps(graph):
    """All possible jump stitches in the graph with their lengths.

    Returns: a generator of tuples: (node1, node2, length)
    """

    # We'll take the easy approach and list all edges that aren't already in
    # the graph.  networkx's algorithm is pretty efficient at ignoring
    # pointless options like jumping between two points on the same element.

    for start, end in nx.complement(graph).edges():
        start_point = graph.nodes[start]['point']
        end_point = graph.nodes[end]['point']
        yield (start, end, start_point.distance(end_point))


def get_starting_and_ending_nodes(graph, elements, preserve_order, starting_point, ending_point):
    """Find or choose the starting and ending graph nodes.

    If points were passed, we'll find the nearest graph nodes.  Since we split
    every path up into 1mm-chunks, we'll be at most 1mm away which is good
    enough.

    If we weren't given starting and ending points, we'll pic kthe far left and
    right nodes.

    returns:
        (starting graph node, ending graph node)
    """

    nodes = []

    nodes.append(find_node(graph, starting_point,
                           min, preserve_order, elements[0]))
    nodes.append(find_node(graph, ending_point,
                           max, preserve_order, elements[-1]))

    return nodes


def find_node(graph, point, extreme_function, constrain_to_satin=False, satin=None):
    if constrain_to_satin:
        nodes = get_nodes_on_element(graph, satin)
    else:
        nodes = graph.nodes()

    if point is None:
        return extreme_function(nodes, key=lambda node: graph.nodes[node]['point'].x)
    else:
        point = Point(*point)
        return min(nodes, key=lambda node: graph.nodes[node]['point'].distance(point))


def get_nodes_on_element(graph, element):
    nodes = set()

    for start_node, end_node, element_for_edge in graph.edges(data='element'):
        if element_for_edge is element:
            nodes.add(start_node)
            nodes.add(end_node)

    return nodes


def remove_original_elements(elements):
    for element in elements:
        for command in element.commands:
            command_group = command.use.getparent()
            if command_group is not None and command_group.get('id').startswith('command_group'):
                remove_from_parent(command_group)
            else:
                remove_from_parent(command.connector)
                remove_from_parent(command.use)
        remove_from_parent(element.node)


def remove_from_parent(node):
    if node.getparent() is not None:
        node.getparent().remove(node)


def create_new_group(parent, insert_index, label):
    group = inkex.Group(attrib={
        INKSCAPE_LABEL: label,
        "transform": get_correction_transform(parent, child=True)
    })
    parent.insert(insert_index, group)

    return group