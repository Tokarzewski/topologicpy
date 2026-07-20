"""
Extended smoke test for the experimental PythonOCCBackend.

Place this file in the root of the TopologicPy repository and run:

    python test_pythonocc_backend_extended.py

This is not intended to run the full TopologicPy test suite. It checks that the
new Core backend delegation path works for a small set of basic operations and
then probes a slightly larger layer of TopologicPy wrappers.

Expected status:
    Vertex / Edge / Wire / Face / Dictionary / Graph should work.
    Shell / Cell may work partially depending on how much of the backend has
    been implemented.
    Area and other derived geometric methods may return None or trigger wrapper
    fallback behaviour until the backend utilities are implemented.
"""

from topologicpy.Core import Core
from topologicpy.PythonOCCBackend import PythonOCCBackend

# Switch TopologicPy to the experimental pythonOCC backend.
Core.SetBackend(PythonOCCBackend())

from topologicpy.Vertex import Vertex
from topologicpy.Edge import Edge
from topologicpy.Wire import Wire
from topologicpy.Face import Face
from topologicpy.Shell import Shell
from topologicpy.Cell import Cell
from topologicpy.Graph import Graph
from topologicpy.Topology import Topology
from topologicpy.Dictionary import Dictionary


def section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def check(label, func, expected_type=None):
    """
    Runs a smoke-test expression and prints either the result or the exception.

    This intentionally does not raise on failure because the goal is to locate
    the next missing backend contract method, not to stop at the first issue.
    """
    print(f"\n--- {label} ---")
    try:
        result = func()
        print(result)
        if expected_type is not None:
            print(f"is {expected_type.__name__}:", isinstance(result, expected_type))
        return result
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return None


section("Backend")
print("Backend:", type(Core.Backend()).__name__)
print("Namespaces:", Core.Namespaces())


section("Vertex")
v1 = check("Vertex.ByCoordinates(0, 0, 0)", lambda: Vertex.ByCoordinates(0, 0, 0))
v2 = check("Vertex.ByCoordinates(1, 0, 0)", lambda: Vertex.ByCoordinates(1, 0, 0))
v3 = check("Vertex.ByCoordinates(1, 1, 0)", lambda: Vertex.ByCoordinates(1, 1, 0))
v4 = check("Vertex.ByCoordinates(0, 1, 0)", lambda: Vertex.ByCoordinates(0, 1, 0))

check("Topology.IsInstance(v1, 'Vertex')", lambda: Topology.IsInstance(v1, "Vertex"))
check("Vertex.Coordinates(v1)", lambda: Vertex.Coordinates(v1))
check("Vertex.Coordinates(v2)", lambda: Vertex.Coordinates(v2))


section("Edge")
e1 = check("Edge.ByStartVertexEndVertex(v1, v2)", lambda: Edge.ByStartVertexEndVertex(v1, v2))
e2 = check("Edge.ByStartVertexEndVertex(v2, v3)", lambda: Edge.ByStartVertexEndVertex(v2, v3))
e3 = check("Edge.ByStartVertexEndVertex(v3, v4)", lambda: Edge.ByStartVertexEndVertex(v3, v4))
e4 = check("Edge.ByStartVertexEndVertex(v4, v1)", lambda: Edge.ByStartVertexEndVertex(v4, v1))

check("Topology.IsInstance(e1, 'Edge')", lambda: Topology.IsInstance(e1, "Edge"))
check("Edge.StartVertex(e1)", lambda: Edge.StartVertex(e1))
check("Edge.EndVertex(e1)", lambda: Edge.EndVertex(e1))
check("Edge.Length(e1)", lambda: Edge.Length(e1))


section("Wire")
w = check("Wire.ByEdges([e1, e2, e3, e4])", lambda: Wire.ByEdges([e1, e2, e3, e4]))
check("Topology.IsInstance(w, 'Wire')", lambda: Topology.IsInstance(w, "Wire"))
check("Wire.Edges(w)", lambda: Wire.Edges(w))
check("Topology.Vertices(w)", lambda: Topology.Vertices(w))
check("Wire.IsClosed(w)", lambda: Wire.IsClosed(w))


section("Face")
f = check("Face.ByWire(w)", lambda: Face.ByWire(w))
check("Topology.IsInstance(f, 'Face')", lambda: Topology.IsInstance(f, "Face"))
check("Face.ExternalBoundary(f)", lambda: Face.ExternalBoundary(f))
check("Face.Edges(f)", lambda: Face.Edges(f))
check("Face.Area(f)", lambda: Face.Area(f))


section("Topology extraction")
check("Topology.Vertices(f)", lambda: Topology.Vertices(f))
check("Topology.Edges(f)", lambda: Topology.Edges(f))
check("Topology.Faces(f)", lambda: Topology.Faces(f))
check("Topology.Wires(f)", lambda: Topology.Wires(f))
check("Topology.TypeAsString(f)", lambda: Topology.TypeAsString(f))
check("Topology.TypeAsString(w)", lambda: Topology.TypeAsString(w))
check("Topology.TypeAsString(e1)", lambda: Topology.TypeAsString(e1))
check("Topology.TypeAsString(v1)", lambda: Topology.TypeAsString(v1))


