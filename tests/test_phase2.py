from collections import Counter
import hashlib
import json
from pathlib import Path
from math import cos, radians, sin, sqrt

import numpy as np
import pymupdf
import pytest
from reportlab.lib.units import mm

from solids.fabrication import offset_polygon, signed_inset, slab_cell, cells_overlap
from solids.geometry import Parameters, make_design, topology
from solids.mesh import analyze_mesh, signed_joint, _triangle_contact
from solids.printing import pdf_bytes, svg_bytes, page_plan, edge_annotations, center_annotations, calibration_pdf_bytes
from solids.transforms import PRESETS


def test_phase1_default_exports_are_byte_identical():
    baseline=json.loads((Path(__file__).parent/'fixtures'/'phase1_pdf_sha256.json').read_text())
    for solid_id,expected in baseline.items():
        output=pdf_bytes(make_design(Parameters(solid_id=solid_id)))
        assert hashlib.sha256(output).hexdigest()==expected,solid_id


@pytest.mark.parametrize("turn,delta,tool,kind,side",[(60,120,60,"convex","interior"),(-60,240,60,"concave","exterior"),(0,180,90,"flat","interior"),(1e-10,180,90,"flat","interior")])
def test_signed_analytic_joints(turn,delta,tool,kind,side):
    result=signed_joint([0,0,1],[1,0,0],[cos(radians(turn)),sin(radians(turn)),0])
    assert result["dihedral_deg"]==pytest.approx(delta)
    assert result["angle_deg"]==pytest.approx(tool)
    assert result["edge_kind"]==kind
    assert result["cut_side"]==side


def excavated(**kwargs):
    return make_design(Parameters(solid_id="cube",preset_id="excavated-cube-single",apex_offset_mm=20,**kwargs))


def test_single_cube_topology_lengths_signed_bevels_and_blank_extension():
    d=excavated()
    assert (len(d["vertices"]),d["total_edges"],d["total_faces"])==(9,16,9)
    assert Counter(e["edge_kind"] for e in d["edges"])=={"concave":4,"convex":12}
    reflex=[e for e in d["edges"] if e["edge_kind"]=="concave"]
    assert [e["length_mm"] for e in reflex]==pytest.approx([sqrt(7600)]*4)
    assert [e["dihedral_deg"] for e in reflex]==pytest.approx([205.841932763]*4)
    assert [e["angle_deg"] for e in reflex]==pytest.approx([77.079033618]*4)
    assert all(e["cut_side"]=="exterior" for e in reflex)
    assert d["thickness_check"]["status"]=="passed" and d["fabrication_error"] is None
    assert sorted((t["sides"],t["quantity"]) for t in d["templates"])==[(3,4),(4,1),(4,4)]
    triangle=next(t for t in d["templates"] if t["sides"]==3)
    assert any(e["exterior_offset_mm"]>0 for e in triangle["edges"])
    assert not np.allclose(triangle["polygon_mm"],triangle["reference_polygon_mm"])
    assert sorted(round(e["length_mm"],5) for e in triangle["edges"])==sorted([120,round(sqrt(7600),5),round(sqrt(7600),5)])


def test_all_cube_and_zero_depth_preserve_perimeter_vertices():
    base=make_design(Parameters(solid_id="cube"))
    flat=make_design(Parameters(solid_id="cube",preset_id="excavated-cube",apex_offset_mm=0))
    assert flat["faces"]==base["faces"] and flat["vertices"]==base["vertices"]
    assert flat["phase2"] is False
    d=make_design(Parameters(solid_id="cube",preset_id="excavated-cube",apex_offset_mm=20))
    assert (len(d["vertices"]),d["total_edges"],d["total_faces"])==(14,36,24)
    assert np.array(d["vertices"][:8])==pytest.approx(np.array(base["vertices"]))
    assert [(t["sides"],t["quantity"]) for t in d["templates"]]==[(3,24)]
    assert Counter(e["edge_kind"] for e in d["edges"])=={"convex":12,"concave":24}
    assert d["fabrication_error"] is None
    with pytest.raises(ValueError,match="center"):
        make_design(Parameters(solid_id="cube",preset_id="excavated-cube",apex_offset_mm=61))


