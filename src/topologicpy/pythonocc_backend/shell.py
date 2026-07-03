from __future__ import annotations

import types
from dataclasses import dataclass
from .topology import Topology
from .face import Face, FaceUtility
from .edge import Edge
from .vertex import Vertex
from .occ_utils import make_occ_shell
from .helpers import unique_by_uuid, edge_key, vertex_key


@dataclass(eq=False)
class Shell(Topology):
    def __init__(self, shape=None, dictionary=None, contents=None, contexts=None, apertures=None, faces=None):
        super().__init__(shape=shape, dictionary=dictionary, contents=contents, contexts=contexts, apertures=apertures)
        self.faces = list(faces) if faces else []

    @staticmethod
    def ByFaces(faces, tolerance: float = 0.0001, silent: bool = False):
        if faces is None:
            if not silent:
                print("Shell.ByFaces - Error: The input faces parameter is None. Returning None.")
            return None
        if not isinstance(faces, list):
            faces = [faces]
        valid_faces = [face for face in faces if Topology.IsInstance(face, "Face")]
        if len(valid_faces) == 0:
            if not silent:
                print("Shell.ByFaces - Error: The input faces list does not contain any valid faces. Returning None.")
            return None
        occ_shell = make_occ_shell(valid_faces)
        if occ_shell is None:
            if not silent:
                print("Shell.ByFaces - Error: Could not create an OpenCascade shell. Returning None.")
            return None
        shell = Shell(shape=occ_shell, faces=valid_faces)
        Shell._patch_edge_face_membership(shell, valid_faces, tolerance=tolerance)
        return shell

    @staticmethod
    def _edge_face_incidence(faces, tolerance: float = 0.0001):
        """
        Builds a mapping from a geometric edge key (endpoint coordinates,
        order-independent, rounded to tolerance) to the list of (face, edge)
        pairs that own an edge at that location.

        Faces built independently (e.g. via Face.ByVertices) do not share
        underlying OCCT edge sub-shapes even when they are geometrically
        coincident, so incidence must be computed by endpoint geometry
        (edge_key) rather than by OCCT shape identity/hash.
        """
        incidence = {}
        for face in faces:
            if not isinstance(face, Face):
                continue
            for edge in face.Edges():
                if not isinstance(edge, Edge):
                    continue
                key = edge_key(edge, tolerance)
                incidence.setdefault(key, []).append((face, edge))
        return incidence

    @staticmethod
    def _patch_edge_face_membership(shell, faces, tolerance: float = 0.0001):
        """
        Monkeypatches a per-instance Faces(hostTopology, output) method onto
        every edge belonging to the given faces, so that
        Topology.SuperTopologies(edge, shell, topologyType="face") (which
        dispatches to Core.InstanceCall(edge, 'Faces', hostTopology, output),
        i.e. edge.Faces(hostTopology, output)) can report which face(s) of
        *this* shell actually own that edge.

        The generic Topology.Faces base-class dispatcher does not use
        hostTopology as a filter (it only understands "does self carry its
        own faces list", which a bare Edge never does), so without this an
        edge's super-face count is always 0 regardless of the shell passed
        in. This is what breaks the algorithm-layer Shell.ExternalBoundary
        (src/topologicpy/Shell.py), which relies on exactly that mechanism
        to tell boundary edges (1 owning face) from internal edges (2).

        The same underlying Face/Edge Python objects can legitimately be
        reused across more than one Shell.ByFaces call in the same session
        (e.g. a test building both a closed 6-face box shell and a 1-face
        open shell out of one shared face) -- each such shell has a
        different notion of "how many faces of *this* shell own this edge".
        A naive single "this edge's owning faces" monkeypatch would get
        silently overwritten by whichever Shell was built most recently
        sharing that edge, corrupting *other*, still-alive Shells built
        earlier from the same face. So each edge instead accumulates a
        {id(shell): owning_faces} map across every Shell.ByFaces call that
        touches it, and the patched Faces() looks up by the hostTopology
        actually passed in (falling back to the map's only entry, or to the
        most recently added one, if hostTopology is None/unrecognised --
        matching the "None is no filter" convention used elsewhere).
        """
        incidence = Shell._edge_face_incidence(faces, tolerance=tolerance)
        seen = set()
        for face in faces:
            if not isinstance(face, Face):
                continue
            for edge in face.Edges():
                if not isinstance(edge, Edge) or id(edge) in seen:
                    continue
                seen.add(id(edge))
                key = edge_key(edge, tolerance)
                owning_faces = unique_by_uuid([f for f, _ in incidence.get(key, [])])

                by_host = getattr(edge, "_shell_faces_by_host", None)
                if by_host is None:
                    by_host = {}
                    edge._shell_faces_by_host = by_host
                by_host[id(shell)] = owning_faces

                if not getattr(edge, "_shell_faces_patched", False):
                    edge._shell_faces_patched = True

                    def _edge_faces(self, hostTopology=None, output=None):
                        host_map = getattr(self, "_shell_faces_by_host", None) or {}
                        if hostTopology is not None and id(hostTopology) in host_map:
                            result = list(host_map[id(hostTopology)])
                        elif host_map:
                            # No (recognised) host given: fall back to the most
                            # recently recorded context for this edge.
                            result = list(next(reversed(list(host_map.values()))))
                        else:
                            result = []
                        if output is not None:
                            output.extend(result)
                            return 0
                        return result

                    edge.Faces = types.MethodType(_edge_faces, edge)

    def Faces(self, hostTopology=None, faces=None):
        result = list(getattr(self, "faces", []) or [])
        if faces is not None:
            faces.extend(result)
            return 0
        return result

    def Edges(self, hostTopology=None, edges=None):
        result = []
        for face in getattr(self, "faces", []) or []:
            if isinstance(face, Face):
                result.extend(face.Edges())
        result = unique_by_uuid(result)
        result = Shell._boundary_first_ordering(result, host=self)
        if edges is not None:
            edges.extend(result)
            return 0
        return result

    @staticmethod
    def _boundary_first_ordering(edges, host=None, tolerance: float = 0.0001):
        """
        Reorders a flat edge list so that the free/boundary edges (the ones
        with exactly one owning face, once .Faces() is patched -- see
        _patch_edge_face_membership) come first, walk-ordered (or grouped
        into walk-ordered disjoint chains via Wire._order_edges), followed by
        the remaining (internal/shared) edges in their original order.

        Why this matters: the algorithm-layer Shell.ExternalBoundary
        (src/topologicpy/Shell.py) computes
            ebEdges = [e for e in Topology.Edges(shell) if <e has 1 owning face>]
        i.e. it filters *this* method's output down to just the boundary
        edges, then does Topology.SelfMerge(Cluster.ByTopologies(ebEdges)).
        That SelfMerge path (Topology._merge_edges_into_wires, out of this
        file's scope) rebuilds a Wire's .edges list via TopExp_Explorer
        traversal of the OCCT wire it constructs from whatever order it was
        given the edges in -- empirically, in this pythonocc version, that
        traversal reproduces true walk order only when the edges were fed to
        BRepBuilderAPI_MakeWire in walk order (and consistently oriented --
        not just "adjacent", but continuing in the same rotational sense)
        already. If ebEdges preserves this method's relative order but that
        order is scrambled, the rebuilt Wire ends up topologically closed
        but with a .edges list that fails the naive edges[0].start ==
        edges[-1].end checks in the (also out-of-scope, deliberately
        untouched) Wire.IsClosed / Wire.Close, which breaks downstream
        Face.ByWire / Shell.SelfMerge calls.

        A plain single greedy walk over the full edge set is not enough: once
        the internal edges connecting two faces are filtered back out, each
        face's remaining boundary edges form their own short chain, and two
        such chains discovered by an undirected walk are not guaranteed to
        be co-orientable (one may need reversing relative to the other) --
        so the boundary subset must be computed and ordered on its own terms
        (via Wire._order_edges, which does handle per-edge reversal) rather
        than derived as a byproduct of a whole-shell walk.
        """
        from .wire import Wire

        edges = [e for e in edges if isinstance(e, Edge)]
        boundary_by_key = {}
        for e in edges:
            key = edge_key(e, tolerance)
            boundary_by_key.setdefault(key, []).append(e)

        boundary_edges = []
        other_edges = []
        seen_boundary_keys = set()
        for e in edges:
            faces_method = getattr(e, "Faces", None)
            owning = faces_method(host) if callable(faces_method) else None
            if isinstance(owning, list) and len(owning) == 1:
                key = edge_key(e, tolerance)
                if key not in seen_boundary_keys:
                    seen_boundary_keys.add(key)
                    boundary_edges.append(e)
            else:
                other_edges.append(e)

        if not boundary_edges:
            return edges

        remaining = list(boundary_edges)
        ordered_boundary = []
        while remaining:
            chain = Wire._order_edges(remaining, tolerance=tolerance)
            if chain is not None:
                ordered_boundary.extend(chain)
                break
            # Not a single simple chain: peel off connected components one at
            # a time (each is itself orderable) until none remain.
            component = [remaining[0]]
            frontier = True
            rest = remaining[1:]
            while frontier:
                frontier = False
                head_key = vertex_key(component[0].start, tolerance) if isinstance(component[0].start, Vertex) else None
                tail_key = vertex_key(component[-1].end, tolerance) if isinstance(component[-1].end, Vertex) else None
                for i, cand in enumerate(rest):
                    c_keys = (vertex_key(cand.start, tolerance), vertex_key(cand.end, tolerance))
                    if head_key in c_keys or tail_key in c_keys:
                        component.append(cand)
                        rest.pop(i)
                        frontier = True
                        break
            sub_order = Wire._order_edges(component, tolerance=tolerance)
            ordered_boundary.extend(sub_order if sub_order is not None else component)
            remaining = rest

        return ordered_boundary + other_edges

    def Vertices(self, hostTopology=None, vertices=None):
        result = []
        for edge in self.Edges():
            result.extend([edge.start, edge.end])
        result = unique_by_uuid([v for v in result if isinstance(v, Vertex)])
        if vertices is not None:
            vertices.extend(result)
            return 0
        return result

    def Shells(self, hostTopology=None, shells=None):
        result = [self]
        if shells is not None:
            shells.extend(result)
            return 0
        return result

    def IsClosed(self, tolerance: float = 0.0001):
        """
        A shell is closed when it has no free (boundary) edges, i.e. every
        edge is shared by exactly two of the shell's faces.
        """
        faces = getattr(self, "faces", []) or []
        if not faces:
            return False
        return len(Shell._boundary_edges(faces, tolerance=tolerance, min_count=1, max_count=1)) == 0

    @staticmethod
    def _boundary_edges(faces, tolerance: float = 0.0001, min_count=None, max_count=None):
        """
        Returns the Edge objects (one representative per geometric location)
        whose face-incidence count falls within [min_count, max_count]
        (either bound may be None to mean "unbounded").
        """
        incidence = Shell._edge_face_incidence(faces, tolerance=tolerance)
        result = []
        for pairs in incidence.values():
            count = len(pairs)
            if min_count is not None and count < min_count:
                continue
            if max_count is not None and count > max_count:
                continue
            result.append(pairs[0][1])
        return result

    @staticmethod
    def _merge_boundary_edges(edges, tolerance: float = 0.0001):
        """
        Stitches a list of boundary Edge objects into a Wire (or a Cluster of
        Wires if they form disjoint chains).

        Prefers Wire._order_edges/Wire.ByEdges over
        Topology._merge_edges_into_wires when the edges form a single simple
        chain: Wire.ByEdges keeps the wrapper's .edges list in true walk
        order (start of edge i == end of edge i-1), which the (deliberately
        untouched, out of scope) Wire.IsClosed / Wire.Close implementations
        rely on -- they only compare edges[0].start to edges[-1].end rather
        than checking real OCCT connectivity, so an out-of-order .edges list
        (as produced by TopExp_Explorer traversal order inside
        Wire.ByOcctShape) makes an otherwise perfectly closed wire look open
        to that naive check. Falls back to Topology._merge_edges_into_wires
        (OCCT BRepBuilderAPI_MakeWire-based, order-independent) whenever the
        edges do not form one simple chain, e.g. disjoint boundary loops.
        """
        from .wire import Wire

        edges = [e for e in edges if isinstance(e, Edge)]
        if not edges:
            return None
        ordered = Wire._order_edges(edges, tolerance=tolerance)
        if ordered is not None:
            wire = Wire.ByEdges(ordered, tolerance=tolerance)
            if wire is not None:
                return wire
        return Topology._merge_edges_into_wires(edges, tolerance=tolerance)

    @staticmethod
    def ExternalBoundary(shell, tolerance: float = 0.0001, silent: bool = False):
        """
        Returns the external (free/boundary) Wire of an open Shell: the wire
        stitched from all edges that belong to exactly one face of the shell.

        If the boundary edges stitch into more than one disjoint wire, the
        longest one is returned (matching the tie-break used by the
        algorithm-layer Shell.ExternalBoundary in src/topologicpy/Shell.py).
        """
        if not isinstance(shell, Shell):
            if not silent:
                print("Shell.ExternalBoundary - Error: The input shell parameter is not a valid Shell. Returning None.")
            return None
        faces = getattr(shell, "faces", []) or []
        boundary_edges = Shell._boundary_edges(faces, tolerance=tolerance, min_count=1, max_count=1)
        if not boundary_edges:
            if not silent:
                print("Shell.ExternalBoundary - Error: External boundary could not be found. Returning None.")
            return None
        merged = Shell._merge_boundary_edges(boundary_edges, tolerance=tolerance)
        if merged is None:
            if not silent:
                print("Shell.ExternalBoundary - Error: External boundary could not be found. Returning None.")
            return None
        if Topology.IsInstance(merged, "Wire"):
            return merged
        # Disjoint boundary chains merged into a Cluster of Wires: keep the longest.
        wires = [w for w in getattr(merged, "topologies", []) or [] if Topology.IsInstance(w, "Wire")]
        if not wires:
            if not silent:
                print("Shell.ExternalBoundary - Error: External boundary could not be found. Returning None.")
            return None

        def _wire_length(wire):
            total = 0.0
            for edge in getattr(wire, "edges", []) or []:
                if isinstance(edge, Edge) and isinstance(edge.start, Vertex) and isinstance(edge.end, Vertex):
                    dx = edge.end.x - edge.start.x
                    dy = edge.end.y - edge.start.y
                    dz = edge.end.z - edge.start.z
                    total += (dx * dx + dy * dy + dz * dz) ** 0.5
            return total

        wires.sort(key=_wire_length)
        return wires[-1]

    def Slice(self, otherTopology, transferDictionary: bool = False):
        """
        Slices this (open) Shell's faces using otherTopology (typically a
        Cluster of cutting Faces) as a cutting tool, keeping this shell's own
        material. Unlike the generic Topology._partition_by (which wraps the
        raw BOPAlgo_CellsBuilder compound result as a Cluster mixing Shells
        and stray Faces), this reassembles the resulting sub-faces of self's
        own shape into a single Shell whenever they are all that remains.

        This is what Cell.Prism (src/topologicpy/Cell.py) needs: it calls
        Topology.Slice(topologyA=shell, topologyB=sliceCluster) and then
        requires the result to satisfy Topology.IsInstance(result, "Shell")
        before handing it to Cell.ByShell.
        """
        from .topology import (
            _collect_boolean_operand_shapes,
            _postprocess_boolean_result,
            _merge_backend_dictionaries,
            _is_null_shape,
            _iter_occ_subshapes,
        )
        try:
            from OCC.Core.TopTools import TopTools_ListOfShape
            from OCC.Core.BOPAlgo import BOPAlgo_CellsBuilder
            from OCC.Core.TopAbs import TopAbs_FACE
        except Exception:
            return None
        if BOPAlgo_CellsBuilder is None:
            return None

        shapes_a = _collect_boolean_operand_shapes(self)
        shapes_b = _collect_boolean_operand_shapes(otherTopology)
        if not shapes_a or not shapes_b:
            return None

        try:
            builder = BOPAlgo_CellsBuilder()
            for shape in shapes_a:
                builder.AddArgument(shape)
            for shape in shapes_b:
                builder.AddArgument(shape)
            builder.Perform()
            if hasattr(builder, "HasErrors") and builder.HasErrors():
                return None

            empty_avoid = TopTools_ListOfShape()
            for shape in shapes_a:
                to_take = TopTools_ListOfShape()
                to_take.Append(shape)
                builder.AddToResult(to_take, empty_avoid)

            builder.MakeContainers()
            result_shape = builder.Shape()
        except Exception:
            return None

        if _is_null_shape(result_shape):
            return None
        result_shape = _postprocess_boolean_result(result_shape)

        result_dictionary = {}
        if transferDictionary:
            result_dictionary = _merge_backend_dictionaries(
                Topology.GetDictionary(self), Topology.GetDictionary(otherTopology)
            )

        result_faces = []
        for occ_face in _iter_occ_subshapes(result_shape, TopAbs_FACE):
            f = Face.ByOcctShape(occ_face)
            if f is not None:
                result_faces.append(f)

        if result_faces:
            new_shell = Shell.ByFaces(result_faces, silent=True)
            if new_shell is not None:
                new_shell.dictionary = result_dictionary
                return new_shell

        # Fall back to the generic wrap (e.g. a genuinely disjoint result).
        return Topology.ByOcctShape(result_shape, dictionary=result_dictionary)

    def Divide(self, otherTopology, transferDictionary: bool = False):
        return self.Slice(otherTopology, transferDictionary=transferDictionary)

    def Impose(self, otherTopology, transferDictionary: bool = False):
        return self.Slice(otherTopology, transferDictionary=transferDictionary)

    def Imprint(self, otherTopology, transferDictionary: bool = False):
        return self.Slice(otherTopology, transferDictionary=transferDictionary)


