from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from math import cos, radians, sin, sqrt

import numpy as np
import pymupdf
import pytest
from reportlab.lib.units import mm

from solids.fabrication import offset_polygon, signed_inset, slab_cell, cells_overlap, intersection_vertices
from solids.geometry import Parameters, make_design, topology, collision_annotations
from solids.mesh import analyze_mesh, signed_joint, _triangle_contact
from solids.printing import pdf_bytes, svg_bytes, page_plan, edge_annotations, center_annotations, collision_vertex_annotations, calibration_pdf_bytes
from solids.transforms import PRESETS


def test_default_exports_match_reviewed_pdf_baseline():
    baseline=json.loads((Path(__file__).parent/'fixtures'/'phase1_pdf_sha256.json').read_text())
    for solid_id,expected in baseline.items():
        output=pdf_bytes(make_design(Parameters(solid_id=solid_id)))
        assert hashlib.sha256(output).hexdigest()==expected,solid_id


def test_assembly_views_and_footer_preserve_original_template_vectors():
    baseline=json.loads((Path(__file__).parent/'fixtures'/'phase1_template_paths_sha256.json').read_text())
    for solid_id,expected in baseline.items():
        doc=pymupdf.open(stream=pdf_bytes(make_design(Parameters(solid_id=solid_id))),filetype='pdf')
        actual=[hashlib.sha256(repr(page.get_drawings()).encode()).hexdigest() for page in list(doc)[1:]]
        assert actual==expected,solid_id


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
    # Four-face corners require manual relief, with printable locations.
    assert d["fabrication_error"] is None
    assert d["thickness_check"]["status"]=="overlap"
    assert len(d["thickness_check"]["collisions"])==24
    assert pdf_bytes(d).startswith(b"%PDF")


@pytest.mark.parametrize('solid,expected_collisions',[('cube',8),('octahedron',12),('dodecahedron',10)])
def test_stellated_flattened_face_separates_clear_and_marked_copies(solid,expected_collisions):
    parameters={'solid_id':solid,'preset_id':f'stellated-{solid}','apex_offset_mm':20}
    symmetric=make_design(Parameters(**parameters))
    assert symmetric['thickness_check']['status']=='passed'
    assert len(symmetric['templates'])==1
    d=make_design(Parameters(**parameters,face_transforms={'F001':{'mode':'flat'}}))
    assert len(d['thickness_check']['collisions'])==expected_collisions
    assert sum(t['quantity'] for t in d['templates'])==d['total_faces']
    copies={}
    for t in d['templates']:
        assert len(t['instances'])==len(t['face_ids'])==t['quantity']
        affected={w['instance_id'] for w in t['collision_warnings']}
        assert affected==({i['id'] for i in t['instances']} if t['collision_regions'] else set())
        for instance in t['instances']:
            assert instance['id'] not in copies
            copies[instance['id']]=t['id']
            assert instance['template_id']==t['id']
            assert all(instance['id'] in r['instance_ids'] for r in t['collision_regions'])
    # Every assembly edge still maps to the correct physical segment after
    # rotations used to align a symmetric pattern's collision marks.
    joints={e['id']:e for e in d['edges']}
    vertices=np.array(d['vertices'])
    for t in d['templates']:
        for instance in t['instances']:
            ids=instance['vertex_ids']
            for i,edge in enumerate(instance['edges']):
                joint=joints[edge['joint_id']]
                assert set(joint['vertices'])=={ids[i],ids[(i+1)%len(ids)]}
                assert t['edges'][i]['angle_deg']==pytest.approx(joint['angle_deg'])
                assert t['edges'][i]['length_mm']==pytest.approx(np.linalg.norm(vertices[ids[i]]-vertices[ids[(i+1)%len(ids)]]))
    for collision in d['thickness_check']['collisions']:
        for panel in collision['panels']:
            assert panel['template_id']==copies[panel['instance_id']]
    if solid=='dodecahedron':
        assert [(t['quantity'],bool(t['collision_regions'])) for t in d['templates']]==[(5,False),(40,False),(5,True),(5,True),(1,True)]
        # The two base-corner cases are mirrored, not interchangeable rotations.
        assert d['templates'][2]['collision_vertices']!=d['templates'][3]['collision_vertices']
        doc=pymupdf.open(stream=pdf_bytes(d),filetype='pdf')
        for page,sheet in zip(list(doc)[1:],page_plan(d)['template_pages']):
            t=next(t for t in d['templates'] if t['id']==sheet['template_id'])
            text=page.get_text()
            assert f"MAKE {t['quantity']}" in text
            assert ('OVERLAP WARNING' in text)==bool(t['collision_regions'])
            assert (b'OVERLAP WARNING' in svg_bytes(d,t['id']))==bool(t['collision_regions'])


