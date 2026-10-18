"""Actual-size vector PDF and SVG; deterministic page planning in millimetres."""
from io import BytesIO
from math import atan2, ceil, cos, degrees, hypot, pi, sin
from xml.sax.saxutils import escape

import numpy as np
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

PAPER = {"letter": (215.9, 279.4), "a4": (210, 297), "a3": (297, 420)}
MARGIN, TOP, BOTTOM, OVERLAP = 14.0, 49.0, 39.0, 10.0
INK = HexColor("#25332e")
GRAY = HexColor("#6b716c")
BEVELER_URL = "https://www.etsy.com/listing/4466016418/precision-beveler-pottery-bevel-cutter"


def page_plan(design):
    width, height = PAPER[design["parameters"]["page_format"]]
    usable_w, usable_h = width - 2 * MARGIN, height - TOP - BOTTOM
    pages = []
    for template in design["templates"]:
        points = np.array(template["polygon_mm"])
        w, h = points.max(axis=0)
        cols = max(1, ceil((w - OVERLAP - 1e-7) / (usable_w - OVERLAP)))
        rows = max(1, ceil((h - OVERLAP - 1e-7) / (usable_h - OVERLAP)))
        canvas_w = usable_w + (cols - 1) * (usable_w - OVERLAP)
        canvas_h = usable_h + (rows - 1) * (usable_h - OVERLAP)
        # Centre the complete panel on its sheet or tile grid, never scale it.
        for row in range(rows):
            for col in range(cols):
                pages.append({"template_id": template["id"], "row": row + 1, "col": col + 1,
                              "rows": rows, "cols": cols,
                              "offset_x": MARGIN + (canvas_w - w) / 2 - col * (usable_w - OVERLAP),
                              "offset_y": BOTTOM + (canvas_h - h) / 2 - row * (usable_h - OVERLAP)})
    if len(pages) + 1 > 120:
        raise ValueError("This design needs more than 120 sheets. Reduce edge length or use A3.")
    return {"page_count": len(pages) + 1, "template_pages": pages,
            "paper_width_mm": width, "paper_height_mm": height,
            "overlap_mm": OVERLAP, "tiled": any(p["cols"] * p["rows"] > 1 for p in pages)}


def _inside(point, polygon, margin=0):
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if (dx * (point[1] - a[1]) - dy * (point[0] - a[0])) / hypot(dx, dy) < margin - 1e-6:
            return False
    return True


def _overlap(a, b):
    # Separating axis test on oriented text rectangles.
    for shape in (a, b):
        for p, q in zip(shape, shape[1:] + shape[:1]):
            axis = np.array([q[1] - p[1], p[0] - q[0]])
            aa, bb = np.array(a) @ axis, np.array(b) @ axis
            if max(aa) < min(bb) + 1e-7 or max(bb) < min(aa) + 1e-7:
                return False
    return True


def edge_annotations(template, precision):
    polygon = template["polygon_mm"]
    for font in (7.5, 7, 6, 5, 4.5):
        labels = []
        valid = True
        for i, (a, b) in enumerate(zip(polygon, polygon[1:] + polygon[:1])):
            edge = template["edges"][i]
            text = f"{edge['label']}  {edge['angle_deg']:.{precision}f}\N{DEGREE SIGN}"
            dx, dy = b[0] - a[0], b[1] - a[1]
            angle = atan2(dy, dx)
            if angle > pi / 2 or angle < -pi / 2:
                angle += pi
            u = np.array([cos(angle), sin(angle)])
            v = np.array([-sin(angle), cos(angle)])
            inward = np.array([-dy, dx]) / hypot(dx, dy)
            half_w = stringWidth(text, "Helvetica", font) / mm / 2
            half_h = font / mm * 0.65
            # Keep the full text box beyond the dashed interior boundary. Its
            # position must follow slab thickness and each edge's bevel inset.
            distance = max(4.0, edge["inset_mm"] + 1.5) + half_h
            center = (np.array(a) + np.array(b)) / 2 + inward * distance
            corners = [(center + u * x + v * y).tolist()
                       for x, y in ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h))]
            if not all(_inside(p, polygon, 0.6) for p in corners):
                valid = False
            if template["inset_polygon_mm"] and not all(
                _inside(p, template["inset_polygon_mm"], 1.5) for p in corners
            ):
                valid = False
            if any(_overlap(corners, old["corners"]) for old in labels):
                valid = False
            labels.append({"text": text, "center": center.tolist(), "angle": degrees(angle),
                           "font": font, "corners": corners})
        if valid:
            return labels
    raise ValueError(f"Template {template['id']} is too small for legible bevel labels. Increase the working edge length.")


