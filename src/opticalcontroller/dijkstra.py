# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# TODO: migrate to NetworkX:
# https://networkx.org/documentation/stable/index.html
# https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html

import sys

class Vertex:
    def __init__(self, node):
        self.id = node
        self.adjacent = {}
        # Set distance to infinity for all nodes
        self.distance = float("inf")
        # Mark all nodes unvisited        
        self.visited = False  
        # Predecessor
        self.previous = None

    # heapq compara gli item nella coda usando <= per vedere ci sono duplciati: 
    # se ho una coda di tuple, 
    # compara il primo elemento della prima tupla nella coda con il primo elemento della seconda tupla nella coda
    # se sono diversi si ferma, se sono uguali continua
    # la tupla nel caso in esame è: (v.get_distance(),v)
    # se due nodi hanno stessa distanza, heapq procede a comparare v: Vertex().
    # Va quindi definita una politica per confrontare i Vertex
    def __lt__(self, other):
        if self.id < other.id:
            return True
        else:
            return False
        
    def __le__(self, other):
        if self.id <= other.id:
            return True
        else:
            return False

    def add_neighbor(self, neighbor, port):
        self.adjacent[neighbor] = port

    def del_neighbor(self, neighbor):
        self.adjacent.pop(neighbor)

    def get_connections(self):
        return self.adjacent.keys()  

    def get_id(self):
        return self.id

    def get_port(self, neighbor):
        return self.adjacent[neighbor][0]
    
    def get_weight(self, neighbor):
        return self.adjacent[neighbor][1]

    def set_distance(self, dist):
        self.distance = dist

    def get_distance(self):
        return self.distance

    def set_previous(self, prev):
        self.previous = prev

    def set_visited(self):
        self.visited = True

    def reset_vertex(self):
        self.visited = False
        self.previous = None
        self.distance = float("inf")

    def __str__(self):
        return str(self.id) + ' adjacent: ' + str([x.id for x in self.adjacent])

class Graph:
    def __init__(self):
        self.vert_dict = {}
        self.num_vertices = 0

    def __iter__(self):
        return iter(self.vert_dict.values())
    
    def reset_graph(self):
        for n in self.vert_dict:
            self.get_vertex(n).reset_vertex()

    def printGraph(self):
        for v in self:
            for w in v.get_connections():
                vid = v.get_id()
                wid = w.get_id()
                print ('( %s , %s, %s, %s, %s, %s)'  % ( vid, wid, v.get_port(w), w.get_port(v), v.get_weight(w), w.get_weight(v)))

    def add_vertex(self, node):
        self.num_vertices = self.num_vertices + 1
        new_vertex = Vertex(node)
        self.vert_dict[node] = new_vertex
        return new_vertex
    
    def del_Vertex(self, node):
        self.vert_dict.pop(node)

    def get_vertex(self, n):
        if n in self.vert_dict:
            return self.vert_dict[n]
        else:
            return None

    def add_edge(self, frm, to, port_frm, port_to,w):
        if frm not in self.vert_dict:
            self.add_vertex(frm)
        if to not in self.vert_dict:
            self.add_vertex(to)

        self.vert_dict[frm].add_neighbor(self.vert_dict[to], [port_frm, w])
        self.vert_dict[to].add_neighbor(self.vert_dict[frm], [port_to, w])

    '''
    def del_edge(self, frm, to, cost = 0):
        self.vert_dict[frm].del_neighbor(self.vert_dict[to])
        self.vert_dict[to].del_neighbor(self.vert_dict[frm])
    '''

    def del_edge(self, frm, to, cost=0):
        if frm in self.vert_dict and to in self.vert_dict:
            v_from = self.vert_dict[frm]
            v_to = self.vert_dict[to]
            if v_to in v_from.adjacent:
                v_from.del_neighbor(v_to)
            if v_from in v_to.adjacent:
                v_to.del_neighbor(v_from)

    def get_vertices(self):
        return self.vert_dict.keys()

    def set_previous(self, current):
        self.previous = current

    def get_previous(self, current):
        return self.previous

    def copy(self):
        """
        Returns a deep copy of the graph (vertices, edges, ports, and weights).
        """
        new_graph = Graph()

        # First, create all vertices
        for node_id in self.vert_dict:
            new_graph.add_vertex(node_id)

        # Then, add all edges with the same attributes
        for v in self:
            for neighbor in v.get_connections():
                frm = v.get_id()
                to = neighbor.get_id()
                port_frm = v.get_port(neighbor)
                port_to = neighbor.get_port(v)
                weight = v.get_weight(neighbor)
                
                # To avoid adding the same undirected edge twice
                if frm < to:
                    new_graph.add_edge(frm, to, port_frm, port_to, weight)

        return new_graph

    def copy2(self):
        new_g = Graph()
        # Copy vertices
        for node_id in self.vert_dict:
            new_g.add_vertex(node_id)
        # Copy edges
        for frm in self.vert_dict:
            for to in self.vert_dict[frm].adjacent:
                port_frm, weight = self.vert_dict[frm].adjacent[to]
                port_to, _ = self.vert_dict[to].adjacent[frm]
                if not new_g.get_vertex(frm).adjacent.get(new_g.get_vertex(to)):
                    new_g.add_edge(frm, to.get_id(), port_frm, port_to, weight)
        return new_g