def test_selective_rhombicuboctahedron_preserves_untouched_faces_and_ids():
    source=topology("rhombicuboctahedron")
    index=next(i for i,f in enumerate(source["faces"]) if len(f)==4)
    face_id=f"F{index+1:03d}"
    d=make_design(Parameters(face_transforms={face_id:{"mode":"inward","offset_mm":12}}))
    assert d["total_faces"]==29
    untouched={r["source_face_id"]:d["faces"][i] for i,r in enumerate(d["face_records"]) if r["subface_index"] is None}
    for i,face in enumerate(source["faces"]):
        if i!=index:
            assert untouched[f"F{i+1:03d}"]==face
    assert [r["id"] for r in d["face_records"] if r["source_face_id"]==face_id]==[f"{face_id}.{i}" for i in range(1,5)]
    assert sum(t["quantity"] for t in d["templates"])==29
    # Four-face corners in this base need additional corner relief even before
    # the edit. Preview the valid surface but do not export intersecting slabs.
    assert "overlap" in d["fabrication_error"]
    with pytest.raises(ValueError,match="overlap"):
        pdf_bytes(d)


def test_rigid_transform_and_scale_invariance_of_signed_mesh():
    d=excavated()
    vertices=np.array(d["vertices"])
    rotation=np.array([[cos(.7),-sin(.7),0],[sin(.7),cos(.7),0],[0,0,1]])
    transformed=analyze_mesh(vertices@rotation.T+[17,-31,24],d["faces"])
    scaled=analyze_mesh(vertices*2,d["faces"])
    for original,a,b in zip(d["edges"],transformed["edges"],scaled["edges"]):
        assert a["angle_deg"]==pytest.approx(original["angle_deg"])
        assert b["dihedral_deg"]==pytest.approx(original["dihedral_deg"])
        assert a["cut_side"]==b["cut_side"]==original["cut_side"]
        assert b["length_mm"]==pytest.approx(original["length_mm"]*2)


def test_shrinkage_applies_to_depth_once_and_not_working_thickness():
    a=excavated()
    b=excavated(shrinkage_percent=20)
    assert np.array(b["vertices"])==pytest.approx(np.array(a["vertices"])/.8)
    for ta,tb in zip(a["templates"],b["templates"]):
        assert [e["signed_inset_mm"] for e in ta["edges"]]==pytest.approx([e["signed_inset_mm"] for e in tb["edges"]])


def test_reflex_and_convex_coupon_halfspaces():
    assert signed_inset(120,6)==pytest.approx(sqrt(12))
    assert signed_inset(240,6)==pytest.approx(-sqrt(12))
    square=[[0,0],[100,0],[100,100],[0,100]]
    expanded=offset_polygon(square,[-sqrt(12),0,0,0])
    assert expanded[0][1]==pytest.approx(-sqrt(12))
    assert expanded[1][1]==pytest.approx(-sqrt(12))
    # Two perpendicular slabs from a cube meet at their miter without positive
    # volume overlap; translating one inward produces an overlap to reject.
    cell_a=slab_cell(np.array([[0,0,0],[100,0,0],[100,100,0],[0,100,0]]),np.array([0,0,1.]),[90]*4,6)
    cell_b={**cell_a,"vertices":cell_a["vertices"]+[0,0,12],"low":cell_a["low"]+[0,0,12],"high":cell_a["high"]+[0,0,12]}
    assert not cells_overlap(cell_a,cell_b,1e-6)
    assert cells_overlap(cell_a,cell_a,1e-6)


@pytest.mark.parametrize("delta",[120,240])
def test_two_panel_miters_have_coincident_inner_edges_without_overlap(delta):
    alpha=radians(180-delta)
    n1=np.array([0.,0,1]);n2=np.array([0.,-sin(alpha),cos(alpha)])
    face1=np.array([[-35,0,0],[35,0,0],[35,40,0],[-35,40,0.]])
    across=np.array([0.,-cos(alpha),-sin(alpha)])
    face2=np.array([[35,0,0],[-35,0,0],np.array([-35,0,0])+40*across,np.array([35,0,0])+40*across])
    a=slab_cell(face1,n1,[delta,180,180,180],6)
    b=slab_cell(face2,n2,[delta,180,180,180],6)
    assert not cells_overlap(a,b,1e-7)
    inset=signed_inset(delta,6)
    for x in [-35,35]:
        inner=np.array([x,inset,-6])
        assert any(np.linalg.norm(v-inner)<1e-6 for v in a["vertices"])
        assert any(np.linalg.norm(v-inner)<1e-6 for v in b["vertices"])


