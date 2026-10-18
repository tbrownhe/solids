from io import BytesIO
from math import hypot
from xml.etree import ElementTree

import numpy as np
import pymupdf
import pytest
from reportlab.lib.units import mm

from solids.geometry import Parameters, make_design
from solids.printing import BOTTOM, MARGIN, OVERLAP, PAPER, TOP, SITE_LABEL, SITE_URL, _inside, _overlap, calibration_pdf_bytes, edge_annotations, page_plan, pdf_bytes, svg_bytes
from solids.registry import SOLIDS


@pytest.mark.parametrize("solid_id", SOLIDS)
def test_all_solids_default_pdf_is_vector_and_text_stays_on_page(solid_id):
    design = make_design(Parameters(solid_id=solid_id))
    data = pdf_bytes(design)
    doc = pymupdf.open(stream=data, filetype="pdf")
    assert len(doc) == page_plan(design)["page_count"]
    assert "FINISHED FORM / EXTERIOR VIEWS" in doc[0].get_text()
    assert "OPPOSITE VIEW" in doc[0].get_text()
    assert "Views not to scale" in doc[0].get_text()
    for page in doc:
        assert not page.get_images()
        assert page.get_drawings()
        assert "PRINT ACTUAL SIZE" in page.get_text()
        assert "EXTERIOR FACE DOWN" in page.get_text()
        assert "INTERIOR FACE UP" in page.get_text()
        assert "underside" not in page.get_text()
        assert SITE_LABEL in page.get_text()
        assert any(link.get("uri") == SITE_URL for link in page.get_links())
        for word in page.get_text("words"):
            rect = pymupdf.Rect(word[:4])
            assert rect.x0 >= 0 and rect.y0 >= 0
            assert rect.x1 <= page.rect.width + .1 and rect.y1 <= page.rect.height + .1


@pytest.mark.parametrize("paper", PAPER)
def test_physical_paper_and_exact_acceptance_cut_outline(paper):
    design = make_design(Parameters(page_format=paper))
    data = pdf_bytes(design)
    assert data == pdf_bytes(design), "Export should be byte-deterministic"
    doc = pymupdf.open(stream=data, filetype="pdf")
    width, height = PAPER[paper]
    assert doc[0].rect.width == pytest.approx(width * mm, abs=.001)
    assert doc[0].rect.height == pytest.approx(height * mm, abs=.001)
    assert len(doc) == 4
    for page, template in zip(list(doc)[1:], design["templates"]):
        paths = [d for d in page.get_drawings() if abs(d["width"] - .6) < .001]
        assert len(paths) == 1
        path = paths[0]
        expected = np.array(template["polygon_mm"]).max(axis=0) * mm
        assert path["rect"].width == pytest.approx(expected[0], abs=.002)
        assert path["rect"].height == pytest.approx(expected[1], abs=.002)
        assert path["rect"].x0 >= MARGIN * mm - .01
        assert path["rect"].x1 <= (width - MARGIN) * mm + .01
        assert path["rect"].y0 >= TOP * mm - .01
        assert path["rect"].y1 <= (height - BOTTOM) * mm + .01
        assert page.get_text().count("°") == template["sides"]
        assert any(path["rect"].contains(rect) for rect in page.search_for(f"MAKE {template['quantity']}"))


def test_calibration_ruler_and_one_inch_square_are_exact_vectors():
    doc = pymupdf.open(stream=pdf_bytes(make_design(Parameters())), filetype="pdf")
    cover = doc[0]
    squares = [d for d in cover.get_drawings() if abs(d["rect"].width - 25.4 * mm) < .01 and abs(d["rect"].height - 25.4 * mm) < .01]
    assert len(squares) == 1
    for page in doc:
        rulers = [d for d in page.get_drawings() if abs(d["rect"].width - 100 * mm) < .01 and d["rect"].height < .001]
        assert len(rulers) == 1


@pytest.mark.parametrize("solid_id", SOLIDS)
@pytest.mark.parametrize("precision", [0, 2, 4])
@pytest.mark.parametrize("thickness", [6, 12])
def test_rotated_edge_labels_are_inside_outlines_and_do_not_collide(solid_id, precision, thickness):
    design = make_design(Parameters(solid_id=solid_id, angle_precision=precision, thickness_mm=thickness))
    for template in design["templates"]:
        labels = edge_annotations(template, precision)
        for i, label in enumerate(labels):
            assert all(_inside(p, template["polygon_mm"], .6) for p in label["corners"])
            assert all(_inside(p, template["inset_polygon_mm"], 1.5) for p in label["corners"])
            for other in labels[i + 1:]:
                assert not _overlap(label["corners"], other["corners"])


