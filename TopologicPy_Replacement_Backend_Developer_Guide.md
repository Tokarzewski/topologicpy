**TopologicPy Replacement Backend Developer Guide**

*Implementing a backend that can replace topologic\_core behind Core.py*

Prepared for the TopologicPy Core facade migration

Date: 2026-05-08

# Contents

* 1. Purpose and intended architecture
* 2. The backend contract in one page
* 3. Required namespaces and object model
* 4. Type IDs and type checks
* 5. Method catalogue by namespace
* 6. Instance-call conventions and list-populating methods
* 7. Dictionaries and attributes
* 8. Topology and geometry behaviour
* 9. Graph behaviour
* 10. Serialization and persistence
* 11. Error handling, mutability, and tolerance
* 12. Implementation skeleton
* 13. Test plan and acceptance checklist
* 14. Common pitfalls
* Appendix A. Minimum backend checklist

# 1. Purpose and intended architecture

TopologicPy has been migrated so that direct access to the current geometry/topology kernel is centralised behind Core.py. The goal of a replacement backend is not to rewrite TopologicPy. The goal is to provide an adapter that behaves like topologic\_core at the boundary that TopologicPy now uses.

|  |
| --- |
| TopologicPy public wrappers and algorithms  |  v  Core.py facade  |  v  Replacement backend adapter  |  v  Actual geometry/topology kernel |

The replacement backend may be implemented using OCCT, CGAL, libigl, a custom non-manifold kernel, a graph-and-BREP hybrid, or another modelling kernel. However, TopologicPy should continue to see a topologic\_core-shaped API: namespaces such as Vertex, Edge, Face, CellComplex, Dictionary, Graph and Topology; objects that pass type checks; and instance methods that follow the same argument conventions.

# 2. The backend contract in one page

* Expose the required namespaces listed in this guide. Each namespace may be a class, a module-like object, or an adapter class with static methods.
* Return backend-native objects that are recognised by Core.Namespace("Vertex"), Core.Namespace("Edge"), etc. for isinstance checks.
* Implement attribute objects for IntAttribute, DoubleAttribute, StringAttribute, and ListAttribute.
* Support Core.InstanceCall(obj, methodName, \*args, \*\*kwargs) by ensuring backend objects expose the expected instance methods.
* Preserve list-populating methods that mutate an output list passed by the caller.
* Preserve TopologicPy type IDs and type ordering.
* Implement enough serialization to support BREPString/String/ByString round-trips used by multiprocessing, dictionaries, CSG, and graph workflows.
* Do not move TopologicPy algorithms into the backend. The backend is the primitive kernel and persistence layer, not the analytical layer.

# 3. Required namespaces and object model

At minimum, a backend must expose the following names. Optional utility namespaces can be implemented as aliases or stubs only if no active code path calls them.

|  |  |
| --- | --- |
| **Namespace or class** | **Backend responsibility** |
| Vertex | Class/namespace for point-like primitives. Must be a real class or return a class through Core.Namespace("Vertex") so isinstance checks work. |
| Edge | Class/namespace for directed line/curve primitives. Must expose construction and start/end vertex access. |
| Wire | Ordered edge collection. Must support closedness, vertex extraction, and edge extraction. |
| Face | Planar or surface-bounded region. Must support external/internal boundaries, area, normal, triangulation, and point containment. |
| Shell | Collection of faces. Must support face/edge/vertex extraction and closedness. |
| Cell | 3D volume. Must support shells, vertices, internal boundaries, volume, internal vertex, and containment. |
| CellComplex | Non-manifold volumetric complex. Must support cell/face/edge/vertex extraction, external boundary, internal boundaries, and merge. |
| Cluster | Heterogeneous topology collection. Must support extraction of all sub-topology classes. |
| Graph | Topologic graph primitive. Must support vertices, edges, adjacency, mutation, edge lookup, and graph set operations. |
| Topology | Common base namespace for serialisation, booleans, transform, dictionary, type, content, contexts, and sub/super-topology access. |
| Dictionary | Core dictionary object with string keys and attribute values. |
| Aperture | Aperture object and aperture-to-topology access. |
| Context | Context object connecting apertures/contents to host topology parameters. |
| TopologyUtility | Transform/translate/rotate/scale utilities. Can alias Topology if Core exposes it that way. |
| VertexUtility | Adjacency utilities from vertices to higher-order topologies. |
| EdgeUtility | Length, parameter, and adjacency utilities from edges. |
| WireUtility | Adjacency utilities from wires. |
| FaceUtility | Area, normal, parameters, point containment, trimming, triangulation, and adjacency utilities. |
| ShellUtility | Adjacency utilities from shells. |
| CellUtility | Containment, internal vertex, volume, and adjacency utilities. |
| CellComplexUtility | Optional. Provide if the active Core facade exposes it. |
| ClusterUtility | Optional. Provide if the active Core facade exposes it. |
| GraphUtility | Optional. Provide if the active Core facade exposes it. |
| IntAttribute, DoubleAttribute, StringAttribute, ListAttribute | Standalone attribute classes used by Dictionary conversion. They must be actual classes for isinstance checks. |

