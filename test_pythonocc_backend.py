"""
Smoke test for the experimental PythonOCCBackend.

Place this file in the root of the TopologicPy repository and run:

    python test_pythonocc_backend.py

This is not intended to run the full TopologicPy test suite. It only checks
that the new Core backend delegation path works for a small set of basic
operations.
"""

from topologicpy.Core import Core
from topologicpy.PythonOCCBackend import PythonOCCBackend

# Switch TopologicPy to the experimental pythonOCC backend.
Core.SetBackend(PythonOCCBackend())

from topologicpy.Vertex import Vertex
from topologicpy.Edge import Edge
from topologicpy.Wire import Wire
from topologicpy.Face import Face
from topologicpy.Graph import Graph
from topologicpy.Topology import Topology
from topologicpy.Dictionary import Dictionary


def section(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


section("Backend")
print("Backend:", type(Core.Backend()).__name__)
print("Namespaces:", Core.Namespaces())


section("Vertex")
v1 = Vertex.ByCoordinates(0, 0, 0)
v2 = Vertex.ByCoordinates(1, 0, 0)
v3 = Vertex.ByCoordinates(1, 1, 0)
v4 = Vertex.ByCoordinates(0, 1, 0)

print("v1:", v1)
print("v1 is Vertex:", Topology.IsInstance(v1, "Vertex"))
print("v1 coordinates:", Vertex.Coordinates(v1))
print("v2 coordinates:", Vertex.Coordinates(v2))


section("Edge")
e1 = Edge.ByStartVertexEndVertex(v1, v2)
e2 = Edge.ByStartVertexEndVertex(v2, v3)
e3 = Edge.ByStartVertexEndVertex(v3, v4)
e4 = Edge.ByStartVertexEndVertex(v4, v1)

print("e1:", e1)
print("e1 is Edge:", Topology.IsInstance(e1, "Edge"))
print("e1 start:", Edge.StartVertex(e1))
print("e1 end:", Edge.EndVertex(e1))
print("e1 length:", Edge.Length(e1))


section("Wire")
w = Wire.ByEdges([e1, e2, e3, e4])
print("wire:", w)
print("wire is Wire:", Topology.IsInstance(w, "Wire"))
print("wire edges:", Wire.Edges(w))
print("wire vertices:", Topology.Vertices(w))


section("Face")
f = Face.ByWire(w)
print("face:", f)
print("face is Face:", Topology.IsInstance(f, "Face"))
print("face external boundary:", Face.ExternalBoundary(f))
print("face edges:", Face.Edges(f))


section("Dictionary")
d = Dictionary.ByKeysValues(["name", "value"], ["test edge", 42])
e1 = Topology.SetDictionary(e1, d)

ed = Topology.Dictionary(e1)
print("edge dictionary:", ed)
print("edge dictionary keys:", Dictionary.Keys(ed))
print("edge name:", Dictionary.ValueAtKey(ed, "name"))
print("edge value:", Dictionary.ValueAtKey(ed, "value"))


section("Graph")
g = Graph.ByVerticesEdges([v1, v2, v3, v4], [e1, e2, e3, e4])
print("graph:", g)
print("graph is Graph:", Topology.IsInstance(g, "Graph"))
print("graph vertices:", Graph.Vertices(g))
print("graph edges:", Graph.Edges(g))
print("adjacent vertices to v1:", Graph.AdjacentVertices(g, v1))


section("Direct Core instance calls")
print("Core.InstanceCall(v1, 'X'):", Core.InstanceCall(v1, "X"))
print("Core.InstanceCall(v1, 'Y'):", Core.InstanceCall(v1, "Y"))
print("Core.InstanceCall(v1, 'Z'):", Core.InstanceCall(v1, "Z"))
print("Core.InstanceCall(e1, 'StartVertex'):", Core.InstanceCall(e1, "StartVertex"))
print("Core.InstanceCall(e1, 'EndVertex'):", Core.InstanceCall(e1, "EndVertex"))

vertices = []
Core.InstanceCall(e1, "Vertices", None, vertices)
print("Core.InstanceCall(e1, 'Vertices', None, vertices):", vertices)


section("Completed")
print("PythonOCCBackend smoke test completed.")
