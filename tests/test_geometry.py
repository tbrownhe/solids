from collections import Counter
from copy import deepcopy
from math import sqrt

import numpy as np
import pytest
from pydantic import ValidationError

from solids.geometry import Parameters, inset_polygon, make_design, topology
from solids.registry import SOLIDS

# Independent inventory fixtures, not values queried from registry metadata.
EXPECTED = {
    "tetrahedron": (4, 6, {3: 4}), "cube": (8, 12, {4: 6}),
    "octahedron": (6, 12, {3: 8}), "dodecahedron": (20, 30, {5: 12}),
    "icosahedron": (12, 30, {3: 20}),
    "truncated-tetrahedron": (12, 18, {3: 4, 6: 4}),
    "cuboctahedron": (12, 24, {3: 8, 4: 6}),
    "truncated-cube": (24, 36, {3: 8, 8: 6}),
    "truncated-octahedron": (24, 36, {4: 6, 6: 8}),
    "rhombicuboctahedron": (24, 48, {3: 8, 4: 18}),
    "truncated-cuboctahedron": (48, 72, {4: 12, 6: 8, 8: 6}),
    "snub-cube": (24, 60, {3: 32, 4: 6}),
    "icosidodecahedron": (30, 60, {3: 20, 5: 12}),
    "truncated-dodecahedron": (60, 90, {3: 20, 10: 12}),
    "truncated-icosahedron": (60, 90, {5: 12, 6: 20}),
    "rhombicosidodecahedron": (60, 120, {3: 20, 4: 30, 5: 12}),
    "truncated-icosidodecahedron": (120, 180, {4: 30, 6: 20, 10: 12}),
    "snub-dodecahedron": (60, 150, {3: 80, 5: 12}),
}


@pytest.mark.parametrize("solid_id", EXPECTED)
def test_source_topology_and_regular_polygons(solid_id):
    expected_v, expected_e, expected_inventory = EXPECTED[solid_id]
    mesh = topology(solid_id)
    assert len(mesh["vertices"]) == expected_v
    assert len(mesh["edges"]) == expected_e
    assert Counter(map(len, mesh["faces"])) == expected_inventory
    for face, normal in zip(mesh["faces"], mesh["normals"]):
        points = mesh["vertices"][face]
        center = points.mean(axis=0)
        assert np.dot(center, normal) > 0
        assert np.max(np.abs((points - center) @ normal)) < 1e-8
        lengths = np.linalg.norm(points - np.roll(points, 1, axis=0), axis=1)
        radii = np.linalg.norm(points - center, axis=1)
        assert lengths == pytest.approx(np.ones(len(face)), abs=1e-8)
        assert np.ptp(radii) < 1e-8
    design = make_design(Parameters(solid_id=solid_id))
    assert sum(t["quantity"] for t in design["templates"]) == sum(expected_inventory.values())
    face_ids = [f for t in design["templates"] for f in t["face_ids"]]
    assert sorted(face_ids) == list(range(len(mesh["faces"])))


def test_rhombicuboctahedron_acceptance_patterns():
    d = make_design(Parameters())
    assert (d["total_faces"], d["total_edges"]) == (26, 48)
    assert [(t["sides"], t["quantity"]) for t in d["templates"]] == [(3, 8), (4, 6), (4, 12)]
    tri, axial, belt = d["templates"]
    assert [e["angle_deg"] for e in tri["edges"]] == pytest.approx([72.3678051586] * 3)
    assert [e["angle_deg"] for e in axial["edges"]] == pytest.approx([67.5] * 4)
    assert [e["angle_deg"] for e in belt["edges"]] == pytest.approx([67.5, 72.3678051586] * 2)
    assert [e["adjacent_sides"] for e in belt["edges"]] == [4, 3, 4, 3]
    assert tri["edges"][0]["inset_mm"] == pytest.approx(1.90702347117)
    assert axial["edges"][0]["inset_mm"] == pytest.approx(2.48528137424)
    assert [e["dihedral_deg"] for e in tri["edges"]] == pytest.approx([144.7356103172] * 3)