def center_annotations(template, edge_labels):
    """Keep quantities on the cutout, with room for edge settings."""
    polygon = template["polygon_mm"]
    center = np.array(polygon).mean(axis=0)
    layouts = [
        [(f"MAKE {template['quantity']}", 12, 8, True),
         ("INTERIOR FACE UP", 9, 2, True),
         ("Cut and bevel with EXTERIOR DOWN", 7, -3, False)],
        [(f"MAKE {template['quantity']}", 10, 0, True)],
    ]
    for layout in layouts:
        for scale in (1, .9, .8, .7, .6, .5, .45):
            labels = []
            for text, font, offset, bold in layout:
                font *= scale
                if font < 4.5:
                    break
                position = center + [0, offset * scale]
                half_w = stringWidth(text, "Helvetica-Bold" if bold else "Helvetica", font) / mm / 2
                half_h = font / mm * .65
                corners = [(position + [x, y]).tolist() for x, y in
                           ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h))]
                if not all(_inside(p, polygon, .6) for p in corners):
                    break
                if any(_overlap(corners, other["corners"]) for other in edge_labels + labels):
                    break
                labels.append({"text": text, "font": font, "bold": bold,
                               "center": position.tolist(), "corners": corners})
            if len(labels) == len(layout):
                return labels
    raise ValueError(f"Template {template['id']} is too small for a legible quantity label. Increase the working edge length.")


def _text(c, x, y, text, size=9, bold=False, color=INK):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x * mm, y * mm, text)


def _line(c, x1, y1, x2, y2, width=0.5):
    c.setLineWidth(width)
    c.line(x1 * mm, y1 * mm, x2 * mm, y2 * mm)


def _ruler(c, y=20):
    _text(c, 14, y + 8, "100 mm calibration ruler", 7)
    c.setStrokeColor(INK)
    _line(c, 14, y, 114, y)
    for i in range(0, 101, 10):
        _line(c, 14 + i, y - 1, 14 + i, y + (3 if i % 20 == 0 else 1.5))
        if i % 20 == 0:
            _text(c, 13 + i, y - 5, str(i), 6)


def _header(c, design, title, page, total, width, height):
    _text(c, MARGIN, height - 17, "SOLIDS / CERAMIC TEMPLATE STUDIO", 8, True)
    title_size = min(16, (width - 2 * MARGIN) * mm / max(1, stringWidth(title, "Helvetica-Bold", 1)))
    _text(c, MARGIN, height - 28, title, title_size, True)
    p = design["parameters"]
    _text(c, MARGIN, height - 35,
          f"{p['edge_length_mm']:g} mm fired edge  /  {design['cut_edge_mm']:.2f} mm working edge  /  {p['thickness_mm']:g} mm working slab", 8)
    _text(c, MARGIN, height - 41,
          f"{p['shrinkage_percent']:g}% cut-to-fired shrinkage  /  {p['page_format'].upper()}  /  PRINT ACTUAL SIZE, 100%", 8)
    _text(c, width - 44, 9, f"SHEET {page:02d} / {total:02d}", 7)
    _text(c, MARGIN, 9, "Disable Fit to Page. Verify calibration before cutting.", 7)


