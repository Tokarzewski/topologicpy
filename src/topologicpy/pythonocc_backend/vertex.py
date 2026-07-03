from __future__ import annotations

from dataclasses import dataclass
from .topology import Topology, _shape_from_topology, _is_null_shape
from .occ_utils import make_occ_vertex
from .helpers import distance3, same_vertex, unique_by_uuid


@dataclass(eq=False)
class Vertex(Topology):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @staticmethod
    def ByCoordinates(x=0.0, y=0.0, z=0.0):
        x = float(x); y = float(y); z = float(z)
        return Vertex(shape=make_occ_vertex(x, y, z), x=x, y=y, z=z)

    @staticmethod
    def ByPoint(point):
        try:
            return Vertex.ByCoordinates(point.X(), point.Y(), point.Z())
        except Exception:
            return None

    @staticmethod
    def ByOcctShape(shape, dictionary=None, contents=None, contexts=None, apertures=None):
        try:
            from OCC.Core.BRep import BRep_Tool
            pnt = BRep_Tool.Pnt(shape)
            x, y, z = pnt.X(), pnt.Y(), pnt.Z()
        except Exception:
            return None
        v = Vertex(shape=shape, x=float(x), y=float(y), z=float(z))
        v.dictionary = dictionary
        v.contents = list(contents) if contents else []
        v.contexts = list(contexts) if contexts else []
        v.apertures = list(apertures) if apertures else []
        return v

    def X(self):
        return float(self.x)

    def Y(self):
        return float(self.y)

    def Z(self):
        return float(self.z)

    def Coordinates(self):
        return [self.x, self.y, self.z]

    def Vertices(self, hostTopology=None, vertices=None):
        result = [self]
        if vertices is not None:
            vertices.extend(result)
            return 0
        return result

    @staticmethod
    def ByCoordinatesString(coordinatesString, separator=","):
        """
        Not part of the guide's minimum checklist and not called by the
        topologicpy algorithm layer (verified: zero call sites), but a real
        `topologic_core.Vertex.ByCoordinatesString` exists, so provide a
        genuine best-effort implementation for direct Core callers: parse
        "x,y,z" (or a caller-supplied separator) into a Vertex.
        """
        if not isinstance(coordinatesString, str):
            return None
        try:
            parts = [p.strip() for p in coordinatesString.split(separator)]
            parts = [p for p in parts if p != ""]
            if len(parts) < 2 or len(parts) > 3:
                return None
            x = float(parts[0])
            y = float(parts[1])
            z = float(parts[2]) if len(parts) == 3 else 0.0
        except (ValueError, IndexError):
            return None
        return Vertex.ByCoordinates(x, y, z)

    @staticmethod
    def Project(vertex, topology, direction=None):
        """
        Not part of the guide's minimum checklist and not called by the
        topologicpy algorithm layer (topologicpy.Vertex.Project is a
        self-contained plane-equation implementation that never reaches
        Core). Best-effort real implementation for direct Core callers:
        projects the vertex onto the target topology's OCCT shape.

        If `direction` is given (a 3-sequence), projects along that ray;
        otherwise returns the nearest point on the target shape (matching
        BRepExtrema_DistShapeShape's default closest-point behavior, which is
        what a normal-direction planar projection reduces to for a Face).
        """
        if not isinstance(vertex, Vertex):
            return None
        target_shape = _shape_from_topology(topology)
        if _is_null_shape(target_shape):
            return None
        try:
            if direction is not None:
                from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Lin
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
                from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
                dx, dy, dz = float(direction[0]), float(direction[1]), float(direction[2])
                norm = (dx ** 2 + dy ** 2 + dz ** 2) ** 0.5
                if norm <= 0:
                    return None
                origin = gp_Pnt(vertex.x, vertex.y, vertex.z)
                line = gp_Lin(origin, gp_Dir(dx, dy, dz))
                # A very long edge along the ray approximates an infinite line
                # for BRepExtrema_DistShapeShape purposes.
                big = 1.0e6
                ray_shape = BRepBuilderAPI_MakeEdge(line, -big, big).Edge()
                dist_calc = BRepExtrema_DistShapeShape(ray_shape, target_shape)
            else:
                from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
                dist_calc = BRepExtrema_DistShapeShape(vertex.shape, target_shape)
            if not dist_calc.IsDone() or dist_calc.NbSolution() < 1:
                return None
            pnt = dist_calc.PointOnShape2(1)
            return Vertex.ByCoordinates(pnt.X(), pnt.Y(), pnt.Z())
        except Exception:
            return None

    def Fuse(self, otherTopology):
        """
        Not part of the guide's minimum checklist and not called by the
        topologicpy algorithm layer (topologicpy.Vertex.Fuse is an unrelated,
        self-contained list-dedup helper that never reaches Core). Instance
        method (not @staticmethod) so both calling conventions work. Mirrors
        real topologic_core.Vertex.Fuse: a boolean union of two vertices,
        which is the coincident vertex itself if they are the same point,
        otherwise a Cluster of both.
        """
        if not isinstance(otherTopology, Vertex):
            return None
        if same_vertex(self, otherTopology):
            return self
        from .cluster import Cluster
        return Cluster.ByTopologies([self, otherTopology])