# 4. Type IDs and type checks

TopologicPy relies on integer type IDs and type ordering. A replacement backend must either return these values directly from topology.Type(), or the Core adapter must translate backend-specific type codes to these values.

|  |  |
| --- | --- |
| **Type name** | **Required TypeID** |
| Vertex | 1 |
| Edge | 2 |
| Wire | 4 |
| Face | 8 |
| Shell | 16 |
| Cell | 32 |
| CellComplex | 64 |
| Cluster | 128 |
| Aperture | 256 |
| Context | 512 |
| Dictionary | 1024 |
| Graph | 2048 |
| Topology | 4096 |

Important details:

* CellComplex must be tested before Cell in string-based type checks because both share the prefix "cell".
* Topology.IsInstance(obj, "Topology") should return True for all topology subclasses: Vertex, Edge, Wire, Face, Shell, Cell, CellComplex, and Cluster.
* Graph, Dictionary, Context, and Aperture are not always subclasses of Topology in every backend design. The adapter must account for this explicitly.
* If the underlying kernel does not have an inheritance hierarchy matching topologic\_core, provide proxy classes or override Core.Namespace/IsInstance logic accordingly.

# 5. Method catalogue by namespace

The following catalogue is the practical backend surface required by the current TopologicPy Core migration. Implement these names exactly in the adapter even if the underlying kernel uses different names internally.

## Aperture

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByTopologyContext(topology, context) | Create an aperture object connected to a host topology/context. |
| Topology(aperture) | Return the topology associated with an aperture. |

## Context

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByTopologyParameters(topology, u=0.5, v=0.5, w=0.5) | Create a context at parametric coordinates on/in a topology. |
| Topology(context) | Return the topology associated with a context. |

## Dictionary and attributes

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| IntAttribute(value) | Create integer attribute. Bool values are encoded as 0/1 in TopologicPy. |
| DoubleAttribute(value) | Create floating-point attribute. |
| StringAttribute(value) | Create string attribute. The sentinel "\_\_NONE\_\_" represents Python None. |
| ListAttribute(value) | Create list attribute from a list of already-converted attribute objects. |
| IntValue(attribute) | Return int payload from an IntAttribute instance. |
| DoubleValue(attribute) | Return float payload from a DoubleAttribute instance. |
| StringValue(attribute) | Return string payload from a StringAttribute instance. |
| ListValue(attribute) | Return list of attribute objects from a ListAttribute instance. |
| ByKeysValues(keys, values) | Create a Dictionary from list[str] and list[Attribute]. |
| Keys(dictionary) | Return list[str]. |
| ValueAtKey(dictionary, key) | Return an Attribute object; Dictionary.py converts it to Python values. |

## Vertex

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByCoordinates(x=0, y=0, z=0) | Return a Vertex object. |
| X(vertex), Y(vertex), Z(vertex) | Return coordinate scalar. TopologicPy rounds at wrapper level. |

## VertexUtility

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| AdjacentEdges(vertex, hostTopology, output) | Populate output list. |
| AdjacentWires(vertex, hostTopology, output) | Populate output list. |
| AdjacentFaces(vertex, hostTopology, output) | Populate output list. |
| AdjacentShells(vertex, hostTopology, output) | Populate output list. |
| AdjacentCells(vertex, hostTopology, output) | Populate output list. |
| AdjacentCellComplexes(vertex, hostTopology, output) | Populate output list. |

## Edge

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByStartVertexEndVertex(vertexA, vertexB, tolerance=None) | Create an edge. Current topologic\_core may ignore tolerance; the adapter should accept it anyway. |
| StartVertex(edge) | Return the start vertex. |
| EndVertex(edge) | Return the end vertex. |
| Vertices(edge, hostTopology=None) | Return or populate vertices. TopologicPy often routes edge.Vertices(None, output). |

## EdgeUtility

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| Length(edge) | Return edge length. |
| ParameterAtPoint(edge, vertex) | Return edge parameter at vertex/point; should fail predictably if point is not on curve. |
| AdjacentWires(edge, output) | Populate output list. |
| AdjacentFaces(edge, output) | Populate output list. |
| AdjacentShells(output) | Populate output list. Note legacy signature may not pass edge. |
| AdjacentCells(output) | Populate output list. Note legacy signature may not pass edge. |
| AdjacentCellComplexes(output) | Populate output list. Note legacy signature may not pass edge. |

## Wire

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByEdges(edges) | Create wire from ordered or unordered edges. Preserve enough ordering for boundary use. |
| Edges(wire, hostTopology=None) | Return or populate list of edges. |
| Vertices(wire, hostTopology=None) | Return or populate list of vertices. |
| IsClosed(wire) | Return bool closedness. |

## WireUtility

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| AdjacentVertices(wire, output) | Populate output list. |
| AdjacentEdges(wire, output) | Populate output list. |
| AdjacentWires(wire, output) | Populate output list. |
| AdjacentFaces(wire, output) | Populate output list. |
| AdjacentShells(output) | Populate output list. |
| AdjacentCells(output) | Populate output list. |
| AdjacentCellComplexes(output) | Populate output list. |

