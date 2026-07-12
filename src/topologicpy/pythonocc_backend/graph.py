from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from .helpers import new_uuid, same_vertex, unique_by_uuid
from .dictionary import Dictionary
from .vertex import Vertex
from .edge import Edge


@dataclass(eq=False)
class Graph:
    vertices: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    dictionary: Any = field(default_factory=dict)
    _uuid: str = field(default_factory=new_uuid)

    def __hash__(self):
        return hash(self._uuid)

    def GetTypeAsString(self):
        return "Graph"

    def SetDictionary(self, dictionary):
        if dictionary is None:
            self.dictionary = {}
        elif isinstance(dictionary, (dict, Dictionary)):
            self.dictionary = dictionary
        elif hasattr(dictionary, "_data") and isinstance(dictionary._data, dict):
            self.dictionary = dictionary
        elif hasattr(dictionary, "data") and isinstance(dictionary.data, dict):
            self.dictionary = dictionary
        else:
            self.dictionary = {}
        return self

    def GetDictionary(self):
        if self.dictionary is None:
            self.dictionary = {}
        return self.dictionary

    def Dictionary(self):
        if self.dictionary is None:
            self.dictionary = {}
        return self.dictionary

    @staticmethod
    def ByVerticesEdges(vertices, edges):
        vertices = [v for v in (vertices or []) if isinstance(v, Vertex)]
        edges = [e for e in (edges or []) if isinstance(e, Edge)]
        for edge in edges:
            if edge.start not in vertices:
                vertices.append(edge.start)
            if edge.end not in vertices:
                vertices.append(edge.end)
        return Graph(vertices=unique_by_uuid(vertices), edges=unique_by_uuid(edges))

    @staticmethod
    def ByVertices(vertices):
        return Graph.ByVerticesEdges(vertices, [])

    def Vertices(self, vertices=None):
        result = list(getattr(self, "vertices", []) or [])
        if vertices is not None:
            vertices.extend(result)
            return 0
        return result

    def Edges(self, edges=None, tolerance=0.0001):
        result = list(getattr(self, "edges", []) or [])
        if edges is not None and isinstance(edges, list):
            edges.extend(result)
            return 0
        return result

    def AdjacentVertices(self, vertex, vertices=None):
        result = []
        if isinstance(vertex, Vertex):
            for edge in self.edges:
                if same_vertex(edge.start, vertex):
                    result.append(edge.end)
                elif same_vertex(edge.end, vertex):
                    result.append(edge.start)
        result = unique_by_uuid(result)
        if vertices is not None:
            vertices.extend(result)
            return 0
        return result

    def Edge(self, vertexA, vertexB, tolerance=0.0001):
        for edge in self.edges:
            if (
                same_vertex(edge.start, vertexA, tolerance)
                and same_vertex(edge.end, vertexB, tolerance)
            ) or (
                same_vertex(edge.start, vertexB, tolerance)
                and same_vertex(edge.end, vertexA, tolerance)
            ):
                return edge
        return None

    def AddVertex(self, vertex):
        if isinstance(vertex, Vertex):
            self.vertices = unique_by_uuid(self.vertices + [vertex])
        return self

    def AddEdge(self, edge):
        if isinstance(edge, Edge):
            self.edges = unique_by_uuid(self.edges + [edge])
            self.vertices = unique_by_uuid(self.vertices + [edge.start, edge.end])
        return self

    def AddVertices(self, vertices, tolerance=0.0001):
        new_vertices = [v for v in (vertices or []) if isinstance(v, Vertex)]
        if new_vertices:
            self.vertices = unique_by_uuid(self.vertices + new_vertices)
        return self

    def RemoveVertices(self, vertices):
        to_remove = [v for v in (vertices or []) if isinstance(v, Vertex)]
        if not to_remove:
            return self
        self.vertices = [
            v for v in self.vertices
            if not any(same_vertex(v, r) for r in to_remove)
        ]
        self.edges = [
            e for e in self.edges
            if not any(same_vertex(e.start, r) or same_vertex(e.end, r) for r in to_remove)
        ]
        return self

    def RemoveEdges(self, edges, tolerance=0.0001):
        to_remove = [e for e in (edges or []) if isinstance(e, Edge)]
        if not to_remove:
            return self

        def _same_edge(a, b):
            return (
                same_vertex(a.start, b.start, tolerance) and same_vertex(a.end, b.end, tolerance)
            ) or (
                same_vertex(a.start, b.end, tolerance) and same_vertex(a.end, b.start, tolerance)
            )

        self.edges = [
            e for e in self.edges
            if not any(_same_edge(e, r) for r in to_remove)
        ]
        return self

    def Connect(self, verticesA, verticesB, tolerance=0.0001):
        verticesA = [v for v in (verticesA or []) if isinstance(v, Vertex)]
        verticesB = [v for v in (verticesB or []) if isinstance(v, Vertex)]
        for va, vb in zip(verticesA, verticesB):
            if same_vertex(va, vb, tolerance):
                continue
            existing = self.Edge(va, vb, tolerance=tolerance)
            if existing is not None:
                continue
            edge = Edge.ByStartVertexEndVertex(va, vb)
            if edge is not None:
                self.AddEdge(edge)
        return self

    def ContainsVertex(self, vertex, tolerance=0.0001):
        if not isinstance(vertex, Vertex):
            return False
        return any(same_vertex(v, vertex, tolerance) for v in self.vertices)

    def ContainsEdge(self, edge, tolerance=0.0001):
        if not isinstance(edge, Edge):
            return False
        for e in self.edges:
            if (
                same_vertex(e.start, edge.start, tolerance)
                and same_vertex(e.end, edge.end, tolerance)
            ) or (
                same_vertex(e.start, edge.end, tolerance)
                and same_vertex(e.end, edge.start, tolerance)
            ):
                return True
        return False

    def _degree(self, vertex, tolerance=0.0001):
        degree = 0
        for edge in self.edges:
            if same_vertex(edge.start, vertex, tolerance):
                degree += 1
            if same_vertex(edge.end, vertex, tolerance):
                degree += 1
        return degree

    def DegreeSequence(self, sequence=None):
        result = sorted((self._degree(v) for v in self.vertices), reverse=True)
        if sequence is not None:
            sequence.extend(result)
            return 0
        return result

    def Density(self):
        n = len(self.vertices)
        m = len(self.edges)
        if n < 2:
            return 0.0
        return float(2.0 * m) / float(n * (n - 1))

    def IsolatedVertices(self, vertices=None):
        result = [v for v in self.vertices if self._degree(v) == 0]
        if vertices is not None:
            vertices.extend(result)
            return 0
        return result

    def AllPaths(self, vertexA, vertexB, searchLimitFlag=True, timeLimit=10, output=None):
        import time as _time
        from .wire import Wire

        if output is None:
            output = []
        if not isinstance(vertexA, Vertex) or not isinstance(vertexB, Vertex):
            return 0

        adjacency = {}
        for edge in self.edges:
            adjacency.setdefault(id(edge.start), []).append((edge.end, edge))
            adjacency.setdefault(id(edge.end), []).append((edge.start, edge))

        start_key = None
        for v in self.vertices:
            if same_vertex(v, vertexA):
                start_key = id(v)
                break
        if start_key is None:
            return 0

        end_time = _time.time() + timeLimit if searchLimitFlag else float("inf")
        max_paths = 1000

        results = []
        visited_ids = set()

        def _dfs(current_vertex, path_edges, visited_ids):
            if _time.time() > end_time or len(results) >= max_paths:
                return
            if same_vertex(current_vertex, vertexB):
                if path_edges:
                    results.append(list(path_edges))
                return
            neighbors = adjacency.get(id(current_vertex), [])
            for next_vertex, edge in neighbors:
                if id(next_vertex) in visited_ids:
                    continue
                visited_ids.add(id(next_vertex))
                path_edges.append(edge)
                _dfs(next_vertex, path_edges, visited_ids)
                path_edges.pop()
                visited_ids.discard(id(next_vertex))
                if _time.time() > end_time or len(results) >= max_paths:
                    return

        visited_ids.add(start_key)
        _dfs(vertexA, [], visited_ids)

        for path_edges in results:
            oriented = self._oriented_edge_chain(path_edges, vertexA)
            wire = Wire.ByEdges(oriented if oriented is not None else path_edges)
            if wire is not None:
                output.append(wire)

        return 0

    @staticmethod
    def _oriented_edge_chain(path_edges, start_vertex, tolerance=0.0001):
        """
        Given a list of edges that form a connected chain (as produced by a
        vertex-to-vertex traversal starting at start_vertex), return a new list
        of edges whose .start/.end are oriented head-to-tail along that chain.
        Edges that already point the right way are reused as-is; edges that
        point backwards are replaced with a reversed copy (dictionary preserved).
        This avoids relying on Wire._order_edges' own (buggy) direction-matching
        when handed edges that are logically chained but not all stored
        head-to-tail.
        """
        if not path_edges:
            return None
        oriented = []
        current = start_vertex
        for edge in path_edges:
            if same_vertex(edge.start, current, tolerance):
                oriented.append(edge)
                current = edge.end
            elif same_vertex(edge.end, current, tolerance):
                flipped = Edge.ByStartVertexEndVertex(edge.end, edge.start)
                if flipped is None:
                    return None
                flipped.dictionary = edge.dictionary
                oriented.append(flipped)
                current = edge.start
            else:
                return None
        return oriented

    def Topology(self):
        from .cluster import Cluster

        topologies = list(self.vertices) + list(self.edges)
        return Cluster.ByTopologies(topologies)

    def Path(self, vertexA, vertexB, tolerance=0.0001):
        from .wire import Wire

        paths = []
        self.AllPaths(vertexA, vertexB, True, 10, paths)
        if not paths:
            return None
        # Prefer the shortest path (fewest edges) as a reasonable default.
        return min(paths, key=lambda w: len(getattr(w, "edges", []) or []))

    def IsComplete(self):
        n = len(self.vertices)
        if n < 2:
            return True
        max_edges = n * (n - 1) / 2.0
        # Count unique undirected edges.
        seen = set()
        for e in self.edges:
            seen.add(frozenset((id(e.start), id(e.end))))
        return len(seen) >= max_edges

    def IsErdoesGallai(self, sequence):
        seq = sorted([s for s in (sequence or [])], reverse=True)
        n = len(seq)
        if n == 0:
            return True
        if sum(seq) % 2 != 0:
            return False
        for k in range(1, n + 1):
            lhs = sum(seq[:k])
            rhs = k * (k - 1) + sum(min(seq[i], k) for i in range(k, n))
            if lhs > rhs:
                return False
        return True

    def MaximumDelta(self):
        if not self.vertices:
            return 0
        return max(self._degree(v) for v in self.vertices)

    def MinimumDelta(self):
        if not self.vertices:
            return 0
        return min(self._degree(v) for v in self.vertices)

    def GetGUID(self):
        return self._uuid


class GraphUtility:
    pass

# ---------------------------------------------------------------------------
# Explicit unsupported Graph API
# ---------------------------------------------------------------------------
from .helpers import not_implemented as _not_implemented


def _graph_not_implemented(name, return_value=None):
    def _method(*args, **kwargs):
        return _not_implemented(f"Graph.{name}", return_value)
    return _method


def _graph_utility_not_implemented(name, return_value=None):
    def _method(*args, **kwargs):
        return _not_implemented(f"GraphUtility.{name}", return_value)
    return _method


Graph.ByTopology = staticmethod(_graph_not_implemented("ByTopology"))
Graph.ByAdjacencyMatrix = staticmethod(_graph_not_implemented("ByAdjacencyMatrix"))
Graph.RemoveVertex = _graph_not_implemented("RemoveVertex")
Graph.RemoveEdge = _graph_not_implemented("RemoveEdge")
Graph.ShortestPath = _graph_not_implemented("ShortestPath")
GraphUtility.AdjacentVertices = staticmethod(_graph_utility_not_implemented("AdjacentVertices"))
GraphUtility.ShortestPath = staticmethod(_graph_utility_not_implemented("ShortestPath"))