def test_tiling_preserves_scale_and_shared_registration_coordinates():
    design = make_design(Parameters(solid_id="cube", edge_length_mm=320))
    plan = page_plan(design)
    assert plan["tiled"]
    pages = plan["template_pages"]
    assert len(pages) == 4
    width, height = PAPER["letter"]
    horizontal, vertical = width - 2 * MARGIN - OVERLAP, height - TOP - BOTTOM - OVERLAP
    assert pages[0]["offset_x"] - pages[1]["offset_x"] == pytest.approx(horizontal)
    assert pages[0]["offset_y"] - pages[2]["offset_y"] == pytest.approx(vertical)
    doc = pymupdf.open(stream=pdf_bytes(design), filetype="pdf")
    for page in list(doc)[1:]:
        outline = next(d for d in page.get_drawings() if abs(d["width"] - .6) < .001)
        assert outline["rect"].width == pytest.approx(320 * mm, abs=.002)
        assert outline["rect"].height == pytest.approx(320 * mm, abs=.002)
        assert "row" in page.get_text()
        assert sum(abs(d["width"] - .35) < .001 for d in page.get_drawings()) >= 8


def test_svg_physical_coordinates_preserve_edge_and_include_orientation():
    design = make_design(Parameters(shrinkage_percent=10))
    root = ElementTree.fromstring(svg_bytes(design, "B"))
    assert root.attrib["width"].endswith("mm")
    assert root.attrib["height"].endswith("mm")
    polygon = root.find(".//{http://www.w3.org/2000/svg}polygon")
    points = [tuple(map(float, p.split(','))) for p in polygon.attrib["points"].split()]
    for a, b in zip(points, points[1:] + points[:1]):
        assert hypot(b[0] - a[0], b[1] - a[1]) == pytest.approx(120 / .9, abs=1e-6)
    text = " ".join(root.itertext())
    assert "MAKE 6" in text and "EXTERIOR" in text and "INTERIOR" in text
    assert any(t.text == "MAKE 6" and "transform" in t.attrib
               for t in root.findall("{http://www.w3.org/2000/svg}text"))


def test_impossible_prints_are_rejected_instead_of_silently_scaled():
    with pytest.raises(ValueError, match="consume"):
        pdf_bytes(make_design(Parameters(solid_id="cube", edge_length_mm=10, thickness_mm=6)))
    with pytest.raises(ValueError, match="120 sheets"):
        page_plan(make_design(Parameters(edge_length_mm=2000)))


def test_small_svg_keeps_metadata_in_the_physical_document():
    from reportlab.pdfbase.pdfmetrics import stringWidth
    design = make_design(Parameters(solid_id="cube", edge_length_mm=30, thickness_mm=1))
    root = ElementTree.fromstring(svg_bytes(design, "A"))
    x, y, width, height = map(float, root.attrib["viewBox"].split())
    for text in root.findall("{http://www.w3.org/2000/svg}text"):
        if "x" in text.attrib:
            assert float(text.attrib["x"]) + stringWidth(text.text, "Helvetica", 2.5 * mm) / mm < x + width
            assert float(text.attrib["y"]) < y + height


def test_calibration_coupons_and_svg_include_website():
    doc=pymupdf.open(stream=calibration_pdf_bytes(Parameters()),filetype="pdf")
    assert SITE_LABEL in doc[0].get_text()
    assert any(link.get("uri")==SITE_URL for link in doc[0].get_links())
    assert SITE_LABEL.encode() in svg_bytes(make_design(Parameters()),"A")


@pytest.mark.parametrize("paper",PAPER)
def test_overlap_cover_marks_actual_affected_faces_without_extra_sheets(paper):
    design=make_design(Parameters(solid_id="dodecahedron",preset_id="stellated-dodecahedron",
                                 face_transforms={"F001":{"mode":"flat"}},page_format=paper))
    doc=pymupdf.open(stream=pdf_bytes(design),filetype="pdf")
    cover=doc[0]
    assert "Pale red / dots" in cover.get_text()
    assert "overlaps do not rule out assembly" in " ".join(cover.get_text().split())
    assert "F001" in cover.get_text()
    assert any(d["fill"] and d["fill"][0]>.9 and d["fill"][1]<.9 for d in cover.get_drawings())
    assert len(doc)==page_plan(design)["page_count"]
    for page in doc:
        assert SITE_LABEL in page.get_text()