## Face

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByExternalBoundary(wire) | Create a face from one external wire. |
| ByExternalInternalBoundaries(externalBoundary, internalBoundaries, tolerance=0.0001) | Create a face with holes. |
| ExternalBoundary(face) | Return external boundary wire. |
| InternalBoundaries(face) | Populate/return list of internal boundary wires. Important: signature uses only output list in the legacy instance method. |
| Edges(face, hostTopology=None) | Return/populate edges. |
| Vertices(face, hostTopology=None) | Return/populate vertices. |
| Wires(face, hostTopology=None) | Return/populate wires. |

## FaceUtility

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| Area(face) | Return area. |
| NormalAtParameters(face, u=0.5, v=0.5) | Return normal vector. |
| Triangulate(face, tolerance, output) | Populate output list with triangular faces. |
| TrimByWire(face, wire, reverse=False) | Return trimmed face/topology. |
| VertexAtParameters(face, u, v) | Return vertex at parameters. |
| ParametersAtVertex(face, vertex) | Return parameter pair/list. |
| IsInside(face, vertex, tolerance=0.0001) | Return bool/int containment result. |
| AdjacentVertices(face, output) | Populate output list. |
| AdjacentEdges(face, output) | Populate output list. |
| AdjacentWires(face, output) | Populate output list. |
| AdjacentShells(output) | Populate output list. |
| AdjacentCells(output) | Populate output list. |
| AdjacentCellComplexes(output) | Populate output list. |

## Shell

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByFaces(faces, tolerance=0.0001) | Create shell from faces. |
| Edges(shell, hostTopology=None) | Return/populate edges. |
| Faces(shell, hostTopology=None) | Return/populate faces. |
| Vertices(shell, hostTopology=None) | Return/populate vertices. |
| Wires(shell, hostTopology=None) | Return/populate wires. |
| IsClosed(shell) | Return bool closedness. |

## ShellUtility

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| AdjacentVertices(shell, output) | Populate output list. |
| AdjacentEdges(shell, output) | Populate output list. |
| AdjacentWires(shell, output) | Populate output list. |
| AdjacentFaces(shell, output) | Populate output list. |
| AdjacentShells(output) | Populate output list. |
| AdjacentCells(output) | Populate output list. |
| AdjacentCellComplexes(output) | Populate output list. |

## Cell

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByFaces(faces, tolerance=0.0001) | Create cell from faces. |
| InternalBoundaries(cell) | Populate/return inner shell boundaries. |
| Shells(cell, hostTopology=None) | Return/populate shells. |
| Vertices(cell, hostTopology=None) | Return/populate vertices. |
| Wires(cell, hostTopology=None) | Return/populate wires. |

## CellUtility

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| Contains(cell, vertex, tolerance=0.0001) | Return containment classification; TopologicPy usually interprets positive/internal results. |
| InternalVertex(cell, tolerance=0.0001) | Return a vertex inside the cell. |
| Volume(cell) | Return volume. |
| AdjacentVertices(cell, output) | Populate output list. |
| AdjacentEdges(cell, output) | Populate output list. |
| AdjacentWires(cell, output) | Populate output list. |
| AdjacentFaces(cell, output) | Populate output list. |
| AdjacentShells(output) | Populate output list. |
| AdjacentCellComplexes(output) | Populate output list. |

## CellComplex

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByFaces(faces, tolerance=0.0001, copyAttributes=False) | Create cell complex from faces. This is a performance-critical constructor. |
| Merge(cellComplex, topology, transferDictionaries=False, tolerance=0.0001) | Merge topology into cell complex. |
| Cells(cellComplex, hostTopology=None) | Return/populate cells. |
| Edges(cellComplex, hostTopology=None) | Return/populate edges. |
| ExternalBoundary(cellComplex) | Return external boundary, usually a Cell or Shell depending on backend. |
| Faces(cellComplex, hostTopology=None) | Return/populate faces. |
| InternalBoundaries(cellComplex) | Populate/return internal boundary faces. |
| NonManifoldFaces(cellComplex) | Populate/return non-manifold faces; signature uses only output list. |
| Vertices(cellComplex, hostTopology=None) | Return/populate vertices. |
| Wires(cellComplex, hostTopology=None) | Return/populate wires. |

## Cluster

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByTopologies(topologies, copyAttributes=False) | Create cluster from mixed topology list. |
| CellComplexes(cluster, hostTopology=None) | Return/populate cell complexes. |
| Cells(cluster, hostTopology=None) | Return/populate cells. |
| Edges(cluster, hostTopology=None) | Return/populate edges. |
| Faces(cluster, hostTopology=None) | Return/populate faces. |
| Shells(cluster, hostTopology=None) | Return/populate shells. |
| Vertices(cluster, hostTopology=None) | Return/populate vertices. |
| Wires(cluster, hostTopology=None) | Return/populate wires. |