class ShellUtility:
    @staticmethod
    def Area(shell):
        if not isinstance(shell, Shell):
            return None
        return sum(FaceUtility.Area(f) or 0.0 for f in shell.faces)

    @staticmethod
    def ExternalBoundary(shell, tolerance: float = 0.0001):
        return Shell.ExternalBoundary(shell, tolerance=tolerance, silent=True)

    @staticmethod
    def InternalBoundaries(shell, tolerance: float = 0.0001):
        """
        Returns the internal (non-manifold, shared-by-2-faces) boundary wires
        of the shell -- i.e. every wire made of edges that are NOT part of the
        shell's single external boundary. For a simple open shell each such
        internal edge is shared by exactly two faces.
        """
        if not isinstance(shell, Shell):
            return []
        faces = getattr(shell, "faces", []) or []
        internal_edges = Shell._boundary_edges(faces, tolerance=tolerance, min_count=2, max_count=None)
        if not internal_edges:
            return []
        merged = Shell._merge_boundary_edges(internal_edges, tolerance=tolerance)
        if merged is None:
            return []
        if Topology.IsInstance(merged, "Wire"):
            return [merged]
        return [w for w in getattr(merged, "topologies", []) or [] if Topology.IsInstance(w, "Wire")]


def _shell_by_wires(wires, triangulate: bool = True, tolerance: float = 0.0001, silent: bool = False):
    """
    Builds a Shell by lofting through a list of profile Wires: consecutive
    wires are connected pairwise by side faces (one face per pair of
    corresponding edges, optionally triangulated into two triangles).

    This is the same "loft between consecutive wires" contract used by the
    algorithm-layer Shell.ByWires (src/topologicpy/Shell.py), which builds
    its own side faces directly out of Edge/Wire/Face primitives and only
    calls into the backend via Shell.ByFaces -- so this backend-level
    ByWires is a smaller, self-contained implementation of the same idea for
    callers that go through Core.Shell.ByWires directly.
    """
    from .wire import Wire

    if not isinstance(wires, list):
        if not silent:
            print("Shell.ByWires - Error: The input wires parameter is not a valid list. Returning None.")
        return None
    wire_list = [w for w in wires if isinstance(w, Wire)]
    if len(wire_list) < 2:
        if not silent:
            print("Shell.ByWires - Error: At least two valid wires are required. Returning None.")
        return None

    faces = []
    for wire_a, wire_b in zip(wire_list[:-1], wire_list[1:]):
        edges_a = wire_a.Edges()
        edges_b = wire_b.Edges()
        if len(edges_a) != len(edges_b):
            if not silent:
                print("Shell.ByWires - Warning: Corresponding wires do not have the same number of edges. Skipping this pair.")
            continue
        for edge_a, edge_b in zip(edges_a, edges_b):
            quad_vertices = [edge_a.start, edge_a.end, edge_b.end, edge_b.start]
            if triangulate:
                tri1 = Face.ByVertices([edge_a.start, edge_a.end, edge_b.end])
                tri2 = Face.ByVertices([edge_a.start, edge_b.end, edge_b.start])
                if tri1 is not None:
                    faces.append(tri1)
                if tri2 is not None:
                    faces.append(tri2)
            else:
                quad = Face.ByVertices(quad_vertices)
                if quad is not None:
                    faces.append(quad)

    if not faces:
        if not silent:
            print("Shell.ByWires - Error: Could not create any side faces. Returning None.")
        return None
    return Shell.ByFaces(faces, tolerance=tolerance, silent=silent)


Shell.ByWires = staticmethod(_shell_by_wires)

# ---------------------------------------------------------------------------
# Explicit unsupported Shell API
# ---------------------------------------------------------------------------
from .helpers import not_implemented as _not_implemented


def _shell_not_implemented(name, return_value=None):
    def _method(*args, **kwargs):
        return _not_implemented(f"Shell.{name}", return_value)
    return _method


def _shell_utility_not_implemented(name, return_value=None):
    def _method(*args, **kwargs):
        return _not_implemented(f"ShellUtility.{name}", return_value)
    return _method

# Shell.ExternalBoundary, Shell.Slice/Divide/Impose/Imprint, ShellUtility.ExternalBoundary,
# and ShellUtility.InternalBoundaries are implemented above -- do not clobber them here.