def test_winding_degeneracy_and_incident_surface_overlap_rejected():
    mesh=topology("cube")
    with pytest.raises(ValueError,match="inward oriented"):
        analyze_mesh(mesh["vertices"],[list(reversed(f)) for f in mesh["faces"]])
    bad=[f[:] for f in mesh["faces"]];bad[0].reverse()
    with pytest.raises(ValueError,match="winding"):
        analyze_mesh(mesh["vertices"],bad)
    a=np.array([[0,0,0],[2,0,0],[0,2,0.]])
    b=np.array([[0,0,0],[1,0,0],[0,1,0.]])
    assert _triangle_contact(a,b,np.array([[0.,0,0]]),1e-8)
    neighbor=np.array([[0,0,0],[2,0,0],[1,-1,0.]])
    assert not _triangle_contact(a,neighbor,np.array([[0.,0,0],[2,0,0]]),1e-8)


def test_closed_manifold_surface_intersection_rejected():
    # This octahedral connectivity is closed and consistently wound, but moving
    # the upper apex through the equator makes nonadjacent triangles cross.
    vertices=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[2,.2,-.5],[0,0,-1]]
    ring=[0,2,1,3]
    faces=[[ring[i],ring[(i+1)%4],4] for i in range(4)]
    faces += [[ring[(i+1)%4],ring[i],5] for i in range(4)]
    with pytest.raises(ValueError,match="Surface intersection"):
        analyze_mesh(vertices,faces)


@pytest.mark.parametrize("preset",PRESETS,ids=lambda p:p["id"])
def test_presets_export_vector_plans_with_cut_sides_assembly_and_scale(preset):
    d=make_design(Parameters(solid_id=preset["solid_id"],preset_id=preset["id"],apex_offset_mm=8,page_format="a3"))
    assert d["fabrication_error"] is None
    doc=pymupdf.open(stream=pdf_bytes(d),filetype="pdf")
    assert len(doc)==page_plan(d)["page_count"]
    assert "EXPERIMENTAL" in doc[0].get_text()
    assert "ASSEMBLY" in doc[-1].get_text()
    for t in d["templates"]:
        assert len(t["instances"])==t["quantity"]
        assert b"CALIBRATION PLAN" in svg_bytes(d,t["id"])
        for label in edge_annotations(t,2):
            assert " IN" in label["text"] or " OUT" in label["text"]
    for page in doc:
        assert not page.get_images()
        for word in page.get_text("words"):
            assert 0<=word[0]<=word[2]<=page.rect.width+.1
            assert 0<=word[1]<=word[3]<=page.rect.height+.1


def test_paired_edges_resolve_to_exactly_two_instance_labels():
    d=excavated()
    joint_map={e["id"]:[] for e in d["edges"]}
    for t in d["templates"]:
        for instance in t["instances"]:
            for edge in instance["edges"]:
                joint_map[edge["joint_id"]].append((instance["face_index"],t["edges"][int(edge["label"][1:])-1]))
    for edge in d["edges"]:
        pairs=joint_map[edge["id"]]
        assert sorted(fi for fi,_ in pairs)==edge["faces"]
        for _,panel_edge in pairs:
            assert panel_edge["angle_deg"]==pytest.approx(edge["angle_deg"])
            assert panel_edge["length_mm"]==pytest.approx(edge["length_mm"])
            assert panel_edge["cut_side"]==edge["cut_side"]


@pytest.mark.parametrize('paper',['letter','a4','a3'])
def test_printed_concave_reference_edge_and_calibration_are_actual_size(paper):
    d=excavated(page_format=paper)
    doc=pymupdf.open(stream=pdf_bytes(d),filetype='pdf')
    paths=[p for p in doc[1].get_drawings() if '6 2 1 2' in p['dashes']]
    assert len(paths)==1
    lengths=[abs(item[2]-item[1]) for item in paths[0]['items'] if item[0]=='l']
    assert sorted(lengths)==pytest.approx(sorted([120*mm,sqrt(7600)*mm,sqrt(7600)*mm]),abs=.002)
    coupon=pymupdf.open(stream=calibration_pdf_bytes(Parameters(page_format=paper)),filetype='pdf')
    assert len(coupon)==1
    text=coupon[0].get_text()
    assert '+3.4641 mm' in text and '-3.4641 mm' in text
    assert '120 deg' in text and '240 deg' in text
    for page in list(doc)+list(coupon):
        for word in page.get_text('words'):
            assert 0<=word[0]<=word[2]<=page.rect.width+.1
            assert 0<=word[1]<=word[3]<=page.rect.height+.1