## Graph

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| ByVerticesEdges(vertices, edges) | Required if current Core exposes Graph namespace directly; create graph primitive. |
| Vertices(graph, output) | Populate vertex list. Some wrappers call graph.Vertices(vertices) or graph.Vertices(output). |
| Edges(graph, vertices=None, tolerance=0.0001) | Return/populate graph edges, optionally incident to a vertex subset. |
| AddVertices(vertices, tolerance) | Mutate graph by adding vertices. |
| RemoveVertices(vertices) | Mutate graph by removing vertices. |
| RemoveEdges(edges) | Mutate graph by removing edges. |
| AdjacentVertices(vertex, output) | Populate vertices adjacent to a vertex. |
| AllPaths(vertexA, vertexB, searchLimitFlag, timeLimit, output) | Populate path output list. |
| Connect(vertexA, vertexB) | Connect two vertices in graph. |
| Edge(vertexA, vertexB, tolerance) | Return edge connecting two graph vertices. |
| ContainsVertex(vertex, tolerance) | Return bool-like result. |
| ContainsEdge(edge, tolerance) | Return bool-like result. |
| DegreeSequence() | Return list of degrees. |
| Density() | Return graph density. |
| Difference(graph) | Return graph difference. |
| IsolatedVertices(output) | Populate isolated vertices. |
| Keys() | Return graph keys if backend provides key/value data. |
| SetDictionary(dictionary) | Set graph dictionary. |

## Topology

|  |  |
| --- | --- |
| **Method name / signature** | **Notes and expectations** |
| AddContent(topology, content) | Attach content to topology. |
| AddContents(topology, contents, typeID) | Attach contents of a given topology type. |
| AddContext(topology, context) | Attach context. |
| Analyze(topology) | Return analysis string. |
| Apertures(topology, hostTopology=None) | Populate/return apertures. Legacy may accept either Apertures(output) or Apertures(hostTopology, output). |
| ByOcctShape(occtShape, guid="") | Optional if backend supports OCCT interoperability. |
| ByString(string) | Deserialize from backend string representation. |
| BREPString(topology, version=0) | Return BREP or backend-compatible string representation. |
| String(topology, version=0) | Return textual serialization. |
| CenterOfMass(topology) | Return vertex/point at centre of mass. |
| Centroid(topology) | Return centroid vertex. |
| Cleanup(topology) | Return cleaned topology. |
| Contents(topology) | Populate/return contents. |
| Contexts(topology) | Populate/return contexts. |
| Copy(topology) | Deep copy; do not return a shared mutable object. |
| Difference/Divide/Impose/Imprint/Merge/Slice/Union/XOR(topologyA, topologyB, transferDictionaries=False) | Boolean or topological operation. Keep argument order semantics. |
| Intersect(topologyA, topologyB) | Intersection. Existing TopologicPy has a workaround for topologic\_core intersection behaviour; maintain predictable return types. |
| Edges/Faces/Shells/Vertices/Wires(topology, hostTopology=None) | Populate/return sub-topology lists. |
| GetDictionary(topology) | Return dictionary. |
| SetDictionary(topology, dictionary) | Mutate and return topology, or make Core adapter return topology after mutation. |
| GetOcctShape(topology) | Optional raw geometry escape hatch. |
| GetTypeAsString(topology) | Return type string. |
| Type(topology) | Return numeric type ID, consistent with Topology.TypeID. |
| IsSame(topologyA, topologyB) | Return strict topological/geometric sameness according to tolerance rules. |
| RemoveContents(topology, contents) | Remove attached contents. |
| SelectSubtopology(topology, selector, typeID) | Return selected subtopology. |
| SelfMerge(topology) | Return self-merged topology. |
| SharedTopologies(topologyA, topologyB, typeID) | Populate/return shared topology list. |
| SubTopologies(topology, typeName, hostTopology=None) | Generic extractor routed to Vertices/Edges/Wires/Faces/Shells/Cells/CellComplexes/Clusters/Apertures. |
| SuperTopologies(topology, hostTopology, typeName) | Find supertopologies of a given type within a host. |
| Transform(topology, \*args) | Apply 4x4 matrix or backend transform arguments. |
| Translate(topology, x, y, z) | Translate. |
| Rotate(topology, origin, x, y, z, angle) | Rotate around axis/origin. |
| Scale(topology, origin, x, y, z) | Scale about origin. |

# 6. Instance-call conventions and list-populating methods

The most important nuance in the migration is the difference between scalar-returning instance calls and list-populating instance calls. The replacement backend must support both.

## 6.1 Scalar-returning instance calls

These calls return a value directly. They are safe to route as Core.InstanceCall(obj, "Method", ...).

|  |
| --- |
| x = Core.InstanceCall(vertex, "X")  sv = Core.InstanceCall(edge, "StartVertex")  d = Core.InstanceCall(topology, "GetDictionary")  type\_id = Core.InstanceCall(topology, "Type") |

## 6.2 List-populating instance calls

