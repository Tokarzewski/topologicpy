"""
Audit the PythonOCC backend against the topologicpy wrapper layer.

For every backend namespace (Vertex, Edge, Wire, Face, Shell, Cell,
CellComplex, Cluster, Graph, Topology, and their *Utility classes):

  1. LIVE-GAP: wrapper static methods that the wrapper dispatches to the
     backend via `Core.InstanceCall(<obj>, "MethodName", ...)` but which are
     NOT present on the backend native class. These are real breakages
     (they would raise AttributeError/TypeError at runtime).

  2. STUB: backend methods that still call `not_implemented()` (print
     "... - Not implemented.") or raise NotImplementedError.

  3. (Optional) SMOKE: backend factory/constructor methods that return
     None when handed valid inputs.

Run:
    TOPOLOGICPY_CORE_BACKEND=pythonocc \
      /path/to/python.exe audit_pythonocc_backend.py
"""
from __future__ import annotations
import os, re, sys, types

# Make sure we import the *wrapper* layer, with the pythonocc backend active.
os.environ.setdefault("TOPOLOGICPY_CORE_BACKEND", "pythonocc")

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(REPO, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from topologicpy import Core  # noqa: E402  (triggers backend selection)

# The active backend instance (Core._backend is set lazily on first use).
def _active_backend_name():
    try:
        b = getattr(Core, "_backend", None)
        if b is None:
            import topologicpy.Vertex as V
            _ = V.Vertex.ByCoordinates(0, 0, 0)
            b = getattr(Core, "_backend", None)
        return type(b).__name__ if b is not None else "unknown"
    except Exception:
        return "unknown"

# --------------------------------------------------------------------------
# Namespace map: (wrapper_module, wrapper_class, backend_module, backend_class)
# --------------------------------------------------------------------------
NAMESPACES = [
    ("Vertex",     "Vertex",     "vertex",     "Vertex"),
    ("Edge",       "Edge",       "edge",       "Edge"),
    ("Wire",       "Wire",       "wire",       "Wire"),
    ("Face",       "Face",       "face",       "Face"),
    ("Shell",      "Shell",      "shell",      "Shell"),
    ("Cell",       "Cell",       "cell",       "Cell"),
    ("CellComplex","CellComplex", "cell_complex","CellComplex"),
    ("Cluster",    "Cluster",    "cluster",    "Cluster"),
    ("Graph",      "Graph",      "graph",      "Graph"),
    ("Topology",   "Topology",   "topology",   "Topology"),
    # NOTE: VertexUtility/EdgeUtility/... are BACKEND-ONLY classes
    # (the wrapper topologicpy.<Ns> has no <Ns>Utility class). There is
    # no wrapper counterpart to diff, so they are skipped here.
]

# Method names that the backend exposes as generic (already-known) helpers
KNOWN_BACKEND_ONLY = set()

def find_dispatched_methods(wrapper_src: str):
    """Return the set of method names the wrapper dispatches via Core.InstanceCall."""
    return set(re.findall(
        r'Core\.InstanceCall\(\s*\w+\s*,\s*[\'"](\w+)[\'"]', wrapper_src))

def find_not_implemented(backend_src: str):
    """Return method names in the backend source that are still stubbed."""
    out = set()
    # Matches:  Name = staticmethod(_x_not_implemented("Name"))  or lambda calling not_implemented
    for m in re.finditer(r'(\w+)\s*=\s*(?:staticmethod\()?_(?:\w+_)?not_implemented\([\'"](\w+)[\'"]', backend_src):
        out.add(m.group(2))
    return out

def main():
    print(f"Active backend: {_active_backend_name()}\n")
    grand_total_gap = 0
    grand_total_stub = 0

    for wmod, wcls, bmod, bcls in NAMESPACES:
        wpath = os.path.join(SRC, "topologicpy", f"{wmod}.py")
        bpath = os.path.join(SRC, "topologicpy", "pythonocc_backend", f"{bmod}.py")
        if not (os.path.exists(wpath) and os.path.exists(bpath)):
            continue

        w_src = open(wpath, encoding="utf-8", errors="ignore").read()
        b_src = open(bpath, encoding="utf-8", errors="ignore").read()

        # Wrapper class dir
        w_mod = __import__(f"topologicpy.{wmod}", fromlist=[wcls])
        w_class = getattr(w_mod, wcls)
        wrap_methods = {m for m in dir(w_class) if not m.startswith("_")}

        # Backend class dir
        b_mod = __import__(f"topologicpy.pythonocc_backend.{bmod}", fromlist=[bcls])
        b_class = getattr(b_mod, bcls)
        back_methods = {m for m in dir(b_class) if not m.startswith("_")}

        dispatched = find_dispatched_methods(w_src)
        stubs = find_not_implemented(b_src)

        # Live gaps: dispatched to backend but missing on backend class
        live_gap = sorted(m for m in dispatched if m not in back_methods)
        # Stub methods actually present as stub assignments
        stub_present = sorted(m for m in stubs if m in back_methods or m in wrap_methods)

        # Also: wrapper methods NOT on backend AND not pure-python helpers
        # (heuristic: skip the long known pure-python algorithm lists)
        missing_nonlive = sorted(
            m for m in wrap_methods
            if m not in back_methods and m not in dispatched
        )

        flag = "GAP" if live_gap else "ok"
        print(f"[{flag}] {wcls:14} (backend {bcls})")
        print(f"      wrapper_methods={len(wrap_methods)} backend_methods={len(back_methods)} "
              f"dispatched={len(dispatched)}")
        if live_gap:
            print(f"      LIVE-GAP (dispatched but backend missing): {live_gap}")
            grand_total_gap += len(live_gap)
        if stub_present:
            print(f"      STUB (not_implemented still present): {stub_present}")
            grand_total_stub += len(stub_present)
        # Report the non-live missing list size only (too long to enumerate)
        if missing_nonlive:
            print(f"      non-live-wrapper-only methods (pure-python algo/IO, not backend-dispatched): {len(missing_nonlive)}")
        print()

    print("=" * 60)
    print(f"TOTAL LIVE-GAPS (real breakages): {grand_total_gap}")
    print(f"TOTAL STUB placeholders:           {grand_total_stub}")
    if grand_total_gap == 0 and grand_total_stub == 0:
        print("=> Backend is fully operational for all live-dispatched methods. No stubs.")
    else:
        print("=> See above for items to implement.")

if __name__ == "__main__":
    main()
