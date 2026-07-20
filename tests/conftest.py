# Copyright (C) 2026
# TopologicPy ontology regression test helpers.

import os
import pytest


def _import_or_skip(module_name, attr_name=None):
    try:
        module = __import__(module_name, fromlist=[attr_name] if attr_name else [])
        return getattr(module, attr_name) if attr_name else module
    except Exception as exc:
        pytest.skip(f"Could not import {module_name}: {exc}")


@pytest.fixture
def topologic_classes():
    Vertex = _import_or_skip("topologicpy.Vertex", "Vertex")
    Edge = _import_or_skip("topologicpy.Edge", "Edge")
    Graph = _import_or_skip("topologicpy.Graph", "Graph")
    Topology = _import_or_skip("topologicpy.Topology", "Topology")
    Dictionary = _import_or_skip("topologicpy.Dictionary", "Dictionary")
    Ontology = _import_or_skip("topologicpy.Ontology", "Ontology")
    return {
        "Vertex": Vertex,
        "Edge": Edge,
        "Graph": Graph,
        "Topology": Topology,
        "Dictionary": Dictionary,
        "Ontology": Ontology,
    }


@pytest.fixture
def simple_graph(topologic_classes):
    Vertex = topologic_classes["Vertex"]
    Edge = topologic_classes["Edge"]
    Graph = topologic_classes["Graph"]
    Topology = topologic_classes["Topology"]
    Dictionary = topologic_classes["Dictionary"]

    v1 = Vertex.ByCoordinates(0, 0, 0)
    v2 = Vertex.ByCoordinates(1, 0, 0)
    e1 = Edge.ByStartVertexEndVertex(v1, v2)

    v1 = Topology.SetDictionary(v1, Dictionary.ByPythonDictionary({
        "id": "n1",
        "index": 0,
        "label": "Room",
        "category": "space",
    }))
    v2 = Topology.SetDictionary(v2, Dictionary.ByPythonDictionary({
        "id": "n2",
        "index": 1,
        "label": "Corridor",
        "category": "space",
    }))
    e1 = Topology.SetDictionary(e1, Dictionary.ByPythonDictionary({
        "id": "e1",
        "src": 0,
        "dst": 1,
        "label": "adjacent",
        "category": "relationship",
    }))

    g = Graph.ByVerticesEdges([v1, v2], [e1])
    g = Topology.SetDictionary(g, Dictionary.ByPythonDictionary({
        "graph_id": "g1",
        "label": "Ontology Test Graph",
        "category": "graph",
    }))
    return g


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "optional_backend: tests requiring optional graph database backends"
    )