These calls mutate an output list supplied by the caller. Do not replace them with direct assignment from the return value. The return value may be a status code or None.

|  |  |
| --- | --- |
| edges = []  # old: \_ = topology.Edges(None, edges)  \_ = Core.InstanceCall(topology, "Edges", None, edges)  return edges | |
| **Pattern** | **Nuance** |
| obj.Vertices(hostTopology, output) | hostTopology may be None. Do not return the status code as the list. |
| obj.Edges(hostTopology, output) | Used by topologies, wires, shells, cells, cell complexes, clusters, and graphs. |
| obj.Wires(hostTopology, output) | Used on wire-bearing topologies. |
| obj.Faces(hostTopology, output) | Used on face-bearing topologies. |
| obj.Shells(hostTopology, output) | Used on shell-bearing topologies. |
| obj.Cells(hostTopology, output) | Used on cell-bearing topologies. |
| obj.CellComplexes(hostTopology, output) | Used on clusters and super-topology searches. |
| obj.Clusters(hostTopology, output) | Used by generic sub-topology extraction. |
| obj.Apertures(output) or obj.Apertures(hostTopology, output) | Your adapter should tolerate both forms if possible. |
| obj.Contents(output) | Used for attached contents. |
| obj.Contexts(output) | Used for contexts. |
| face.InternalBoundaries(output) | No hostTopology parameter. |
| cell.InternalBoundaries(output) | No hostTopology parameter. |
| cellComplex.InternalBoundaries(output) | No hostTopology parameter. |
| cellComplex.NonManifoldFaces(output) | No hostTopology parameter. |
| topologyA.SharedTopologies(topologyB, typeID, output) | Three parameters after self. |
| graph.AdjacentVertices(vertex, output) | Graph-specific adjacency extractor. |
| graph.AllPaths(vertexA, vertexB, True, timeLimit, output) | Path extraction mutates output list. |

# 7. Dictionaries and attributes

TopologicPy dictionaries are not plain Python dictionaries at the core boundary. They are core Dictionary objects whose values are Attribute objects. Dictionary.py converts Python values to attributes on write and converts attributes back to Python values on read.

|  |  |
| --- | --- |
| **Python value** | **Core attribute representation** |
| None | StringAttribute("\_\_NONE\_\_") |
| bool | IntAttribute(0 or 1) |
| int | IntAttribute(value) |
| float | DoubleAttribute(value) |
| str | StringAttribute(value) |
| dict | StringAttribute(json.dumps(dict)) |
| Topology object | StringAttribute(Topology.JSONString/BREP-compatible serialization) |
| tuple/list | ListAttribute([converted attribute, ...]) |

Required behaviour:

* Dictionary.ByKeysValues(keys, values) receives values that are already Attribute objects.
* Dictionary.ValueAtKey(dictionary, key) must return an Attribute object, not a Python value.
* Attribute instance methods IntValue, DoubleValue, StringValue, and ListValue must exist.
* ListValue must return a list of Attribute objects so Dictionary.\_ConvertAttribute can recurse.
* The sentinel "\_\_NONE\_\_" must survive storage and be converted back to Python None by Dictionary.py.
* Do not silently coerce all values to strings. TopologicPy depends on numeric types remaining numeric after round-trip.

# 8. Topology and geometry behaviour

The replacement backend must preserve the observable behaviour of topologic\_core at the Core boundary. The internal representation can be different, but TopologicPy expects non-manifold topology, shared sub-topologies, dictionaries, contexts, apertures, and topology traversal.

## 8.1 Non-manifold topology

CellComplex is central to TopologicPy. It is not enough to provide separate solids. The backend must represent or emulate shared faces, shared edges, and multiple cells incident to the same face. Methods such as SharedTopologies, SuperTopologies, NonManifoldFaces, CellComplex.ByFaces, and CellComplex.ExternalBoundary depend on this.

## 8.2 Boolean operations

* Union, Difference, Intersect, Merge, Slice, Impose, Imprint, Divide, and XOR must preserve input order semantics.
* Return None for true failure if TopologicPy expects failure, not an arbitrary empty topology.
* transferDictionaries=False must be accepted even if ignored internally.
* For face-on-face operations, return face/shell/cluster types that TopologicPy can decompose further.

## 8.3 Transform operations

* Transform must accept the matrix format used by TopologicPy Matrix methods, usually a 4x4 nested list.
* Translate, Rotate, and Scale should return new transformed topology objects unless the adapter is explicitly designed for mutation and the wrappers account for it.
* Preserve attached dictionaries through transformations where possible. If the underlying kernel drops attributes, the adapter should copy them back.

# 9. Graph behaviour

Graph is partly a core primitive and partly a TopologicPy analytical abstraction. The backend should implement primitive graph storage, mutation, adjacency, vertex/edge extraction, and edge lookup. Higher-level algorithms such as centrality, shortest paths, layouts, CSV import/export, Kuzu/Neo4j integration, and GraphRAG should remain in TopologicPy.

