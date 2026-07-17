from __future__ import annotations

from dataclasses import dataclass, field
from .topology import Topology
from .cell import Cell
from .cluster import Cluster
from .helpers import unique_by_uuid

try:
    from OCC.Core.BOPAlgo import BOPAlgo_CellsBuilder, BOPAlgo_MakerVolume
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCC.Core.TopAbs import TopAbs_SHELL, TopAbs_FACE, TopAbs_SOLID
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopTools import TopTools_ListOfShape
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_CompSolid, topods
except Exception:  # pragma: no cover - allows import without PythonOCC
    BOPAlgo_CellsBuilder = None
    BOPAlgo_MakerVolume = None
    BRepAlgoAPI_Fuse = None
    TopAbs_SHELL = TopAbs_FACE = TopAbs_SOLID = None
    TopExp_Explorer = None
    TopTools_ListOfShape = None
    BRep_Builder = None
    TopoDS_CompSolid = None
    topods = None


def _iter_subshapes(shape, shape_type):
    if TopExp_Explorer is None or shape_type is None:
        return []
    result = []
    explorer = TopExp_Explorer(shape, shape_type)
    while explorer.More():
        result.append(explorer.Current())
        explorer.Next()
    return result


def _as_compsolid(shape):
    """
    BOPAlgo_CellsBuilder.MakeContainers() may yield a plain COMPOUND
    containing the resulting Solids rather than a COMPSOLID, even when every
    Solid shares faces with its neighbours. topologic_core's CellComplex is
    specifically a COMPSOLID, so rebuild one explicitly from the Solid
    sub-shapes whenever the builder didn't already produce one.
    """
    if shape is None:
        return None
    try:
        from OCC.Core.TopAbs import TopAbs_COMPSOLID
        if shape.ShapeType() == TopAbs_COMPSOLID:
            return shape
    except Exception:
        pass

    solids = _iter_subshapes(shape, TopAbs_SOLID)
    if not solids or BRep_Builder is None:
        return None
    try:
        builder = BRep_Builder()
        compsolid = TopoDS_CompSolid()
        builder.MakeCompSolid(compsolid)
        for solid in solids:
            builder.Add(compsolid, topods.Solid(solid))
        return compsolid
    except Exception:
        return None


def _shape_same(a, b):
    """OCCT shape equality. Two TopoDS_Shape objects are the same
    topology iff IsSame returns True (coincident + same orientation
    class). Used for shared/non-manifold face detection where
    BOPAlgo_MakerVolume emits distinct Python objects for the same
    geometric face in adjacent cells.
    """
    if a is b:
        return True
    try:
        return bool(a.IsSame(b))
    except Exception:
        return False


def _is_null_shape(shape):
    if shape is None:
        return True
    try:
        return bool(shape.IsNull())
    except Exception:
        return True


