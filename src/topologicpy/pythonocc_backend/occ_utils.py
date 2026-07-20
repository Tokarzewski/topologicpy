from __future__ import annotations

try:
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.BRepBuilderAPI import (
        BRepBuilderAPI_MakeVertex,
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeWire,
        BRepBuilderAPI_MakeFace,
    )
except Exception:  # pragma: no cover
    gp_Pnt = None
    BRepBuilderAPI_MakeVertex = None
    BRepBuilderAPI_MakeEdge = None
    BRepBuilderAPI_MakeWire = None
    BRepBuilderAPI_MakeFace = None


def make_occ_vertex(x: float, y: float, z: float):
    if gp_Pnt is None or BRepBuilderAPI_MakeVertex is None:
        return None
    try:
        return BRepBuilderAPI_MakeVertex(gp_Pnt(float(x), float(y), float(z))).Vertex()
    except Exception:
        return None


def make_occ_edge(start, end):
    if gp_Pnt is None or BRepBuilderAPI_MakeEdge is None:
        return None
    try:
        return BRepBuilderAPI_MakeEdge(gp_Pnt(start.x, start.y, start.z), gp_Pnt(end.x, end.y, end.z)).Edge()
    except Exception:
        return None


def make_occ_wire(edges: list):
    if BRepBuilderAPI_MakeWire is None:
        return None
    try:
        maker = BRepBuilderAPI_MakeWire()
        for edge in edges:
            if getattr(edge, "shape", None) is not None:
                maker.Add(edge.shape)
        if maker.IsDone():
            return maker.Wire()
    except Exception:
        pass
    return None


def make_occ_face(wire):
    if BRepBuilderAPI_MakeFace is None:
        return None
    try:
        if getattr(wire, "shape", None) is not None:
            maker = BRepBuilderAPI_MakeFace(wire.shape)
            if maker.IsDone():
                return maker.Face()
    except Exception:
        pass
    return None


def make_occ_shell(faces: list):
    """
    Builds a Shell from independently-constructed Faces.

    Faces built via make_occ_face() are each made from their own fresh,
    coordinate-only geometry (see make_occ_edge's docstring-equivalent note
    below) -- two adjacent faces do NOT share the same underlying
    TopoDS_Vertex/Edge at their common boundary even when geometrically
    coincident. A BRep_Builder.Add()-only shell is therefore topologically
    "leaky": BRepCheck_Analyzer reports it invalid, and downstream boolean
    operations (BOPAlgo_CellsBuilder etc.) silently fail to split it
    correctly (verified empirically: an "leaky" box built this way did not
    split when cut by a plane, while a clean BRepPrimAPI_MakeBox did).
    BRepBuilderAPI_Sewing fuses coincident vertices/edges across face
    boundaries within tolerance, producing a real watertight shell -- use it
    instead of a bare BRep_Builder shell.
    """
    if not faces:
        return None
    try:
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Shell, topods
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing
        from OCC.Core.BRepCheck import BRepCheck_Analyzer
    except Exception:
        return None

    occ_faces = []
    for face in faces:
        occ_face = getattr(face, "shape", None)
        if occ_face is None:
            continue
        try:
            occ_faces.append(topods.Face(occ_face))
        except Exception:
            continue

    if not occ_faces:
        return None

    try:
        sewer = BRepBuilderAPI_Sewing(0.0001)
        for occ_face in occ_faces:
            sewer.Add(occ_face)
        sewer.Perform()
        sewn = sewer.SewedShape()
    except Exception:
        sewn = None

    if sewn is not None and not sewn.IsNull():
        try:
            if sewn.ShapeType() == 3:  # TopAbs_SHELL
                return topods.Shell(sewn)
        except Exception:
            pass
        try:
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopAbs import TopAbs_SHELL
            explorer = TopExp_Explorer(sewn, TopAbs_SHELL)
            if explorer.More():
                return topods.Shell(explorer.Current())
        except Exception:
            pass

    # Fallback: bare unsewn shell (may be topologically leaky, but still
    # geometrically usable for traversal/visualization purposes).
    builder = BRep_Builder()
    occ_shell = TopoDS_Shell()
    builder.MakeShell(occ_shell)
    added = 0
    for occ_face in occ_faces:
        try:
            builder.Add(occ_shell, occ_face)
            added += 1
        except Exception:
            continue
    if added == 0:
        return None
    return occ_shell


def make_occ_cell(shell):
    if shell is None:
        return None
    try:
        from OCC.Core.TopoDS import TopoDS_Shell, topods
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
        from OCC.Core.BRepCheck import BRepCheck_Analyzer
        from OCC.Core.BRepLib import breplib
        from OCC.Core.BOPAlgo import BOPAlgo_MakerVolume
        from OCC.Core.TopTools import TopTools_ListOfShape
    except Exception:
        BOPAlgo_MakerVolume = None

    occ_shell = getattr(shell, "shape", None)
    if occ_shell is None:
        faces = getattr(shell, "faces", None)
        occ_shell = make_occ_shell(faces) if faces else None
    if occ_shell is None:
        return None

    try:
        occ_shell = topods.Shell(occ_shell)
    except Exception:
        try:
            tmp_shell = TopoDS_Shell()
            tmp_shell = occ_shell
            occ_shell = tmp_shell
        except Exception:
            return None

    def _solid_from(solid):
        try:
            breplib.OrientClosedSolid(solid)
        except Exception:
            pass
        # BOPAlgo_MakerVolume / MakeSolid can yield an inside-out solid
        # (negative volume). Flip the orientation if needed so the
        # backend Cell reports a positive volume.
        try:
            from OCC.Core.TopAbs import TopAbs_REVERSED
            from OCC.Core.GProp import GProp_GProps
            from OCC.Core.BRepGProp import brepgprop
            props = GProp_GProps()
            brepgprop.VolumeProperties(solid, props)
            if props.Mass() < 0.0:
                solid.Orientation(TopAbs_REVERSED)
                breplib.OrientClosedSolid(solid)
        except Exception:
            pass
        try:
            analyzer = BRepCheck_Analyzer(solid)
            if not analyzer.IsValid():
                return solid
        except Exception:
            pass
        return solid

    try:
        solid_maker = BRepBuilderAPI_MakeSolid(occ_shell)
        if solid_maker.IsDone():
            occ_solid = solid_maker.Solid()
            return _solid_from(occ_solid)
    except Exception:
        pass

    # Fallback: BOPAlgo_MakerVolume builds a solid from a (possibly
    # non-closed) shell by thickening — robust for polyhedra like the
    # dodecahedron whose pentagonal faces don't sew perfectly closed.
    if BOPAlgo_MakerVolume is not None:
        try:
            args = TopTools_ListOfShape()
            args.Append(occ_shell)
            maker = BOPAlgo_MakerVolume()
            maker.SetArgs(args)
            maker.SetRunParallel(False)
            maker.Perform()
            if not maker.IsDone():
                return None
            occ_solid = maker.GetResult()
            if occ_solid is None or (hasattr(occ_solid, "IsNull") and occ_solid.IsNull()):
                return None
            return _solid_from(occ_solid)
        except Exception:
            return None
    return None