* Graph vertices are Topologic Vertex objects with dictionaries.
* Graph edges are Topologic Edge objects and may carry dictionaries.
* Graph.AddVertices mutates the graph in current topologic\_core behaviour. If your backend is immutable, the adapter must return a graph and Core/Graph.py must use that return consistently.
* Graph.AdjacentVertices(vertex, output) is list-populating.
* Graph.Edge(vertexA, vertexB, tolerance) should return the stored edge when possible, not merely create a geometric edge with no dictionary.
* Directedness is subtle: TopologicPy often treats graph adjacency as undirected but edge StartVertex/EndVertex still matter for routing and adjacency matrices.

# 10. Serialization and persistence

Several TopologicPy workflows serialise topologies into strings and later reconstruct them. A backend replacement must support this even if the string is not literally OpenCASCADE BREP. The public method names should remain BREPString, String, and ByString/ByBREPString at the TopologicPy layer.

* The string format must round-trip geometry, topology, and preferably dictionaries when requested by wrappers.
* Multiprocessing code serialises topologies before sending work to child processes.
* CSG and GraphRAG workflows may store topology strings inside dictionaries.
* If the backend uses external handles or memory-only objects, provide a portable textual representation at the adapter level.

# 11. Error handling, mutability, and tolerance

|  |  |
| --- | --- |
| **Topic** | **Backend rule** |
| Errors | Raise predictable Python exceptions at the adapter boundary or return None where TopologicPy wrappers expect None. Avoid process crashes from the underlying kernel. |
| Mutability | Know which methods mutate objects. SetDictionary, AddContent, AddVertices, RemoveEdges and similar methods are often mutation-oriented. |
| Tolerance | Accept tolerance parameters even when the underlying operation ignores them. TopologicPy often passes tolerance uniformly. |
| Precision | Do not round inside the backend unless the method specifically asks for it. TopologicPy wrappers apply mantissa rounding. |
| Ordering | Maintain deterministic ordering of vertices, edges, wires, faces and graph vertices whenever possible. |
| Thread/process safety | Objects may be serialised to child processes. Avoid backend state that cannot be reconstructed in a new process. |

# 12. Implementation skeleton

A practical backend should be written as an adapter, not as a direct replacement of all TopologicPy classes.

|  |
| --- |
| class MyBackend:  class Vertex:  @staticmethod  def ByCoordinates(x=0, y=0, z=0):  return MyVertex(x, y, z)  class Edge:  @staticmethod  def ByStartVertexEndVertex(vertexA, vertexB, tolerance=None):  return MyEdge(vertexA, vertexB)  class Dictionary:  @staticmethod  def ByKeysValues(keys, values):  return MyDictionary(keys, values)  class Topology:  @staticmethod  def SetDictionary(topology, dictionary):  topology.SetDictionary(dictionary)  return topology  # Runtime installation  from topologicpy.Core import Core  Core.SetBackend(MyBackend) |

## 12.1 Object method skeletons

|  |
| --- |
| class MyTopologyBase:  def Vertices(self, hostTopology, output):  output.extend(self.\_vertices(hostTopology))  return 0  def Edges(self, hostTopology, output):  output.extend(self.\_edges(hostTopology))  return 0  def GetDictionary(self):  return self.\_dictionary  def SetDictionary(self, dictionary):  self.\_dictionary = dictionary  return 0  def Type(self):  return self.\_type\_id |

## 12.2 List-populating adapter helper

|  |
| --- |
| def \_populate(output, values):  if output is None:  raise ValueError("Output list cannot be None for this core-style method.")  output.extend(values or [])  return 0 |

# 13. Test plan and acceptance checklist

Use progressive testing. Do not attempt to replace the backend and then run the whole test suite only at the end.

1. Install the backend using Core.SetBackend(MyBackend).
2. Run direct smoke tests for Vertex.ByCoordinates, Edge.ByStartVertexEndVertex, Face.ByExternalBoundary, CellComplex.ByFaces, Dictionary.ByKeysValues, and Graph.ByVerticesEdges.
3. Run dictionary round-trip tests for None, bool, int, float, string, dict, list, nested list, and topology string values.
4. Run list-populating tests for Vertices, Edges, Faces, Shells, Cells, CellComplexes, Apertures, Contents, Contexts, InternalBoundaries, NonManifoldFaces, SharedTopologies, and Graph.AdjacentVertices.
5. Run type tests for all type IDs and IsInstance combinations.
6. Run geometry construction tests: Vertex, Edge, Wire, Face, Shell, Cell, CellComplex, Cluster.
7. Run boolean and transform tests.
8. Run graph tests, including adjacency, edge lookup, add/remove vertices and edges, and dictionary transfer.
9. Run the full pytest suite.
10. Run any project-specific IFC, energy model, graph database, and GraphRAG workflows that rely on serialisation and dictionaries.