class VertexUtility:
    @staticmethod
    def Distance(vertexA, vertexB):
        if isinstance(vertexA, Vertex) and isinstance(vertexB, Vertex):
            return distance3(vertexA, vertexB)
        return None

    @staticmethod
    def NearestVertex(vertex, topology, useKDTree=True):
        """
        Not part of the guide's minimum checklist and not called by the
        topologicpy algorithm layer (topologicpy.Vertex.NearestVertex is a
        self-contained implementation that never reaches Core). Best-effort
        real implementation for direct Core callers: linear-scan the target
        topology's vertices for the closest one (useKDTree is accepted for
        API compatibility but not needed at this scale).
        """
        if not isinstance(vertex, Vertex) or not isinstance(topology, Topology):
            return None
        candidates = []
        topology.Vertices(None, candidates)
        candidates = [v for v in candidates if isinstance(v, Vertex)]
        if not candidates:
            return None
        return min(candidates, key=lambda v: distance3(vertex, v))

    @staticmethod
    def ParameterAtVertex(edge, vertex):
        """
        Not part of the guide's minimum checklist and not called by the
        topologicpy algorithm layer (Edge.ParameterAtPoint / EdgeUtility.
        ParameterAtPoint already cover this via a different namespace).
        Best-effort real implementation for direct Core callers: delegates to
        EdgeUtility.ParameterAtPoint, matching legacy topologic_core naming
        (VertexUtility.ParameterAtVertex is an alias for the same concept).
        """
        from .edge import EdgeUtility
        return EdgeUtility.ParameterAtPoint(edge, vertex)

    @staticmethod
    def AdjacentEdges(vertex, topology, edges):
        from .edge import Edge
        from .graph import Graph
        if not isinstance(vertex, Vertex):
            return 1
        result = []
        if isinstance(topology, Graph):
            for edge in topology.edges:
                if same_vertex(edge.start, vertex) or same_vertex(edge.end, vertex):
                    result.append(edge)
        elif isinstance(topology, Topology):
            temp = []
            topology.Edges(None, temp)
            for edge in temp:
                if isinstance(edge, Edge) and (same_vertex(edge.start, vertex) or same_vertex(edge.end, vertex)):
                    result.append(edge)
        edges.extend(unique_by_uuid(result))
        return 0

# ---------------------------------------------------------------------------
# Explicit unsupported Vertex API
# ---------------------------------------------------------------------------
from .helpers import not_implemented as _not_implemented


def _vertex_not_implemented(name, return_value=None):
    def _method(*args, **kwargs):
        return _not_implemented(f"Vertex.{name}", return_value)
    return _method


def _vertex_utility_not_implemented(name, return_value=None):
    def _method(*args, **kwargs):
        return _not_implemented(f"VertexUtility.{name}", return_value)
    return _method


Vertex.Origin = staticmethod(lambda: Vertex.ByCoordinates(0.0, 0.0, 0.0))
# Vertex.ByCoordinatesString, Vertex.Project, Vertex.Fuse, VertexUtility.NearestVertex,
# and VertexUtility.ParameterAtVertex now have real implementations defined on the
# classes above -- do not re-clobber them here (see gotcha about stub assignments
# silently overriding real implementations added earlier in the file).
