from fastapi.testclient import TestClient

from solids.api import app

client = TestClient(app)


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