|  |  |
| --- | --- |
| **Acceptance check** | **Pass condition** |
| No direct topologic\_core use outside Core.py | The AST checker reports no imports or topologic.\* references outside Core.py. |
| Core namespace smoke test | Every required Core namespace exists and exposes required methods. |
| Dictionary round-trip | Dictionary.ValueAtKey returns correct Python values for scalar, list, dict, None and topology values. |
| List-populating methods | All methods that take output lists return populated Python lists through TopologicPy wrappers. |
| Type identity | Topology.IsInstance and Topology.Type return expected results. |
| Serialization | BREPString/String and ByString/ByBREPString round-trip representative topologies. |
| pytest | All tests pass. |

# 14. Common pitfalls

|  |  |
| --- | --- |
| **Pitfall** | **Why it matters / mitigation** |
| Core.Namespace and isinstance | If TopologicPy calls isinstance(obj, Core.Namespace("Vertex")), Core.Namespace must return an actual class/type, not a proxy instance. |
| List-populating methods | Never convert list-populating methods into scalar-return methods. Preserve the mutable output list and ignore the status code unless needed. |
| None hostTopology | Many calls pass None as hostTopology. A backend must treat None as no host filter, not as an error. |
| Transfer-dictionary flags | Boolean operation methods often receive transferDictionaries=False. Keep the parameter even if the backend ignores it. |
| Dictionary sentinels | TopologicPy stores Python None as StringAttribute("\_\_NONE\_\_"). Do not treat that as a normal string on read. |
| Nested list attributes | ListAttribute payloads are lists of Attribute objects, not raw Python values. Convert recursively in both directions. |
| Topological mutation | SetDictionary, AddContent, AddVertices, RemoveEdges, etc. may mutate objects. If your backend is immutable, the adapter must return and propagate replacements consistently. |
| Object identity | Graph and topology functions often compare objects or rely on object identity. Proxy objects must have stable identity and equality semantics. |
| Directed edges | TopologicPy treats an Edge as directed for StartVertex/EndVertex, even if graph analysis later treats connections as bidirectional. |
| Serialization | BREPString/String/ByString must round-trip enough information for multiprocessing, graph storage, CSG, and dictionaries that store topologies as strings. |
| Tolerance | TopologicPy wrappers do a lot of tolerance checking. Backend constructors should still accept tolerance parameters where passed, even if ignored. |
| Ordering | Methods that return vertices/edges of wires and faces must be deterministic where algorithms depend on boundary order. |
| Booleans returning None | TopologicPy often interprets None as a failed operation. Do not return empty clusters for true failure unless the wrapper expects it. |
| OCCT escape hatches | GetOcctShape and ByOcctShape can be stubs only if the parts of TopologicPy used in your deployment never call them; otherwise implement or raise a clear exception. |
| Graph algorithms vs graph kernel | Do not move TopologicPy graph algorithms into the backend. The backend should implement primitive graph storage and access only. |

# Appendix A. Minimum backend checklist

* Implement namespace: Aperture
* Implement namespace: Context
* Implement namespace: Dictionary and attributes
* Implement namespace: Vertex
* Implement namespace: VertexUtility
* Implement namespace: Edge
* Implement namespace: EdgeUtility
* Implement namespace: Wire
* Implement namespace: WireUtility
* Implement namespace: Face
* Implement namespace: FaceUtility
* Implement namespace: Shell
* Implement namespace: ShellUtility
* Implement namespace: Cell
* Implement namespace: CellUtility
* Implement namespace: CellComplex
* Implement namespace: Cluster
* Implement namespace: Graph
* Implement namespace: Topology
* Implement Core.SetBackend smoke test.
* Implement Core.InstanceCall compatibility for scalar and list-populating methods.
* Implement type IDs and IsInstance support.
* Implement dictionary/attribute conversion support.
* Implement topology serialisation round-trip.
* Implement graph primitive mutation and adjacency.
* Run full pytest suite.

# Appendix B. Compact method index

**Aperture:** ByTopologyContext(topology, context); Topology(aperture)

**Context:** ByTopologyParameters(topology, u=0.5, v=0.5, w=0.5); Topology(context)

**Dictionary and attributes:** IntAttribute(value); DoubleAttribute(value); StringAttribute(value); ListAttribute(value); IntValue(attribute); DoubleValue(attribute); StringValue(attribute); ListValue(attribute); ByKeysValues(keys, values); Keys(dictionary); ValueAtKey(dictionary, key)

**Vertex:** ByCoordinates(x=0, y=0, z=0); X(vertex), Y(vertex), Z(vertex)

**VertexUtility:** AdjacentEdges(vertex, hostTopology, output); AdjacentWires(vertex, hostTopology, output); AdjacentFaces(vertex, hostTopology, output); AdjacentShells(vertex, hostTopology, output); AdjacentCells(vertex, hostTopology, output); AdjacentCellComplexes(vertex, hostTopology, output)

**Edge:** ByStartVertexEndVertex(vertexA, vertexB, tolerance=None); StartVertex(edge); EndVertex(edge); Vertices(edge, hostTopology=None)

**EdgeUtility:** Length(edge); ParameterAtPoint(edge, vertex); AdjacentWires(edge, output); AdjacentFaces(edge, output); AdjacentShells(output); AdjacentCells(output); AdjacentCellComplexes(output)