def shortest(v, path):
    if v.previous:
        path.append(v.previous.get_id())
        shortest(v.previous, path)
    return

import heapq

def dijkstra(aGraph, start):
    """print ('''Dijkstra's shortest path''')"""
    # Set the distance for the start node to zero 
    start.set_distance(0)

    # Put tuple pair into the priority queue
    unvisited_queue = [(v.get_distance(),v) for v in aGraph]
    #priority queue->costruisce un albero in cui ogni nodo parent ha  ha un valore <= di ogni child
    #heappop prende il valore più piccolo, nel caso di dikstra, il nodo più vicino
    heapq.heapify(unvisited_queue)

    while len(unvisited_queue):
        # Pops a vertex with the smallest distance 
        uv = heapq.heappop(unvisited_queue)
        current = uv[1]
        current.set_visited()

        #for next in v.adjacent:
        for next in current.adjacent:
            # if visited, skip
            if next.visited:
                continue
            new_dist = current.get_distance() + current.get_weight(next)
            
            if new_dist < next.get_distance():
                next.set_distance(new_dist)
                next.set_previous(current)
                """print ('updated : current = %s next = %s new_dist = %s' \
                        %(current.get_id(), next.get_id(), next.get_distance()))"""
            else:
                """print ('not updated : current = %s next = %s new_dist = %s' \
                        %(current.get_id(), next.get_id(), next.get_distance()))"""

        # Rebuild heap
        # 1. Pop every item
        while len(unvisited_queue):
            heapq.heappop(unvisited_queue)
        # 2. Put all vertices not visited into the queue
        unvisited_queue = [(v.get_distance(),v) for v in aGraph if not v.visited]
        heapq.heapify(unvisited_queue)
        
def shortest_path(graph, src, dst):
    dijkstra(graph, src)
    target = dst
    path = [target.get_id()]
    shortest(target, path)
    return path[::-1]


