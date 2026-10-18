from fastapi.testclient import TestClient

from solids.api import app

client = TestClient(app)


def test_guide_short_url_redirects_permanently_to_canonical_directory():
    response=client.get('/guide/slab-polyhedra',follow_redirects=False)
    assert response.status_code==308
    assert response.headers['location']=='/guide/slab-polyhedra/'


def test_complete_design_to_pdf_and_svg_workflow():
    assert client.get("/api/health").json() == {"status": "ok"}
    assert len(client.get("/api/solids").json()) == 18
    response = client.post("/api/design", json={})
    assert response.status_code == 200
    design = response.json()
    assert design["layout"]["page_count"] == 4
    assert design["export_error"] is None
    assert design["templates"][2]["quantity"] == 12
    pdf = client.post("/api/export/pdf", json={})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["cache-control"] == "no-store"
    assert "attachment" in pdf.headers["content-disposition"]
    svg = client.post("/api/export/svg/C", json={})
    assert svg.status_code == 200 and b"MAKE 12" in svg.content


def test_bad_parameters_and_unknown_resources_are_friendly_errors():
    for data in ({"solid_id": "missing"}, {"shrinkage_percent": 100}, {"thickness_mm": -6}, {"page_format": "no"}):
        assert client.post("/api/design", json=data).status_code == 422
    assert client.post("/api/export/svg/Z", json={}).status_code == 422
    assert client.post("/api/export/pdf", json={"solid_id": "cube", "edge_length_mm": 10, "thickness_mm": 6}).status_code == 422


def test_unbuildable_panel_still_previews_with_export_disabled():
    response = client.post("/api/design", json={"solid_id": "cube", "edge_length_mm": 10, "thickness_mm": 6})
    assert response.status_code == 200
    assert "consume" in response.json()["export_error"]


def test_phase2_catalog_presets_and_export_workflow():
    assert len(client.get('/api/presets').json())==7
    data={"solid_id":"cube","preset_id":"excavated-cube-single","apex_offset_mm":20}
    response=client.post('/api/design',json=data)
    assert response.status_code==200
    design=response.json()
    assert design['geometry_version']==2 and design['phase2']
    assert design['total_faces']==9 and design['layout']['assembly_pages']==1
    assert design['export_error'] is None
    assert any(e['cut_side']=='exterior' for e in design['edges'])
    assert client.post('/api/export/pdf',json=data).status_code==200
    svg=client.post('/api/export/svg/A',json=data)
    assert svg.status_code==200 and b'CALIBRATION PLAN' in svg.content and b'OUT' in svg.content
    coupon=client.post('/api/export/calibration',json=data)
    assert coupon.status_code==200 and coupon.content.startswith(b'%PDF')
    # Legacy saved parameter objects remain valid without Phase 2 fields.
    assert client.post('/api/design',json={'solid_id':'cube','edge_length_mm':120}).json()['phase2'] is False


def test_phase2_invalid_offsets_block_export_but_overlaps_are_printable():
    too_deep={'solid_id':'cube','preset_id':'excavated-cube','apex_offset_mm':61}
    assert client.post('/api/design',json=too_deep).status_code==422
    invalid_face={'solid_id':'cube','face_transforms':{'F999':{'mode':'inward','offset_mm':8}}}
    assert client.post('/api/design',json=invalid_face).status_code==422
    overlap={'face_transforms':{'F009':{'mode':'inward','offset_mm':12}}}
    preview=client.post('/api/design',json=overlap)
    assert preview.status_code==200
    design=preview.json()
    assert design['export_error'] is None
    assert design['thickness_check']['status']=='overlap'
    assert design['layout']['collision_pages']>0
    assert any(t['collision_annotations'] for t in design['templates'])
    assert client.post('/api/export/pdf',json=overlap).status_code==200
    marked=next(t for t in design['templates'] if t['collision_regions'])
    svg=client.post('/api/export/svg/'+marked['id'],json=overlap)
    assert svg.status_code==200 and b'hatch' in svg.content and b'OVERLAP' in svg.content


def test_flattened_stellated_dodecahedron_keeps_40_clear_triangles_unmarked():
    parameters={'solid_id':'dodecahedron','preset_id':'stellated-dodecahedron','apex_offset_mm':20,'face_transforms':{'F001':{'mode':'flat','offset_mm':0}}}
    response=client.post('/api/design',json=parameters)
    assert response.status_code==200
    d=response.json()
    assert d['export_error'] is None
    clear=next(t for t in d['templates'] if t['quantity']==40)
    assert not clear['collision_regions'] and not clear['collision_annotations'] and not clear['collision_warnings']
    marked=[t for t in d['templates'] if t['sides']==3 and t['collision_regions']]
    assert [t['quantity'] for t in marked]==[5,5]
    assert client.post('/api/export/pdf',json=parameters).status_code==200