def _outline(c, polygon, ox, oy, dashed=False):
    if len(polygon) < 3:
        return
    path = c.beginPath()
    path.moveTo((ox + polygon[0][0]) * mm, (oy + polygon[0][1]) * mm)
    for x, y in polygon[1:]:
        path.lineTo((ox + x) * mm, (oy + y) * mm)
    path.close()
    c.setDash(3, 3) if dashed else c.setDash()
    c.setLineWidth(0.35 if dashed else 0.6)
    c.drawPath(path, stroke=1, fill=0)
    c.setDash()


def _cross(c, x, y):
    _line(c, x - 2, y, x + 2, y, 0.35)
    _line(c, x, y - 2, x, y + 2, 0.35)


def _cover(c, design, plan):
    w, h = plan["paper_width_mm"], plan["paper_height_mm"]
    _header(c, design, design["name"], 1, plan["page_count"], w, h)
    y = h - 58
    _text(c, MARGIN, y, f"{len(design['templates'])} reusable templates / {design['total_faces']} clay panels", 11, True)
    y -= 10
    for template in design["templates"]:
        _text(c, MARGIN, y, f"{template['id']}   {template['sides']}-sided panel   /   MAKE {template['quantity']}", 9, True)
        y -= 6
        pattern = " / ".join(f"{e['angle_deg']:.{design['parameters']['angle_precision']}f} deg" for e in template["edges"])
        _text(c, MARGIN + 6, y, pattern, 8)
        y -= 10
    y -= 2
    for i, line in enumerate([
        "1. Print at Actual Size / 100%. Turn off Fit, Shrink and borderless enlargement.",
        "2. Check the 100 mm ruler and 1-inch square with a physical ruler.",
        "3. Keep EXTERIOR FACE DOWN and INTERIOR FACE UP for cutting AND beveling.",
        "4. Trace and cut the full solid outline, then bevel off the upper waste on that same side.",
        "5. Preserve the exterior edge underneath. Tool angles are from the slab plane; 90 deg = vertical.",
        "6. Dashed lines show the remaining upper INTERIOR face, NOT a cutting outline.",
        "7. Make the quantity shown for each template; test-fit a scrap joint first.",
    ]):
        _text(c, MARGIN, y - i * 7, line, 8)
    y -= 62
    _text(c, MARGIN, y, "JOINT SECTION / PRESERVE THE EXTERIOR EDGE", 8, True)
    # Cutting position: interior up, exterior down. The upper-left wedge is waste.
    x, sy = MARGIN + 8, y - 25
    c.setFillColor(HexColor("#e6e9e3"))
    path = c.beginPath()
    path.moveTo(x * mm, sy * mm)
    path.lineTo((x + 12) * mm, (sy + 16) * mm)
    path.lineTo((x + 65) * mm, (sy + 16) * mm)
    path.lineTo((x + 65) * mm, sy * mm)
    path.close()
    c.drawPath(path, fill=1, stroke=1)
    c.setDash(2, 2)
    _line(c, x, sy, x, sy + 16)
    _line(c, x, sy + 16, x + 12, sy + 16)
    c.setDash()
    _text(c, x + 14, sy + 19, "INTERIOR FACE UP", 7)
    _text(c, x + 6, sy - 5, "EXTERIOR FACE DOWN / keep full edge", 7)
    _text(c, x - 7, sy + 10, "waste", 6)
    _text(c, x + 80, sy + 10, "Inset = thickness / tan(tool angle)", 8)
    _text(c, x + 80, sy + 3, "Diagram schematic; labels are tool settings.", 7)
    y = sy - 16
    if plan["tiled"]:
        _text(c, MARGIN, y, "TILED PANELS: match template ID and row/column; overlap sheets by 10 mm.", 8, True)
        _text(c, MARGIN, y - 6, "Align matching registration crosses in the overlap. Join the outline before tracing.", 8)
        y -= 15
    _text(c, MARGIN, y, "Dimensions assume uniform linear shrinkage. Clay and wire behaviour need a test joint.", 7)
    y -= 6
    tool_note = "Optimized for adjustable wire bevelers such as the Precision Beveler by KellyHoferStudios."
    _text(c, MARGIN, y, tool_note, 7)
    c.linkURL(BEVELER_URL, (MARGIN * mm, (y - 1) * mm,
                          MARGIN * mm + stringWidth(tool_note, "Helvetica", 7), (y + 3) * mm), relative=0)
    for warning in design["warnings"]:
        # Wrap warnings to a physical line length, keeping cover text within margins.
        words, lines, line = warning.split(), [], ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if stringWidth(candidate, "Helvetica", 7) > (w - 2 * MARGIN) * mm:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        for line in lines:
            y -= 5
            _text(c, MARGIN, y, line, 7)
    _ruler(c, 28)
    c.setLineWidth(0.5)
    c.rect((w - MARGIN - 25.4) * mm, 22 * mm, 25.4 * mm, 25.4 * mm)
    _text(c, w - MARGIN - 25.4, 17, "1 inch / 25.4 mm", 7)


