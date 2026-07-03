# Handoff: PythonOCC backend implementation

## Goal
Make `Core.SetBackend(PythonOCCBackend)` (in `src/topologicpy/pythonocc_backend/`) a full
drop-in replacement for `topologic_core`, such that the **entire pytest suite in `tests/`
passes** with this backend active. See `TopologicPy_Replacement_Backend_Developer_Guide.md`
for the original spec (treat it as guidance, not ground truth — several of its claims about
exact call signatures turned out to be wrong; the real `src/topologicpy/*.py` call sites are
authoritative). `PYTHONOCC_BACKEND_GOAL.md` is an earlier, now-stale status doc from a prior
pass — this file supersedes it.

## Why this backend exists
This machine's Windows Application Control / Smart App Control security policy **blocks the
real `topologic_core` DLL from loading at all** (`Code Integrity determined that a process
attempted to load ...TKTopAlgo...dll that did not meet Enterprise signing level
requirements`). Do not try to import or fall back to `topologic_core` — it is unusable here.
`pythonocc-core` (from conda-forge) is not blocked and is what this backend is built on.

## Environment
A dedicated conda env already exists and is set up correctly:
```
/c/Users/model/miniconda3/envs/topologicpy-occ/python.exe
```
It has `topologicpy` installed editable (`pip install -e .`), plus `pythonocc-core` (conda-forge),
`pytest`, `pytest-xdist`, and a **PyPI** (not conda-forge) build of `numpy` — conda-forge's numpy
build crashes the whole process on any `np.dot` call on this CPU (`Windows fatal exception: code
0xc06d007f`), verified totally unrelated to this backend's code. If numpy ever needs
reinstalling: `pip install --force-reinstall --no-deps numpy==2.1.3` (PyPI wheel, not conda).

To activate the backend, set an env var before Python starts (nothing else needed):
```
TOPOLOGICPY_CORE_BACKEND=pythonocc
```
This is wired into `Core.Backend()` in `src/topologicpy/Core.py` — opt-in only, `topologic_core`
stays the silent default for everyone else.