def test_truncated_octahedron_acceptance_patterns():
    d = make_design(Parameters(solid_id="truncated-octahedron"))
    square, hexagon = d["templates"]
    assert (square["quantity"], hexagon["quantity"]) == (6, 8)
    assert [e["angle_deg"] for e in square["edges"]] == pytest.approx([62.6321948414] * 4)
    assert [e["angle_deg"] for e in hexagon["edges"]] == pytest.approx([54.7356103172, 62.6321948414] * 3)
    assert [e["adjacent_sides"] for e in hexagon["edges"]] == [6, 4, 6, 4, 6, 4]


def test_shrinkage_and_thickness_have_separate_effects():
    base = make_design(Parameters())
    shrunk = make_design(Parameters(shrinkage_percent=12))
    thicker = make_design(Parameters(thickness_mm=9))
    assert shrunk["cut_edge_mm"] == pytest.approx(120 / .88)
    assert np.array(shrunk["vertices"]) == pytest.approx(np.array(base["vertices"]) / .88)
    assert np.array(thicker["vertices"]) == pytest.approx(np.array(base["vertices"]))
    assert [e["angle_deg"] for e in shrunk["edges"]] == pytest.approx([e["angle_deg"] for e in base["edges"]])
    assert thicker["templates"][0]["edges"][0]["inset_mm"] == pytest.approx(base["templates"][0]["edges"][0]["inset_mm"] * 1.5)


@pytest.mark.parametrize("kwargs", [{"edge_length_mm": 0}, {"edge_length_mm": -1}, {"thickness_mm": 0}, {"shrinkage_percent": 100}, {"shrinkage_percent": -1}, {"edge_length_mm": float("nan")}, {"thickness_mm": float("inf")}, {"page_format": "a0"}, {"angle_precision": 5}])
def test_invalid_physical_inputs(kwargs):
    with pytest.raises(ValidationError):
        Parameters(**kwargs)


def test_overthick_panel_collapses_interior():
    d = make_design(Parameters(solid_id="cube", edge_length_mm=10, thickness_mm=6))
    assert d["templates"][0]["inset_polygon_mm"] == []
    assert d["warnings"]
    assert inset_polygon([[0, 0], [10, 0], [10, 10], [0, 10]], [6] * 4) == []


def test_open_mesh_is_rejected(monkeypatch):
    broken = deepcopy(SOLIDS["cube"])
    broken["faces"].pop()
    monkeypatch.setattr("solids.geometry.get_solid", lambda _: broken)
    with pytest.raises(ValueError, match="exactly two"):
        topology("intentionally-open-test-mesh")


def test_chiral_variants_remain_explicit():
    for solid_id in ("snub-cube", "snub-dodecahedron"):
        d = make_design(Parameters(solid_id=solid_id))
        assert d["chirality"]
        assert any("do not mirror" in warning for warning in d["warnings"])


@pytest.mark.parametrize("solid_id", EXPECTED)
def test_interior_up_cutting_view_reverses_exterior_edge_order(solid_id):
    design = make_design(Parameters(solid_id=solid_id))
    by_vertices = {tuple(e["vertices"]): e for e in design["edges"]}
    for template in design["templates"]:
        assert template["view"] == "interior-up"
        face_id = template["face_ids"][0]
        face = design["faces"][face_id]
        exterior = []
        for a, b in zip(face, face[1:] + face[:1]):
            edge = by_vertices[tuple(sorted((a, b)))]
            neighbor = next(f for f in edge["faces"] if f != face_id)
            exterior.append((round(edge["angle_deg"], 6), len(design["faces"][neighbor])))
        interior = list(reversed(exterior))
        displayed = [(round(e["angle_deg"], 6), e["adjacent_sides"]) for e in template["edges"]]
        assert any(displayed == interior[i:] + interior[:i] for i in range(len(interior)))
        polygon = template["polygon_mm"]
        assert sum(a[0]*b[1] - b[0]*a[1] for a,b in zip(polygon, polygon[1:]+polygon[:1])) > 0