def test_assembled_bounds_follow_shrinkage_and_face_edits():
    for shrinkage in (0,20):
        d=make_design(Parameters(solid_id="cube",shrinkage_percent=shrinkage))
        assert d["dimensions"]["axes"]==["width","depth","height"]
        assert d["dimensions"]["fired_mm"]==pytest.approx([120]*3)
        assert d["dimensions"]["working_mm"]==pytest.approx([120/(1-shrinkage/100)]*3)
    assert excavated()["dimensions"]["fired_mm"]==pytest.approx([120]*3)
    outward=make_design(Parameters(solid_id="cube",face_transforms={f"F{i:03d}":{"mode":"outward","offset_mm":20} for i in range(1,7)}))
    assert outward["dimensions"]["fired_mm"]==pytest.approx([160]*3)


def test_intersection_region_finds_crossing_cells_without_contained_vertices():
    # Crossing narrow rectangular slabs have eight new intersection vertices.
    a=slab_cell(np.array([[-10,-1,0],[10,-1,0],[10,1,0],[-10,1,0.]]),np.array([0.,0,1]),[180]*4,2)
    b=slab_cell(np.array([[-1,-10,0],[1,-10,0],[1,10,0],[-1,10,0.]]),np.array([0.,0,1]),[180]*4,2)
    assert cells_overlap(a,b,1e-6)
    for source,other in ((a,b),(b,a)):
        assert not np.any(np.all(source["vertices"] @ other["planes"][:,:3].T+other["planes"][:,3]<=1e-6,axis=1))
    points=intersection_vertices(a,b,1e-6)
    assert len(points)==8
    assert np.ptp(points,axis=0)==pytest.approx([2,2,2])


@pytest.mark.parametrize('paper',['letter','a4','a3'])
@pytest.mark.parametrize('edge',[120,400])
def test_overlap_prints_mark_every_affected_template_and_reference(paper,edge):
    d=make_design(Parameters(face_transforms={'F009':{'mode':'inward','offset_mm':12}},page_format=paper,edge_length_mm=edge))
    plan=page_plan(d)
    doc=pymupdf.open(stream=pdf_bytes(d),filetype='pdf')
    assert len(doc)==plan['page_count']
    reference=''.join(p.get_text() for p in list(doc)[-plan['collision_pages']:])
    lookup={t['id']:t for t in d['templates']}
    for collision in d['thickness_check']['collisions']:
        assert collision['id'] in reference
        assert len(collision['panels'])==2
        for panel in collision['panels']:
            assert panel['instance_id'] in reference
            template=lookup[panel['template_id']]
            instance=next(i for i in template['instances'] if i['id']==panel['instance_id'])
            assert panel['corner_labels']==[f'V{i+1}' for i,v in enumerate(instance['vertex_ids']) if v in collision['shared_vertices']]
            assert any(collision['id'] in region['collision_ids'] and instance['id'] in region['instance_ids'] for region in template['collision_regions'])
    for page,sheet in zip(list(doc)[1:],plan['template_pages']):
        template=lookup[sheet['template_id']]
        if template['collision_regions']:
            assert 'OVERLAP' in page.get_text()
            assert b'pattern' in svg_bytes(d,template['id'])
    for page in doc:
        for word in page.get_text('words'):
            assert 0<=word[0]<=word[2]<=page.rect.width+.1
            assert 0<=word[1]<=word[3]<=page.rect.height+.1


def test_overlap_volumes_are_real_and_template_projection_is_rigid_invariant():
    d=make_design(Parameters(face_transforms={'F003':{'mode':'inward','offset_mm':12}}))
    vertices=np.array(d['vertices'])
    mesh=analyze_mesh(vertices,d['faces'])
    edge_lookup={tuple(e['vertices']):e for e in mesh['edges']}
    cells=[]
    for face,normal in zip(mesh['faces'],mesh['normals']):
        deltas=[edge_lookup[tuple(sorted((a,b)))]['dihedral_deg'] for a,b in zip(face,face[1:]+face[:1])]
        cells.append(slab_cell(vertices[face],normal,deltas,6))
    for collision in d['thickness_check']['collisions']:
        region=np.array(collision['region_mm'])
        for fi in collision['faces']:
            planes=cells[fi]['planes']
            assert np.max(region@planes[:,:3].T+planes[:,3])<1e-5
    rotation=np.array([[cos(.7),0,-sin(.7)],[0,1,0],[sin(.7),0,cos(.7)]])
    translation=np.array([17,-31,24])
    transformed=analyze_mesh(vertices@rotation.T+translation,d['faces'])
    collisions=deepcopy(d['thickness_check']['collisions'])
    for collision in collisions:
        collision['region_mm']=(np.array(collision['region_mm'])@rotation.T+translation).tolist()
    templates=deepcopy(d['templates'])
    collision_annotations(transformed,templates,collisions)
    for before,after in zip(d['templates'],templates):
        assert before['collision_warnings']==after['collision_warnings']
        for a,b in zip(before['collision_regions'],after['collision_regions']):
            assert np.array(a['polygon_mm'])==pytest.approx(np.array(b['polygon_mm']))
        labels=edge_annotations(before,2);labels+=center_annotations(before,labels)
        assert {l['text'] for l in collision_vertex_annotations(before,labels)}=={f'V{i+1}' for i in before['collision_vertices']}


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