### Running tests
Always use `-n0` for single-file debugging — xdist workers swallow native tracebacks/crashes:
```bash
TOPOLOGICPY_CORE_BACKEND=pythonocc "/c/Users/model/miniconda3/envs/topologicpy-occ/python.exe" \
  -m pytest tests/test_06Cell.py -q -n0 -W "ignore::DeprecationWarning"
```
For the full suite (parallel, per `pyproject.toml`'s `-nauto` default):
```bash
TOPOLOGICPY_CORE_BACKEND=pythonocc "/c/Users/model/miniconda3/envs/topologicpy-occ/python.exe" \
  -m pytest tests/ -q --no-header
```
Expect **tens of thousands of `DeprecationWarning` lines** (pythonocc-core 7.7.1 deprecating
`topods_Vertex`/`topexp_FirstVertex`/`breptools_OuterWire`/etc. free functions in favor of
`topods.Vertex`/`topexp.FirstVertex`/`breptools.OuterWire` module-proxy style). These are cosmetic
and don't fail anything, but they're a real productivity drain when debugging — consider a
pass to switch the deprecated free-function imports to the module-proxy form throughout
`pythonocc_backend/*.py` (mechanical, low-risk, not yet done).

All 15 test files (`test_01Vertex.py` .. `test_15Speckle.py`) had a hard, unconditional
`import topologic_core as topologic` at module scope, which fails to even *collect* on this
machine regardless of backend. This has already been made defensive (`try/except → None`) in
every file — do not revert that. Two genuine hardcoded `isinstance(x, topologic.Cluster)` calls
in `test_13Graph.py` were also rewritten to use `Topology.IsInstance(x, "Cluster")` — this is a
legitimate fix (matches the pattern already used everywhere else in the suite), not a workaround.

## Status as of this handoff

**Confirmed passing** (as of the last full clean run, `/tmp/full_run5.txt`):
test_01Vertex, test_02Edge, test_10Dictionary, test_11Grid, test_12Matrix, test_13Graph,
test_14Vector.

**Fixed since that run, not yet re-verified with a full suite run** (interrupted by user
before it could finish — re-run the full suite first thing):
- `test_03Wire.py` — root cause fixed (`Topology._apply_rigid`/`_apply_gtrsf` now recurse into
  aggregate members — e.g. `Cluster.ByTopologies([v1,v2])` with `shape=None` — instead of
  returning `None`). Manually verified this specific file passes stand-alone after the fix.
- Likely also fixes/helps `test_06Cell.py`, `test_07CellComplex.py`, `test_09Topology.py`, and
  possibly others: `Wire.ByOcctShape` (`pythonocc_backend/wire.py`) now walks edges via
  `BRepTools_WireExplorer` (true connectivity order) instead of generic `TopExp_Explorer`
  (arbitrary order). This was the root cause of `Cell.ByThickenedShell` failing — a wire
  rebuilt from a *scrambled* edge list (e.g. `Cluster.ByTopologies([bottomEdge, sideEdge1,
  topEdge, sideEdge2])`) was topologically closed but its `.edges` list wasn't in walk order,
  and `Wire.IsClosed`/`Wire.Close` (algorithm layer, untouched/out of scope) naively check
  `edges[0].start == edges[-1].end` rather than real connectivity. Verified with a standalone
  scrambled-4-edge-square repro that `.edges` now comes back in correct head-to-tail order.
  **This bug pattern likely affects other currently-unexamined failures too** — anywhere a
  Wire gets rebuilt from a non-walk-ordered edge list via `Topology.SelfMerge`/
  `Topology._merge_edges_into_wires`.

**Failing as of `/tmp/full_run5.txt`, root cause not yet investigated (or only partially)**:
- `test_04Face.py` — `AssertionError: Face.ByShell...`. The Face agent (see below) reported
  this bottoms out in `Shell.ExternalBoundary` → `Topology.SuperTopologies(edge, shell,
  "face")` returning 0 for every edge — but that was **before** the `_dispatch_subtopologies`
  rank-based fix (see "Key fixes" below) landed. Re-investigate fresh; may already be fixed.
- `test_05Shell.py` — `AssertionError: Shell.SelfMerge...`. Not yet investigated.
- `test_08Cluster.py` — `AssertionError: Cluster.Simplify...`. Not yet investigated.
- `test_06Cell.py` — was `Cell.ByThickenedShell` → `Shell.ExternalBoundary` returning `None`
  for a single-face shell in the full test context (but the *exact same* construction worked
  fine in isolation — turned out to be the wire-walk-order bug above, likely now fixed, but
  re-verify since the isolation repro used a 4-edge scrambled square, not the exact 1-face
  shell scenario).
- `test_07CellComplex.py` — `AssertionError: CellComplex.Box...` (`CellComplex.Prism` →
  `Topology.Slice` on a `Cell`+cutting-`Face` returning a `Cluster` instead of `CellComplex`
  with 0 cells). This was being actively debugged and mostly fixed (see "Key fixes" below —
  `_partition_by` rewritten to use geometric classification instead of broken
  `Modified()`/`AddToResult(original_shape)` approaches, plus `make_occ_shell` sewing fix so
  `Cell.Prism`'s shape is actually watertight). Last direct test showed `Topology.Slice`
  correctly finding 2 cells but the **overall wrapped result was still typed as `Cluster` not
  `CellComplex`** — needs the `_promote_to_compsolid_if_multi_solid` helper (already written,
  see below) wired into `_partition_by`'s final result before calling `Topology.ByOcctShape`.
  **This is probably the very next thing to fix** — the helper exists, it just isn't called yet
  at the end of `_partition_by`.
- `test_09Topology.py` — `TypeError: 'NoneType' object is not iterable`. Not yet root-caused;
  may be fixed by the wire-walk-order or dispatch-rank fixes below — check first.

**Not yet run/checked at all**: `test_15Speckle.py` (likely trivial/unaffected — no backend
calls observed in earlier grepping, but never actually run against this backend).

## Key architectural fixes landed this session (read before changing `topology.py`)

All in `src/topologicpy/pythonocc_backend/topology.py` unless noted.

1. **Dual calling convention.** TopologicPy calls backend methods two ways: `Core.Topology.X(topology,
   ...)` (explicit namespace call) and `Core.InstanceCall(obj, 'X', ...)` → `getattr(obj,
   'X')(*args)` (instance-bound). A plain instance method (`def X(self, ...)`, no
   `@staticmethod`) supports both; a `@staticmethod def X(topology, ...)` only supports the
   first. The whole `Topology` base class was converted to instance methods for this reason.
   Any new method that might be called via `Core.InstanceCall` must be a plain instance method.

2. **Stub-clobbering bug** — recurring, found and fixed ~6 times already (Aperture, Context,
   Face.ByWires, Cluster.SelfMerge, and others). Every backend file has a block at the bottom
   like `X.Method = staticmethod(_x_not_implemented("Method"))`. If you implement `Method`
   properly earlier in the file, you **must** delete/replace that bottom assignment or it
   silently overwrites your real implementation with the stub. Check every time.

3. **`Topology.GetDictionary`/`Topology.Dictionary` must never return `None`** — always `{}`
   for "no dictionary set". `topologicpy.Dictionary.Keys()` treats bare `None` as an
   invalid-dictionary *error* but `{}` as valid-empty. This silently broke the
   dictionary-transfer path of `Topology.Rotate`/`Translate` until fixed.

4. **Dedup must use OCCT shape identity, not `_uuid`.** Two wrapper objects independently
   extracted from the *same* underlying OCCT sub-shape (e.g. the shared vertex between two
   adjacent edges in a wire) get different Python `_uuid`s but represent the same point.
   `_deduplicate_by_identity` (topology.py) and `unique_by_uuid` (helpers.py) both now prefer
   `hash(shape)` (Python builtin — **`TopoDS_Shape.HashCode(...)` does not exist in this
   pythonocc-core build**, only `__hash__`/`IsSame`/`IsEqual`) over `_uuid`.

5. **Dimension-direction-aware `Vertices`/`Edges`/`Wires`/`Faces`/`Shells`/`Cells`/
   `CellComplexes`.** These generic dispatch methods (`Topology._dispatch_subtopologies`) only
   correctly returned "my own substructure" (correct when the target type's dimension ≤ self's
   own dimension, e.g. a Face asking for its own Edges). When self is *lower*-dimensional than
   the requested type **and a hostTopology is given** (e.g. `vertex.Edges(hostTopology, out)`),
   real topologic_core semantics flip to an adjacency/super-topology query: "find every Edge
   within hostTopology incident to this Vertex". Fixed by adding a `_TYPE_RANK` dict
   (Vertex=0..CellComplex=6) and routing to `Topology.SuperTopologies(self, hostTopology,
   targetTypeName)` when `self_rank < target_rank and hostTopology is not None`. This was
   silently breaking `Vertex.Degree`, `Wire.StartVertex`/`StartEndVertices`, and anything else
   built on host-scoped adjacency — found by the Graph sub-agent, fixed centrally. **If you find
   another "always returns empty/0" bug on a low-dimensional object asking a host-scoped
   question, suspect this pattern first.**

6. **Non-manifold `CellComplex` construction: use `BOPAlgo_MakerVolume`, not
   `BOPAlgo_CellsBuilder`, for Face/Shell soup → Solids.** `BOPAlgo_CellsBuilder` partitions
   *same-dimensional* shapes — fed pure 2D `Face`s, it builds 2D face-cells, not 3D solids
   (verified: 12 faces of two adjacent boxes → 0 solids found). `BOPAlgo_MakerVolume` is OCCT's
   dedicated tool for building volumetric cells from a Face/Shell/Solid boundary soup,
   including shared internal faces between adjacent volumes (verified: same 12 faces → 2
   solids correctly). This is now used in `cell_complex.py`'s `CellComplex._build_from_shapes`.

7. **`BOPAlgo_CellsBuilder`/`BOPAlgo_MakerVolume`'s `MakeContainers()` yields a plain
   `COMPOUND`, not a `COMPSOLID`, even when the resulting Solids genuinely share faces**
   (verified empirically in this OCCT build). Since `Topology.ByOcctShape` dispatches
   `COMPSOLID` → `CellComplex` but `COMPOUND` → `Cluster`, any boolean/merge/partition result
   with ≥2 Solid sub-shapes needs to be explicitly rebuilt as a `TopoDS_CompSolid` (via
   `BRep_Builder.MakeCompSolid` + `.Add()` per solid) before wrapping, or it silently becomes a
   `Cluster` instead of a `CellComplex`. A shared helper for this,
   `_promote_to_compsolid_if_multi_solid(shape)`, already exists in `topology.py` and is wired
   into `cell_complex.py`'s builder — **but is NOT yet called at the end of `_partition_by`**
   (used by `Divide`/`Slice`/`Impose`/`Imprint`), which is why `CellComplex.Box`/`Prism` (which
   goes through `Topology.Slice`) still returns a `Cluster`. Wire it in — that's the very next
   fix.

8. **`_partition_by` (Divide/Slice/Impose/Imprint) — do not use `AddToResult(to_take=[original_
   shape], ...)`, and do not trust `Modified()`/`IsDeleted()` history for Solid-level splits.**
   Both are traps discovered empirically: `AddToResult` with the *original* unsplit shape just
   re-selects it whole, not the pieces it was cut into; and `BOPAlgo_CellsBuilder`'s own
   `Modified(solid)`/`IsDeleted(solid)` history reports the solid as unmodified/not-deleted even
   when `AddAllToResult()` correctly produces multiple split pieces from it. The working
   approach (already implemented): `AddAllToResult()` to get every fragment from both operands,
   then geometrically classify each fragment's centre of mass (`GProp_GProps` +
   `BRepClass3d_SolidClassifier` against self's *original* shapes) to keep only fragments that
   came from self's material, dropping fragments that came purely from the other operand's
   exclusive volume.

9. **`make_occ_shell` (occ_utils.py) now sews faces via `BRepBuilderAPI_Sewing` instead of a
   bare `BRep_Builder`.** Faces built independently (e.g. via `Face.ByVertices`) never share
   the same underlying `TopoDS_Vertex`/`TopoDS_Edge` at their common boundary even when
   geometrically coincident (each face's edges are built from raw coordinates via
   `make_occ_edge`). A bare-`BRep_Builder` shell from such faces is topologically invalid
   (`BRepCheck_Analyzer.IsValid() == False`) and silently breaks downstream boolean operations
   (verified: `Cell.Prism`'s box, built this way, did not split when cut by a plane via
   `BOPAlgo_CellsBuilder`, while a clean `BRepPrimAPI_MakeBox` did). Sewing fixes this — `Cell.
   Prism`'s shape is now genuinely valid. **If you see another "boolean op silently does
   nothing" bug, check `BRepCheck_Analyzer(shape).IsValid()` on the operands first** — it's
   probably this.

10. **`Wire.ByOcctShape` walks edges via `BRepTools_WireExplorer`** (connectivity/walk order),
    not generic `TopExp_Explorer` (arbitrary order) — see status section above, fix #? just
    landed. Falls back to the old `TopExp_Explorer` approach if the wire explorer throws.

11. **pythonocc-core API surface gotchas in this exact install** (7.7.1, verified — don't trust
    generic OCCT docs or assume a "class static method" form exists):
    - `TopoDS_Shape.HashCode(...)` — does not exist. Use Python's builtin `hash(shape)`.
    - `OCC.Core.TopExp.TopExp` (the class) is not exposed. Use free functions
      `topexp_FirstVertex`/`topexp_LastVertex` (deprecated but working) or the module proxy
      `topexp.FirstVertex`/`topexp.LastVertex` (preferred, not deprecated).
    - `OCC.Core.BRepTools.BRepTools.OuterWire(face)` similarly not exposed as a class
      staticmethod — use `breptools_OuterWire` (deprecated) or `breptools.OuterWire` (module
      proxy). This deprecated-free-function-vs-module-proxy pattern is broad across this
      pythonocc-core version — if a class-style call raises `AttributeError`, check
      `dir(OCC.Core.<Module>)` for a `snake_case` free function or lowercase module proxy
      before assuming the operation is unsupported.
    - `TopTools_ListOfShape` is **not** directly Python-iterable — use
      `TopTools_ListIteratorOfListOfShape(the_list)` (`.More()`/`.Value()`/`.Next()`), or the
      `_toptools_list_to_pylist()` helper already in `topology.py`.
    - `BRepBuilderAPI_MakeWire.Add(edge)` **does** correctly auto-connect + share vertices
      across edges added in any (scrambled) order — verified with a scrambled 4-edge rectangle.
      `maker.IsDone()` right after each `.Add()` reliably reflects whether that specific edge
      connected, and recovers to `True` once a later edge does connect. Use this for stitching
      edges into a wire (see `Topology._merge_edges_into_wires`); don't hand-roll vertex fusion.

## Parallel sub-agent work landed this session (already merged into the working tree)

Four agents ran in parallel on disjoint files, all reported back complete:
- **Vertex/Edge/Wire** (`vertex.py`, `edge.py`, `wire.py`): fixed `test_01Vertex.py`,
  `test_02Edge.py`. Implemented `Edge.Intersect` (with an analytic segment/segment crossing-
  point test, since `BRepAlgoAPI_Common` only finds coincident-region overlaps, not
  transversal crossings), plus several best-effort/zero-coverage stubs
  (`Vertex.Project`/`Fuse`, `VertexUtility.NearestVertex`/`ParameterAtVertex`,
  `Wire.ByEdgesCluster`/`ByWires`/`Reverse`, `WireUtility.Length`/`Cycles`/`Split`).
- **Face** (`face.py`): fixed the `Face.AddInternalBoundaries` case in `test_04Face.py`.
  Implemented `Face.ByExternalInternalBoundaries`, `FaceUtility.VertexAtParameters`/
  `ParametersAtVertex`/`IsInside`/`Triangulate`/`InternalVertex`. Flagged (not fixed, out of
  scope for that agent): a `Topology.SpatialRelationship`/`Intersect`/`Difference`
  misclassification issue in `topology.py`, and the `Shell.ExternalBoundary` `SuperTopologies`
  issue that the dispatch-rank fix (#5 above) may have since resolved.
- **Shell/Cell** (`shell.py`, `cell.py`): implemented real `Shell.ExternalBoundary` (boundary-
  edge stitching via face-incidence counting), `ShellUtility.InternalBoundaries`,
  `Shell.ByWires`/`Slice`/`Divide`/`Impose`/`Imprint`, plus a `_walk_ordered` workaround for the
  same wire-order issue #10 fixes more generally (this was written *before* the general
  `Wire.ByOcctShape` fix landed — may now be partially redundant, not a correctness issue
  either way). Also patches per-instance `edge.Faces` methods to support
  `Topology.SuperTopologies(edge, shell, "face")` — **check whether this monkeypatching is
  still needed after fix #5, or now-redundant** (leaving it shouldn't cause harm, just
  possibly-dead code). Did not get to `CellUtility.Volume`/`Contains`/`InternalVertex`,
  `Cell.ByBox` — check if still stubbed and needed.
- **Graph** (`graph.py`): fixed `test_13Graph.py` fully. Implemented `AddVertices`,
  `RemoveVertices`, `RemoveEdges`, `Connect`, `ContainsVertex`/`ContainsEdge`,
  `DegreeSequence`, `Density`, `IsolatedVertices`, `AllPaths`, `Topology()`, `Path()`,
  `IsComplete`, `IsErdoesGallai`, `MaximumDelta`, `MinimumDelta`, `GetGUID`. This agent is the
  one who found the dispatch-rank bug (#5 above) but couldn't fix it (out of scope) — I fixed
  it centrally afterward and confirmed `test_13Graph.py` passes.

## Recommended next steps, in order

1. Wire `_promote_to_compsolid_if_multi_solid` into the end of `_partition_by` in
   `topology.py` (right before the final `Topology.ByOcctShape(result_shape, ...)` call) —
   same pattern already used in `cell_complex.py`'s `_build_from_shapes`. Should fix
   `test_07CellComplex.py`.
2. Re-run the full suite (`tests/` with `-n0` per-file if anything crashes/hangs under xdist)
   and get fresh numbers — several fixes landed since the last full run and weren't
   re-verified together.
3. Investigate remaining failures one file at a time, in the style used throughout this
   session: reproduce standalone outside pytest first (minimal repro), trace to the exact
   backend call, fix, re-verify that file, then re-run the full suite before moving on.
4. Once all 15 files pass: consider the deprecation-warning cleanup (switch deprecated free
   functions to module-proxy form throughout `pythonocc_backend/*.py` — purely cosmetic,
   `-W "ignore::DeprecationWarning"` works fine as a stopgap for now).
5. `PYTHONOCC_BACKEND_GOAL.md`'s Appendix-A-style checklist (wiring the backend into `Core.py`
   as more than an opt-in env var, running the full guide's acceptance checklist) — the opt-in
   env var mechanism (`TOPOLOGICPY_CORE_BACKEND=pythonocc`) already satisfies the "don't make
   it the silent default" requirement from that doc; no further `Core.py` change is needed
   unless the user asks for a different selection mechanism.

## Do not

- Do not modify `PythonOCCBackend.py` (a separate, abandoned single-file attempt) — only
  `src/topologicpy/pythonocc_backend/`.
- Do not touch Mojo-related repos/backends (separate effort, out of scope).
- Do not move TopologicPy *algorithms* into the backend — the backend is the primitive
  kernel + persistence layer only (per the developer guide, §1).
- Do not commit anything unless explicitly asked.