@dataclass(eq=False)
class CellComplex(Topology):
    cells: list = field(default_factory=list)

    @staticmethod
    def _build_from_shapes(shapes, tolerance=0.0001):
        """
        Genuine non-manifold CellComplex construction: partitions 3D space
        bounded by the input Face/Cell shapes into every resulting Solid,
        sharing Faces between adjacent Solids.

        BOPAlgo_CellsBuilder partitions same-dimensional shapes (fed pure
        Faces, it builds 2D face-cells, not 3D solids) so it is the wrong
        tool here. BOPAlgo_MakerVolume is OCCT's dedicated tool for building
        volumetric cells from a Face/Shell/Solid boundary soup, including
        shared internal faces between adjacent volumes -- verified
        empirically to produce 2 distinct Solids from 12 Faces forming two
        face-adjacent boxes, where BOPAlgo_CellsBuilder produced 0.
        """
        shapes = [s for s in (shapes or []) if not _is_null_shape(s)]
        if not shapes or BOPAlgo_MakerVolume is None:
            return None

        try:
            args = TopTools_ListOfShape()
            for shape in shapes:
                args.Append(shape)
            maker = BOPAlgo_MakerVolume()
            maker.SetArguments(args)
            maker.SetIntersect(True)
            if tolerance:
                try:
                    maker.SetFuzzyValue(float(tolerance))
                except Exception:
                    pass
            maker.Perform()
            if hasattr(maker, "HasErrors") and maker.HasErrors():
                return None
            result_shape = maker.Shape()
        except Exception:
            return None

        if _is_null_shape(result_shape):
            return None

        solid_count = len(_iter_subshapes(result_shape, TopAbs_SOLID))
        if solid_count >= 2:
            compsolid = _as_compsolid(result_shape)
            if compsolid is not None:
                result_shape = compsolid

        result = Topology.ByOcctShape(result_shape)
        if isinstance(result, CellComplex):
            return result
        if isinstance(result, Cell):
            # The faces/cells only bounded a single solid: still a valid
            # (single-cell) CellComplex per topologic_core semantics.
            return CellComplex(shape=result_shape, cells=[result])
        return None

    @staticmethod
    def ByCells(cells, tolerance=0.0001):
        cells = [c for c in (cells or []) if isinstance(c, Cell)]
        shapes = [c.shape for c in cells if not _is_null_shape(getattr(c, "shape", None))]
        if len(shapes) < 1:
            return None
        if len(shapes) == 1:
            return CellComplex(shape=shapes[0], cells=cells)
        result = CellComplex._build_from_shapes(shapes, tolerance)
        if result is None:
            return CellComplex(shape=None, cells=cells)
        return result

    @staticmethod
    def ByFaces(faces, tolerance=0.0001, copyAttributes=False):
        from .face import Face
        faces = [f for f in (faces or []) if isinstance(f, Face)]
        shapes = [f.shape for f in faces if not _is_null_shape(getattr(f, "shape", None))]
        if len(shapes) < 1:
            return None
        result = CellComplex._build_from_shapes(shapes, tolerance)
        if result is not None:
            return result
        # BOPAlgo_MakerVolume found no fallback volume (e.g. it errored on a
        # face soup that a simpler single-cell sewing pass would tolerate).
        # Fall back to the single-cell path, same as ByCells does when its
        # own _build_from_shapes call fails.
        cell = Cell.ByFaces(faces, tolerance=tolerance)
        if cell is None:
            return None
        return CellComplex.ByCells([cell], tolerance)

    def Cells(self, hostTopology=None, cells=None):
        result = list(getattr(self, "cells", []) or [])
        if cells is not None:
            cells.extend(result)
            return 0
        return result

    def Shells(self, hostTopology=None, shells=None):
        result = []
        for cell in self.Cells():
            result.extend(cell.Shells())
        result = unique_by_uuid(result)
        if shells is not None:
            shells.extend(result)
            return 0
        return result

    def Faces(self, hostTopology=None, faces=None):
        result = []
        for cell in self.Cells():
            result.extend(cell.Faces())
        result = unique_by_uuid(result)
        if faces is not None:
            faces.extend(result)
            return 0
        return result

    def Edges(self, hostTopology=None, edges=None):
        result = []
        for cell in self.Cells():
            result.extend(cell.Edges())
        result = unique_by_uuid(result)
        if edges is not None:
            edges.extend(result)
            return 0
        return result

    def Vertices(self, hostTopology=None, vertices=None):
        result = []
        for cell in self.Cells():
            result.extend(cell.Vertices())
        result = unique_by_uuid(result)
        if vertices is not None:
            vertices.extend(result)
            return 0
        return result

    def CellComplexes(self, hostTopology=None, cellComplexes=None):
        result = [self]
        if cellComplexes is not None:
            cellComplexes.extend(result)
            return 0
        return result

    def ExternalBoundary(self):
        """
        Returns the outer Shell bounding the union of all of this
        CellComplex's Cells (i.e. its Cells fused together, with internal
        non-manifold boundaries removed).
        """
        cell_shapes = [c.shape for c in self.Cells() if not _is_null_shape(getattr(c, "shape", None))]
        if not cell_shapes or BRepAlgoAPI_Fuse is None:
            return None

        try:
            fused = cell_shapes[0]
            for shape in cell_shapes[1:]:
                op = BRepAlgoAPI_Fuse(fused, shape)
                op.Build()
                if not op.IsDone():
                    return None
                fused = op.Shape()
        except Exception:
            return None

        if _is_null_shape(fused):
            return None

        try:
            explorer = TopExp_Explorer(fused, TopAbs_SHELL)
            if explorer.More():
                outer_shell_shape = explorer.Current()
                return Topology.ByOcctShape(outer_shell_shape)
        except Exception:
            pass
        return Topology.ByOcctShape(fused)

    def InternalBoundaries(self, faces=None):
        result = self.NonManifoldFaces()
        if faces is not None:
            faces.extend(result)
            return 0
        return result

    def NonManifoldFaces(self, faces=None):
        """
        Returns the Faces shared by two or more of this CellComplex's Cells
        (the non-manifold internal boundaries). Identity is decided by OCCT
        shape equality (TopoDS_Shape.IsSame), NOT Python object/identity
        hashing: BOPAlgo_MakerVolume rebuilds the shared face as a
        distinct TopoDS_Face object inside each Cell, so two copies of the
        same geometric face have different Python identities and hashes yet
        are the same topology. IsSame is the only correct test here.
        """
        per_cell = []
        for cell in self.Cells():
            seen = []
            for face in cell.Faces():
                shape = getattr(face, "shape", None)
                if _is_null_shape(shape):
                    continue
                # de-dupe within a single cell first
                if not any(_shape_same(shape, s) for s, _ in seen):
                    seen.append((shape, face))
            if seen:
                per_cell.append(seen)

        result = []
        used = set()
        for i in range(len(per_cell)):
            for j in range(i + 1, len(per_cell)):
                for s_i, f_i in per_cell[i]:
                    for s_j, f_j in per_cell[j]:
                        if _shape_same(s_i, s_j):
                            key = id(f_i)
                            if key not in used:
                                used.add(key)
                                result.append(f_i)
        if faces is not None:
            faces.extend(result)
            return 0
        return result


# ---------------------------------------------------------------------------
# Explicit unsupported CellComplex API
# ---------------------------------------------------------------------------
from .helpers import not_implemented as _not_implemented


def _cell_complex_not_implemented(name, return_value=None):
    def _method(*args, **kwargs):
        return _not_implemented(f"CellComplex.{name}", return_value)
    return _method


CellComplex.ByCellsCluster = staticmethod(
    lambda cluster, transferDictionaries=False, tolerance=0.0001, silent=False: (
        CellComplex.ByCells(
            (Topology.Cells(cluster) if isinstance(cluster, Cluster) else []),
            tolerance=tolerance,
        )
    )
)
# CellComplex.ExternalBoundary and CellComplex.NonManifoldFaces are implemented above.