def compute_disjoint_paths(graph, src, dst, k=2, disjoint_type="link", debug=False):
    """
    Compute up to k disjoint shortest paths between src and dst using Dijkstra.
    disjoint_type: "link" (edge-disjoint) or "node" (vertex-disjoint)
    """
    
    paths = []
    removed_edges = []  # Keep track of removed edges
    removed_nodes = []  # Keep track of removed nodes

    for i in range(k):
        # Compute shortest path using the existing Dijkstra-based function
        path = shortest_path(graph, src, dst)

        # Stop if no valid path found
        if not path or len(path) < 2:
            if debug:
                print(f"[INFO] No more disjoint paths found after {i} iterations.")
            break

        paths.append(path)
        if debug:
            print(f"[INFO] Path {i+1}: {path}")

        # Depending on disjointness type, remove edges or nodes from graph
        if disjoint_type == "link":
            for u, v in zip(path[:-1], path[1:]):
                if debug:
                    print(f"  Removing edge {u}-{v}")
                removed_edges.append((u, v))
                # Remove edge in both directions
                graph.del_edge(u, v)

        elif disjoint_type == "node":
            # Remove intermediate nodes (not source or destination)
            for n in path[1:-1]:
                if debug:
                    print(f"  Removing node {n}")
                removed_nodes.append(n)
                # Remove all edges involving this node
                v = graph.get_vertex(n)
                if v is not None:
                    for neighbor in list(v.get_connections()):
                        graph.del_edge(n, neighbor.get_id())
                    graph.del_Vertex(n)
        else:
            raise ValueError("disjoint_type must be 'link' or 'node'")

        # Reset distances & visited flags for the next run
        graph.reset_graph()

    if debug:
        print(f"[INFO] Found {len(paths)} disjoint paths.")

    return paths

def disjoint_path(graph, src_id, dst_id, pathz, debug=False):
    g2 = graph.copy()
    src = g2.get_vertex(src_id)
    dst = g2.get_vertex(dst_id)
    removed_edges = []  # Keep track of removed edges
    removed_nodes = []  # Keep track of removed nodes
    for u, v in zip(pathz[:-1], pathz[1:]):
       if debug:
          print(f"  Removing edge {u}-{v}") 
       removed_edges.append((u, v))
       # Remove edge in both directions
       g2.del_edge(u, v)
    # Compute shortest path using the existing Dijkstra-based function
    g2.reset_graph()
    pathx = shortest_path(g2, src, dst)

    # Stop if no valid path found
    if not pathx or len(pathx) < 2:
        if debug:
            print(f"[INFO] No more disjoint paths found.")
            return []

    g2.reset_graph()

    return pathx


if __name__ == '__main__':

    print("Testing Algo")
    g = Graph()

    g.add_vertex('a')
    g.add_vertex('b')
    g.add_vertex('c')
    g.add_vertex('d')
    g.add_vertex('e')
    g.add_vertex('f')

    g.add_edge('a', 'b', 1, 1, 7)  
    g.add_edge('a', 'c', 2, 1, 9)
    g.add_edge('a', 'f', 3, 1, 14)
    g.add_edge('b', 'c', 2, 2, 10)
    g.add_edge('b', 'd', 3, 1, 15)
    g.add_edge('c', 'd', 3, 2, 11)
    g.add_edge('c', 'f', 4, 2, 2)
    g.add_edge('d', 'e', 4, 1, 6)
    g.add_edge('e', 'f', 2, 3, 9)


    """print ('Graph data:')
    for v in g:
        for w in v.get_connections():
            vid = v.get_id()
            wid = w.get_id()
            print ('( %s , %s, %3d)'  % ( vid, wid, v.get_weight(w)))

            
    dijkstra(g, g.get_vertex('a')) 

    target = g.get_vertex('e')
    path = [target.get_id()]
    shortest(target, path)
    print ('The shortest path : %s' %(path[::-1]))"""
    #print(g.printGraph())
    pat = shortest_path(g, g.get_vertex('a'), g.get_vertex('e'))
    print(pat)
    
    #paths = compute_disjoint_paths(g, g.get_vertex('a'), g.get_vertex('e'), k=2, disjoint_type="link", debug=False)
    #paths = compute_disjoint_paths(g, g.get_vertex('a'), g.get_vertex('e'), k=2, disjoint_type="link", debug=False)
    #print(paths)
    path2 = compute_disjoint_path(g, 'a', 'e', pat, False)
    print(path2)
    
    pat = shortest_path(g, g.get_vertex('a'), g.get_vertex('d'))
    print(pat)
    path2 = compute_disjoint_path(g, 'a', 'd', pat, False)
    print(path2)