def pdf_bytes(design):
    plan = page_plan(design)
    if any(not t["inset_polygon_mm"] for t in design["templates"]):
        raise ValueError("Cannot export: bevels consume an interior face. Reduce thickness or increase edge length.")
    annotations = {t["id"]: edge_annotations(t, design["parameters"]["angle_precision"]) for t in design["templates"]}
    center_labels = {t["id"]: center_annotations(t, annotations[t["id"]]) for t in design["templates"]}
    stream = BytesIO()
    w, h = plan["paper_width_mm"], plan["paper_height_mm"]
    c = Canvas(stream, pagesize=(w * mm, h * mm), invariant=1, pageCompression=1)
    c.setTitle(f"{design['name']} - ceramic panel templates")
    c.setAuthor("Solids Studio")
    _cover(c, design, plan)
    c.showPage()
    for page_number, page in enumerate(plan["template_pages"], start=2):
        template = next(t for t in design["templates"] if t["id"] == page["template_id"])
        tiled = page["cols"] * page["rows"] > 1
        suffix = f" / row {page['row']}, col {page['col']} of {page['rows']} x {page['cols']}" if tiled else ""
        title = f"{template['id']} / {template['sides']}-sided panel / MAKE {template['quantity']}" + suffix
        _header(c, design, title, page_number, plan["page_count"], w, h)
        ox, oy = page["offset_x"], page["offset_y"]
        c.saveState()
        clip = c.beginPath()
        clip.rect(MARGIN * mm, BOTTOM * mm, (w - 2 * MARGIN) * mm, (h - TOP - BOTTOM) * mm)
        c.clipPath(clip, stroke=0, fill=0)
        c.setStrokeColor(INK)
        _outline(c, template["polygon_mm"], ox, oy)
        c.setStrokeColor(GRAY)
        _outline(c, template["inset_polygon_mm"], ox, oy, dashed=True)
        for label in annotations[template["id"]]:
            c.saveState()
            c.translate((ox + label["center"][0]) * mm, (oy + label["center"][1]) * mm)
            c.rotate(label["angle"])
            c.setFont("Helvetica", label["font"])
            c.setFillColor(INK)
            c.drawCentredString(0, -label["font"] * 0.30, label["text"])
            c.restoreState()
        polygon = np.array(template["polygon_mm"])
        for label in center_labels[template["id"]]:
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold" if label["bold"] else "Helvetica", label["font"])
            c.drawCentredString((ox + label["center"][0]) * mm,
                               (oy + label["center"][1]) * mm - label["font"] * .30, label["text"])
        # A global lattice puts identical crosses in adjacent overlap windows.
        # Black crosses are separate from the uninterrupted cut outline.
        if tiled:
            pw, ph = w - 2 * MARGIN, h - TOP - BOTTOM
            grid_w, grid_h = pw + (page["cols"] - 1) * (pw - OVERLAP), ph + (page["rows"] - 1) * (ph - OVERLAP)
            panel_w, panel_h = polygon.max(axis=0)
            gx, gy = ox - (grid_w - panel_w) / 2, oy - (grid_h - panel_h) / 2
            xs = [5] + [i * (pw - OVERLAP) + 5 for i in range(1, page["cols"])] + [grid_w - 5]
            ys = [5] + [i * (ph - OVERLAP) + 5 for i in range(1, page["rows"])] + [grid_h - 5]
            c.setStrokeColor(GRAY)
            for x in xs:
                for y in ys:
                    _cross(c, gx + x, gy + y)
        c.restoreState()
        _text(c, MARGIN, 34, "Cut + bevel: EXTERIOR FACE DOWN / INTERIOR FACE UP. Solid = full outline; dashed = interior inset.", 7)
        _ruler(c)
        c.showPage()
    c.save()
    return stream.getvalue()