**Wire:** ByEdges(edges); Edges(wire, hostTopology=None); Vertices(wire, hostTopology=None); IsClosed(wire)

**WireUtility:** AdjacentVertices(wire, output); AdjacentEdges(wire, output); AdjacentWires(wire, output); AdjacentFaces(wire, output); AdjacentShells(output); AdjacentCells(output); AdjacentCellComplexes(output)

**Face:** ByExternalBoundary(wire); ByExternalInternalBoundaries(externalBoundary, internalBoundaries, tolerance=0.0001); ExternalBoundary(face); InternalBoundaries(face); Edges(face, hostTopology=None); Vertices(face, hostTopology=None); Wires(face, hostTopology=None)

**FaceUtility:** Area(face); NormalAtParameters(face, u=0.5, v=0.5); Triangulate(face, tolerance, output); TrimByWire(face, wire, reverse=False); VertexAtParameters(face, u, v); ParametersAtVertex(face, vertex); IsInside(face, vertex, tolerance=0.0001); AdjacentVertices(face, output); AdjacentEdges(face, output); AdjacentWires(face, output); AdjacentShells(output); AdjacentCells(output); AdjacentCellComplexes(output)

**Shell:** ByFaces(faces, tolerance=0.0001); Edges(shell, hostTopology=None); Faces(shell, hostTopology=None); Vertices(shell, hostTopology=None); Wires(shell, hostTopology=None); IsClosed(shell)

**ShellUtility:** AdjacentVertices(shell, output); AdjacentEdges(shell, output); AdjacentWires(shell, output); AdjacentFaces(shell, output); AdjacentShells(output); AdjacentCells(output); AdjacentCellComplexes(output)

**Cell:** ByFaces(faces, tolerance=0.0001); InternalBoundaries(cell); Shells(cell, hostTopology=None); Vertices(cell, hostTopology=None); Wires(cell, hostTopology=None)

**CellUtility:** Contains(cell, vertex, tolerance=0.0001); InternalVertex(cell, tolerance=0.0001); Volume(cell); AdjacentVertices(cell, output); AdjacentEdges(cell, output); AdjacentWires(cell, output); AdjacentFaces(cell, output); AdjacentShells(output); AdjacentCellComplexes(output)

**CellComplex:** ByFaces(faces, tolerance=0.0001, copyAttributes=False); Merge(cellComplex, topology, transferDictionaries=False, tolerance=0.0001); Cells(cellComplex, hostTopology=None); Edges(cellComplex, hostTopology=None); ExternalBoundary(cellComplex); Faces(cellComplex, hostTopology=None); InternalBoundaries(cellComplex); NonManifoldFaces(cellComplex); Vertices(cellComplex, hostTopology=None); Wires(cellComplex, hostTopology=None)

**Cluster:** ByTopologies(topologies, copyAttributes=False); CellComplexes(cluster, hostTopology=None); Cells(cluster, hostTopology=None); Edges(cluster, hostTopology=None); Faces(cluster, hostTopology=None); Shells(cluster, hostTopology=None); Vertices(cluster, hostTopology=None); Wires(cluster, hostTopology=None)

**Graph:** ByVerticesEdges(vertices, edges); Vertices(graph, output); Edges(graph, vertices=None, tolerance=0.0001); AddVertices(vertices, tolerance); RemoveVertices(vertices); RemoveEdges(edges); AdjacentVertices(vertex, output); AllPaths(vertexA, vertexB, searchLimitFlag, timeLimit, output); Connect(vertexA, vertexB); Edge(vertexA, vertexB, tolerance); ContainsVertex(vertex, tolerance); ContainsEdge(edge, tolerance); DegreeSequence(); Density(); Difference(graph); IsolatedVertices(output); Keys(); SetDictionary(dictionary)

**Topology:** AddContent(topology, content); AddContents(topology, contents, typeID); AddContext(topology, context); Analyze(topology); Apertures(topology, hostTopology=None); ByOcctShape(occtShape, guid=""); ByString(string); BREPString(topology, version=0); String(topology, version=0); CenterOfMass(topology); Centroid(topology); Cleanup(topology); Contents(topology); Contexts(topology); Copy(topology); Difference/Divide/Impose/Imprint/Merge/Slice/Union/XOR(topologyA, topologyB, transferDictionaries=False); Intersect(topologyA, topologyB); Edges/Faces/Shells/Vertices/Wires(topology, hostTopology=None); GetDictionary(topology); SetDictionary(topology, dictionary); GetOcctShape(topology); GetTypeAsString(topology); Type(topology); IsSame(topologyA, topologyB); RemoveContents(topology, contents); SelectSubtopology(topology, selector, typeID); SelfMerge(topology); SharedTopologies(topologyA, topologyB, typeID); SubTopologies(topology, typeName, hostTopology=None); SuperTopologies(topology, hostTopology, typeName); Transform(topology, \*args); Translate(topology, x, y, z); Rotate(topology, origin, x, y, z, angle); Scale(topology, origin, x, y, z)