section("Dictionary")
d = check(
    "Dictionary.ByKeysValues(['name', 'value'], ['test edge', 42])",
    lambda: Dictionary.ByKeysValues(["name", "value"], ["test edge", 42]),
)
e1 = check("Topology.SetDictionary(e1, d)", lambda: Topology.SetDictionary(e1, d))
ed = check("Topology.Dictionary(e1)", lambda: Topology.Dictionary(e1))
check("Dictionary.Keys(ed)", lambda: Dictionary.Keys(ed))
check("Dictionary.ValueAtKey(ed, 'name')", lambda: Dictionary.ValueAtKey(ed, "name"))
check("Dictionary.ValueAtKey(ed, 'value')", lambda: Dictionary.ValueAtKey(ed, "value"))


section("Shell")
sh = check("Shell.ByFaces([f])", lambda: Shell.ByFaces([f]))
check("Topology.IsInstance(sh, 'Shell')", lambda: Topology.IsInstance(sh, "Shell"))
check("Topology.Faces(sh)", lambda: Topology.Faces(sh))
check("Topology.Edges(sh)", lambda: Topology.Edges(sh))
check("Topology.Vertices(sh)", lambda: Topology.Vertices(sh))


section("Cell")

v000 = Vertex.ByCoordinates(0, 0, 0)
v100 = Vertex.ByCoordinates(1, 0, 0)
v110 = Vertex.ByCoordinates(1, 1, 0)
v010 = Vertex.ByCoordinates(0, 1, 0)

v001 = Vertex.ByCoordinates(0, 0, 1)
v101 = Vertex.ByCoordinates(1, 0, 1)
v111 = Vertex.ByCoordinates(1, 1, 1)
v011 = Vertex.ByCoordinates(0, 1, 1)

def face_by_vertices(vertices):
    edges = []
    for i in range(len(vertices)):
        edges.append(Edge.ByStartVertexEndVertex(vertices[i], vertices[(i + 1) % len(vertices)]))
    wire = Wire.ByEdges(edges)
    return Face.ByWire(wire)

bottom = face_by_vertices([v000, v100, v110, v010])
top = face_by_vertices([v001, v011, v111, v101])
front = face_by_vertices([v000, v001, v101, v100])
right = face_by_vertices([v100, v101, v111, v110])
back = face_by_vertices([v110, v111, v011, v010])
left = face_by_vertices([v010, v011, v001, v000])

cube_faces = [bottom, top, front, right, back, left]

sh2 = check("Shell.ByFaces(cube_faces)", lambda: Shell.ByFaces(cube_faces))
check("Topology.IsInstance(sh2, 'Shell')", lambda: Topology.IsInstance(sh2, "Shell"))
check("Topology.Faces(sh2)", lambda: Topology.Faces(sh2))

c = check("Cell.ByShell(sh2)", lambda: Cell.ByShell(sh2))
check("Topology.IsInstance(c, 'Cell')", lambda: Topology.IsInstance(c, "Cell"))
check("Topology.Shells(c)", lambda: Topology.Shells(c))
check("Topology.Faces(c)", lambda: Topology.Faces(c))
check("Topology.Edges(c)", lambda: Topology.Edges(c))
check("Topology.Vertices(c)", lambda: Topology.Vertices(c))


section("Graph")
g = check("Graph.ByVerticesEdges([v1, v2, v3, v4], [e1, e2, e3, e4])", lambda: Graph.ByVerticesEdges([v1, v2, v3, v4], [e1, e2, e3, e4]))
check("Topology.IsInstance(g, 'Graph')", lambda: Topology.IsInstance(g, "Graph"))
check("Graph.Vertices(g)", lambda: Graph.Vertices(g))
check("Graph.Edges(g)", lambda: Graph.Edges(g))
check("Graph.AdjacentVertices(g, v1)", lambda: Graph.AdjacentVertices(g, v1))


section("Direct Core instance calls")
check("Core.InstanceCall(v1, 'X')", lambda: Core.InstanceCall(v1, "X"))
check("Core.InstanceCall(v1, 'Y')", lambda: Core.InstanceCall(v1, "Y"))
check("Core.InstanceCall(v1, 'Z')", lambda: Core.InstanceCall(v1, "Z"))
check("Core.InstanceCall(e1, 'StartVertex')", lambda: Core.InstanceCall(e1, "StartVertex"))
check("Core.InstanceCall(e1, 'EndVertex')", lambda: Core.InstanceCall(e1, "EndVertex"))

vertices = []
check("Core.InstanceCall(e1, 'Vertices', None, vertices)", lambda: Core.InstanceCall(e1, "Vertices", None, vertices))
print("vertices after direct call:", vertices)

edges = []
check("Core.InstanceCall(w, 'Edges', None, edges)", lambda: Core.InstanceCall(w, "Edges", None, edges))
print("edges after direct call:", edges)

faces = []
check("Core.InstanceCall(sh, 'Faces', None, faces)", lambda: Core.InstanceCall(sh, "Faces", None, faces))
print("faces after direct call:", faces)


section("Completed")
print("Extended PythonOCCBackend smoke test completed.")