def svg_bytes(design, template_id):
    template = next((t for t in design["templates"] if t["id"] == template_id), None)
    if template is None:
        raise ValueError("Unknown template ID.")
    if not template["inset_polygon_mm"]:
        raise ValueError("Bevels consume the interior face. Reduce thickness or increase edge length.")
    points = template["polygon_mm"]
    w, h = np.array(points).max(axis=0)
    labels = edge_annotations(template, design["parameters"]["angle_precision"])
    center_labels = center_annotations(template, labels)
    polygon = lambda p: " ".join(f"{x:.8f},{h-y:.8f}" for x, y in p)
    metadata = [f'{template_id}: MAKE {template["quantity"]} / INTERIOR FACE UP / EXTERIOR FACE DOWN',
                f'Working edge {design["cut_edge_mm"]:.2f} mm / slab {design["parameters"]["thickness_mm"]:g} mm / print at 100%',
                'Keep EXTERIOR FACE DOWN for cutting AND beveling. Remove upper waste.',
                'Solid = full exterior footprint; dashed = remaining upper interior face.',
                'Angles from slab plane: 90 deg = perpendicular; 0 deg = parallel']
    # Keep metadata legible even when the physical panel is very small. Widen
    # the document, preserving one viewBox unit per mm and the cut outline.
    document_width = max(w + 20, max(stringWidth(line, "Helvetica", 2.5 * mm) / mm for line in metadata) + 20)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{document_width:.8f}mm" height="{h+50:.8f}mm" viewBox="-10 -10 {document_width:.8f} {h+50:.8f}">',
             f'<title>{escape(design["name"])} template {template_id}, make {template["quantity"]}</title>',
             '<g fill="none" stroke="#25332e" stroke-width="0.2">',
             f'<polygon points="{polygon(points)}"/>',
             f'<polygon points="{polygon(template["inset_polygon_mm"])}" stroke-dasharray="1.2 1.2" stroke-width="0.12"/>', '</g>']
    for label in labels:
        x, y = label["center"]
        parts.append(f'<text transform="translate({x:.8f} {h-y:.8f}) rotate({-label["angle"]:.8f})" text-anchor="middle" dominant-baseline="central" font-family="Helvetica,Arial,sans-serif" font-size="{label["font"]/mm:.8f}" fill="#25332e">{escape(label["text"])}</text>')
    for label in center_labels:
        x, y = label["center"]
        parts.append(f'<text transform="translate({x:.8f} {h-y:.8f})" text-anchor="middle" dominant-baseline="central" font-family="Helvetica,Arial,sans-serif" font-size="{label["font"]/mm:.8f}" font-weight="{"bold" if label["bold"] else "normal"}" fill="#25332e">{escape(label["text"])}</text>')
    parts.extend(f'<text x="0" y="{h+8+i*5}" font-family="Helvetica,Arial,sans-serif" font-size="2.5">{escape(line)}</text>' for i, line in enumerate(metadata))
    parts.append('</svg>')
    return "\n".join(parts).encode()
