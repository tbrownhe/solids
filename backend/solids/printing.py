"""Actual-size vector PDF and SVG; deterministic page planning in millimetres."""
from io import BytesIO
from math import atan2, ceil, cos, degrees, hypot, pi, sin
from xml.sax.saxutils import escape

import numpy as np
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from .fabrication import offset_polygon, signed_inset
from .schematics import project_schematic, view_direction

PAPER = {"letter": (215.9, 279.4), "a4": (210, 297), "a3": (297, 420)}
MARGIN, TOP, BOTTOM, OVERLAP = 14.0, 49.0, 39.0, 10.0
INK = HexColor("#25332e")
GRAY = HexColor("#6b716c")
BEVELER_URL = "https://www.etsy.com/listing/4466016418/precision-beveler-pottery-bevel-cutter"
SITE_URL = "https://solids.tobiasbrownheft.xyz"
SITE_LABEL = "solids.tobiasbrownheft.xyz"


def page_plan(design):
    width, height = PAPER[design["parameters"]["page_format"]]
    usable_w = width - 2 * MARGIN
    pages = []
    for template in design["templates"]:
        bottom=BOTTOM+(12 if template.get("collision_regions") else 0)
        usable_h=height-TOP-bottom
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
                              "bottom_mm":bottom,"usable_height_mm":usable_h,
                              "offset_x": MARGIN + (canvas_w - w) / 2 - col * (usable_w - OVERLAP),
                              "offset_y": bottom + (canvas_h - h) / 2 - row * (usable_h - OVERLAP)})
    assembly_rows = max(1, int((height-101)/5)+1)
    assembly_pages = ceil(len(design["edges"])/assembly_rows) if design.get("phase2") else 0
    collision_rows=max(1,int((height-116)/7)+1)
    collision_count=len((design.get("thickness_check") or {}).get("collisions",[]))
    collision_pages=ceil(collision_count/collision_rows)
    if len(pages) + 1 + assembly_pages + collision_pages > 120:
        raise ValueError("This design needs more than 120 sheets. Reduce edge length or use A3.")
    return {"page_count": len(pages) + 1 + assembly_pages + collision_pages, "template_pages": pages,
            "assembly_pages":assembly_pages,"assembly_rows":assembly_rows,
            "collision_pages":collision_pages,"collision_rows":collision_rows,
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


def _phase2_annotations(template,precision):
    polygon=template["polygon_mm"]
    for font in (7.5,7,6,5,4.5):
        candidates=[]
        for i,(a,b) in enumerate(zip(polygon,polygon[1:]+polygon[:1])):
            edge=template["edges"][i]
            side="OUT" if edge["cut_side"]=="exterior" else "IN"
            text=f"{edge['label']}  {edge['angle_deg']:.{precision}f}\N{DEGREE SIGN} {side}"
            a,b=np.array(a),np.array(b)
            tangent=(b-a)/np.linalg.norm(b-a)
            inward=np.array([-tangent[1],tangent[0]])
            angle=atan2(tangent[1],tangent[0])
            if angle>pi/2 or angle< -pi/2:
                angle+=pi
            u=np.array([cos(angle),sin(angle)]);v=np.array([-sin(angle),cos(angle)])
            half_w=stringWidth(text,"Helvetica",font)/mm/2;half_h=font/mm*.65
            minimum=max(4,max(edge["inset_mm"],edge.get("exterior_offset_mm",0))+1.5)+half_h
            choices=[]
            for fraction in (.5,.6,.4,.7,.3,.8,.2):
                for extra in (0,2,4,6):
                    center=a+(b-a)*fraction+inward*(minimum+extra)
                    corners=[(center+u*x+v*y).tolist() for x,y in ((-half_w,-half_h),(half_w,-half_h),(half_w,half_h),(-half_w,half_h))]
                    if not all(_inside(p,polygon,.6) for p in corners):
                        continue
                    if any(not all(_inside(p,template[key],1.5) for p in corners)
                           for key in ("reference_polygon_mm","inset_polygon_mm") if template[key]):
                        continue
                    choices.append({"text":text,"center":center.tolist(),"angle":degrees(angle),"font":font,"corners":corners})
            candidates.append(choices)
        if any(not choices for choices in candidates):
            continue
        order=sorted(range(len(candidates)),key=lambda i:len(candidates[i]))
        selected={};attempts=0
        def place(depth):
            nonlocal attempts
            if depth==len(order):
                return True
            index=order[depth]
            for label in candidates[index]:
                attempts+=1
                if attempts>2500:
                    return False
                if all(not _overlap(label["corners"],old["corners"]) for old in selected.values()):
                    selected[index]=label
                    if place(depth+1):
                        return True
                    del selected[index]
            return False
        if place(0):
            return [selected[i] for i in range(len(candidates))]
    raise ValueError(f"Template {template['id']} is too small for legible bevel labels. Increase the edge length or reduce thickness/depth.")


def edge_annotations(template, precision):
    if template.get("phase2"):
        return _phase2_annotations(template,precision)
    polygon = template["polygon_mm"]
    for font in (7.5, 7, 6, 5, 4.5):
        labels = []
        valid = True
        for i, (a, b) in enumerate(zip(polygon, polygon[1:] + polygon[:1])):
            edge = template["edges"][i]
            text = f"{edge['label']}  {edge['angle_deg']:.{precision}f}\N{DEGREE SIGN}"
            if template.get("phase2"):
                side = "OUT" if edge["cut_side"]=="exterior" else "IN"
                text += f" {side}"
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
            distance = max(4.0, max(edge["inset_mm"],edge.get("exterior_offset_mm",0)) + 1.5) + half_h
            center = (np.array(a) + np.array(b)) / 2 + inward * distance
            corners = [(center + u * x + v * y).tolist()
                       for x, y in ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h))]
            if not all(_inside(p, polygon, 0.6) for p in corners):
                valid = False
            if template["inset_polygon_mm"] and not all(
                _inside(p, template["inset_polygon_mm"], 1.5) for p in corners
            ):
                valid = False
            if template.get("reference_polygon_mm") and not all(
                _inside(p,template["reference_polygon_mm"],1.5) for p in corners
            ) and template.get("phase2"):
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
    if template.get("phase2"):
        layouts = [
            [(f"{template['id']} / MAKE {template['quantity']}",12,8,True),
             ("INTERIOR VIEW / CALIBRATION PLAN",8,2,True),
             ("IN: interior up / OUT: exterior up",7,-3,False)],
            [(f"{template['id']} / MAKE {template['quantity']}",9,0,True)],
        ]
        # Leave the central reference area to edge labels on narrow triangles;
        # the quantity can live anywhere safely inside the reusable raw blank.
        w,h=np.array(polygon).max(axis=0)
        for font in (10,9,8,7,6,5,4.5):
            text=f"{template['id']} / MAKE {template['quantity']}"
            half_w=stringWidth(text,"Helvetica-Bold",font)/mm/2
            half_h=font/mm*.65
            for fraction in (.5,.3,.2,.7,.15,.85):
                position=np.array([center[0],h*fraction])
                corners=[(position+[x,y]).tolist() for x,y in ((-half_w,-half_h),(half_w,-half_h),(half_w,half_h),(-half_w,half_h))]
                if all(_inside(p,polygon,.6) for p in corners) and all(not _overlap(corners,old["corners"]) for old in edge_labels):
                    fallback={"text":text,"font":font,"bold":True,"center":position.tolist(),"corners":corners}
                    break
            else:
                continue
            break
        else:
            fallback=None
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
    if template.get("phase2") and fallback:
        return [fallback]
    raise ValueError(f"Template {template['id']} is too small for a legible quantity label. Increase the working edge length.")


def collision_vertex_annotations(template, labels):
    """Optional corner callouts never displace bevel or quantity instructions."""
    result=[]
    reference=np.array(template.get("reference_polygon_mm",template["polygon_mm"]))
    center=reference.mean(axis=0)
    for i in template.get("collision_vertices",[]):
        point=reference[i]
        direction=center-point;direction/=np.linalg.norm(direction)
        text=f"V{i+1}"
        font=6
        half_w=stringWidth(text,"Helvetica-Bold",font)/mm/2;half_h=font/mm*.65
        for distance in (4,6,8,10,12,16,20,24):
            position=point+direction*distance
            corners=[(position+[x,y]).tolist() for x,y in ((-half_w,-half_h),(half_w,-half_h),(half_w,half_h),(-half_w,half_h))]
            if (all(_inside(p,template["polygon_mm"],.6) for p in corners)
                    and all(not _overlap(corners,other["corners"]) for other in labels+result)):
                result.append({"text":text,"center":position.tolist(),"point":point.tolist(),
                               "font":font,"corners":corners})
                break
    return result


def _collision_marks(c,template,ox,oy,labels):
    for region in template.get("collision_regions",[]):
        polygon=np.array(region["polygon_mm"])
        c.saveState()
        path=c.beginPath();path.moveTo((ox+polygon[0,0])*mm,(oy+polygon[0,1])*mm)
        for x,y in polygon[1:]:path.lineTo((ox+x)*mm,(oy+y)*mm)
        path.close()
        c.setStrokeColor(GRAY);c.setLineWidth(.3)
        c.drawPath(path,stroke=1,fill=0)
        c.clipPath(path,stroke=0,fill=0)
        low,high=polygon.min(axis=0),polygon.max(axis=0)
        for start in np.arange(low[0]-high[1],high[0]-low[1]+1.5,1.5):
            _line(c,ox+start+low[1],oy+low[1],ox+start+high[1],oy+high[1],.25)
        c.restoreState()
    for label in labels:
        c.setStrokeColor(GRAY)
        _line(c,ox+label["point"][0],oy+label["point"][1],ox+label["center"][0],oy+label["center"][1],.25)
        _text(c,ox+label["center"][0]-stringWidth(label["text"],"Helvetica-Bold",label["font"])/mm/2,
              oy+label["center"][1]-.65,label["text"],label["font"],True)


def _affected_copies(template):
    return sorted({w["instance_id"] for w in template.get("collision_warnings",[])})


def _copy_summary(template):
    copies=_affected_copies(template)
    return ", ".join(copies[:5])+(f" and {len(copies)-5} more" if len(copies)>5 else "")


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
          f"{p['edge_length_mm']:g} mm fired {'base ' if design.get('phase2') else ''}edge  /  {design['cut_edge_mm']:.2f} mm working {'base ' if design.get('phase2') else ''}edge  /  {p['thickness_mm']:g} mm working slab", 8)
    _text(c, MARGIN, height - 41,
          f"{p['shrinkage_percent']:g}% cut-to-fired shrinkage  /  {p['page_format'].upper()}  /  PRINT ACTUAL SIZE, 100%", 8)
    _text(c, width - 44, 9, f"SHEET {page:02d} / {total:02d}", 7)
    _print_footer(c)


def _print_footer(c):
    _text(c, MARGIN, 9, SITE_LABEL + "  /  Disable Fit to Page. Verify calibration before cutting.", 7)
    c.linkURL(SITE_URL, (MARGIN * mm, 8 * mm,
                        MARGIN * mm + stringWidth(SITE_LABEL, "Helvetica", 7), 12 * mm), relative=0)


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


def _reference_outline(c,template,ox,oy):
    if not any(e.get("exterior_offset_mm",0)>1e-7 for e in template["edges"]):
        return
    points=template["reference_polygon_mm"]
    path=c.beginPath()
    path.moveTo((ox+points[0][0])*mm,(oy+points[0][1])*mm)
    for x,y in points[1:]:
        path.lineTo((ox+x)*mm,(oy+y)*mm)
    path.close()
    c.setStrokeColor(INK);c.setLineWidth(.35);c.setDash([6,2,1,2])
    c.drawPath(path,fill=0,stroke=1);c.setDash()


def _wrapped(c, x, y, text, width, size=8, bold=False, leading=4.2):
    font = "Helvetica-Bold" if bold else "Helvetica"
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and stringWidth(candidate, font, size) > width * mm:
            _text(c, x, y, line, size, bold)
            y -= leading
            line = word
        else:
            line = candidate
    if line:
        _text(c, x, y, line, size, bold)
        y -= leading
    return y


def _schematic(c, design, direction, x, y, width, height):
    view = project_schematic(design, direction)
    low, high = view["bounds"]
    scale = min((width - 4) / (high[0] - low[0]), (height - 4) / (high[1] - low[1]))
    origin = np.array([x + width / 2, y + height / 2]) - (low + high) / 2 * scale
    transform = lambda points: (np.asarray(points) * scale + origin).tolist()
    patterns = {i: t["id"] for t in design["templates"] for i in t["face_ids"]}
    collisions = (design.get("thickness_check") or {}).get("collisions", [])
    affected = {i for collision in collisions for i in collision["faces"]}
    c.saveState()
    light = np.array([-.45, .7, 1.])
    light /= np.linalg.norm(light)
    for face in view["faces"]:
        index = face["face_index"]
        normal = np.array([-face["plane"][0], -face["plane"][1], 1.])
        normal /= np.linalg.norm(normal)
        brightness = max(0., normal @ light)
        # A fixed upper-left light distinguishes inward folds from outward
        # points even when every triangle uses the same reusable template.
        if index in affected:
            c.setFillColorRGB(*(np.array([.98, .88, .86]) * (.94 + .06 * brightness)))
        else:
            c.setFillGray(.84 + .15 * brightness)
        for region in face["regions"]:
            points = transform(region)
            path = c.beginPath()
            path.moveTo(points[0][0] * mm, points[0][1] * mm)
            for px, py in points[1:]:
                path.lineTo(px * mm, py * mm)
            path.close()
            c.drawPath(path, fill=1, stroke=0)
    c.setStrokeColor(INK)
    c.setLineWidth(.55)
    for segment in view["edges"]:
        a, b = transform(segment)
        _line(c, *a, *b, .55)
    occupied = []
    # Fit labels wholly inside visible surfaces, never across a crease or a
    # hidden surface. Dense views omit an ID before sacrificing legibility.
    for face in view["faces"]:
        index = face["face_index"]
        label = patterns[index]
        panel_id = design["face_records"][index]["id"]
        regions = sorted((transform(region) for region in face["regions"]),
                         key=lambda p: abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(p,p[1:]+p[:1]))), reverse=True)
        placed = False
        layouts = [[(label, 7, 1.3), (panel_id, 5.5, -1.6)], [(label, 7, 0)]] if design.get("phase2") else [[(label, 7, 0)]]
        for layout in layouts:
            for polygon in regions:
                center = np.mean(polygon, axis=0)
                positions = [center] + [.75*center + .25*np.array(p) for p in polygon]
                for position in positions:
                    boxes = []
                    for text, font, offset in layout:
                        hw, hh = stringWidth(text, "Helvetica-Bold", font) / mm / 2, font / mm * .6
                        cx, cy = position + [0, offset]
                        boxes.append([[cx-hw,cy-hh],[cx+hw,cy-hh],[cx+hw,cy+hh],[cx-hw,cy+hh]])
                    if not all(_inside(p, polygon, .65) for box in boxes for p in box):
                        continue
                    if any(_overlap(box, old) for box in boxes for old in occupied):
                        continue
                    for text, font, offset in layout:
                        c.setFillColor(INK);c.setFont("Helvetica-Bold",font)
                        c.drawCentredString(position[0]*mm,(position[1]+offset)*mm-font*.3,text)
                    occupied.extend(boxes)
                    placed = True
                    break
                if placed:
                    break
            if placed:
                break
    # Mark only corners actually visible in this view; hidden warnings remain
    # on the detailed template and overlap reference sheets.
    corners = {v for collision in collisions for v in collision["shared_vertices"]}
    for vertex in sorted(corners):
        point = view["vertices"][vertex]
        if any(np.linalg.norm(point - endpoint) < 1e-7 for segment in view["edges"] for endpoint in segment):
            px, py = transform([point])[0]
            c.setStrokeColor(HexColor("#963f37"));c.setFillColor(HexColor("#963f37"))
            c.circle(px*mm,py*mm,.7*mm,fill=1,stroke=0)
    c.restoreState()


def _joint_section(c, x, y, width, phase2):
    """Compact section alongside the exterior assembly views."""
    _text(c,x,y,"BEVEL SECTION / UPPER WEDGE IS WASTE",7,True)
    sy = y - 20
    c.setStrokeColor(INK);c.setFillColor(HexColor("#e6e9e3"))
    path=c.beginPath()
    path.moveTo((x+4)*mm,sy*mm);path.lineTo((x+12)*mm,(sy+10)*mm)
    path.lineTo((x+width-4)*mm,(sy+10)*mm);path.lineTo((x+width-4)*mm,sy*mm);path.close()
    c.drawPath(path,fill=1,stroke=1)
    c.setDash(2,2);_line(c,x+4,sy,x+4,sy+10);_line(c,x+4,sy+10,x+12,sy+10);c.setDash()
    _text(c,x+14,sy+13,"INTERIOR FACE UP" + (" / IN" if phase2 else ""),7,True)
    _text(c,x+4,sy-4,"EXTERIOR FACE DOWN / keep exterior edge",7)
    if phase2:
        _text(c,x,sy-10,"For OUT edges, turn over: EXTERIOR FACE UP.",7)
    else:
        _text(c,x,sy-10,"Inset = thickness / tan(tool angle)",7)
    return sy-16


def _reference_cover(c, design, plan):
    w,h=plan["paper_width_mm"],plan["paper_height_mm"]
    phase2=design.get("phase2")
    _header(c,design,design["name"],1,plan["page_count"],w,h)
    size=" x ".join(f"{v:.1f}" for v in design["dimensions"]["fired_mm"])
    _text(c,MARGIN,h-49,f"ESTIMATED FIRED SIZE / W x D x H: {size} mm (exterior reference)",8,True)
    gap=10
    column=(w-2*MARGIN-gap)/2
    right=MARGIN+column+gap
    top=h-61
    bottom=54
    view_h=(top-bottom-28)/2
    direction=view_direction(design)
    _text(c,right,top,"FINISHED FORM / EXTERIOR VIEWS",8,True)
    _text(c,right,top-7,"VIEW A",7)
    _schematic(c,design,direction,right,top-11-view_h,column,view_h)
    _text(c,right,top-18-view_h,"OPPOSITE VIEW / INCLUDING UNDERSIDE",7)
    _schematic(c,design,-direction,right,top-22-2*view_h,column,view_h)
    _wrapped(c,right,bottom,"Letters = template IDs. Views not to scale.",column,7,leading=3.5)
    _wrapped(c,right,bottom-7,"Panel IDs shown where space allows." if phase2 else "Build reference; use full-size sheets for cutting.",column,6.5,leading=3.5)
    y=top
    _text(c,MARGIN,y,f"{design['total_faces']} PANELS / {len(design['templates'])} REUSABLE TYPES",9,True)
    y-=6
    summary=" / ".join(f"{t['id']}: MAKE {t['quantity']}" for t in design["templates"][:6])
    y=_wrapped(c,MARGIN,y,summary,column,8,True)
    if len(design["templates"])>6:
        y=_wrapped(c,MARGIN,y,"Full quantities are on the template sheets.",column,7)
    y-=3
    _text(c,MARGIN,y,"PRINT, CUT & ASSEMBLE",8,True);y-=6
    instructions = [
        "Print at Actual Size / 100%; turn off Fit, Shrink and borderless enlargement. Check both calibration marks.",
    ]
    if phase2:
        instructions += [
            "Trace the solid RAW BLANK outline, including reflex-edge extensions.",
            "IN: cut and bevel INTERIOR FACE UP / EXTERIOR FACE DOWN.",
            "OUT: bevel EXTERIOR FACE UP / INTERIOR FACE DOWN. Keep edge IDs when turning over.",
            "Dash-dot = final exterior reference. Dashed = interior surface. Neither is a cutting outline.",
            "Keep slab thickness inward of the exterior reference. Edge lengths are working reference lengths.",
            "Match panel and joint IDs using the assembly sheets. Dry-fit convex/reflex scrap joints first.",
        ]
    else:
        instructions += [
            "Cut AND bevel EXTERIOR FACE DOWN / INTERIOR FACE UP.",
            "Trace the full solid outline. Remove the upper waste on that same side; keep the full exterior edge underneath.",
            "Dashed lines show the remaining upper INTERIOR face; they are not a cutting outline.",
            "Make the quantity on each template. Test-fit a scrap joint before making a full set.",
        ]
    instructions.append("Angles are from the slab plane: 90 deg = normal; 0 deg = parallel. Shrinkage is applied once.")
    if design.get("chirality"):
        instructions.append("Chiral form: preserve the handedness shown. Rotate templates; never mirror them.")
    if design["cut_edge_mm"] < 25:
        instructions.append("Small panels may have limited room for legible bevel labels; check before cutting.")
    if plan["tiled"]:
        instructions.append("Tiled panels: match ID and row/column; align crosses with 10 mm overlap before tracing.")
    if plan["collision_pages"]:
        instructions.append("Pale red / dots = fitting areas. Bevel first, then shape marked corners to fit; overlaps do not rule out assembly.")
    for instruction in instructions:
        y=_wrapped(c,MARGIN,y,instruction,column,8,leading=4.1)-1.6
    y-=2
    if phase2:
        y=_wrapped(c,MARGIN,y,"EXPERIMENTAL / DRY-FIT REQUIRED",column,8,True)-2
    # Longer custom or tiled plans keep the safety instructions in full. The
    # bevel illustration is supplemental, and yields to them on compact paper.
    if y-36 >= 52:
        y=_joint_section(c,MARGIN,y,column,phase2)
    if y >= 63:
        note="Optimized for adjustable wire bevelers such as the Precision Beveler by KellyHoferStudios."
        end=_wrapped(c,MARGIN,y,note,column,7,leading=3.7)
        c.linkURL(BEVELER_URL,(MARGIN*mm,end*mm,(MARGIN+column)*mm,(y+3)*mm),relative=0)
    _ruler(c,28)
    c.setStrokeColor(INK);c.setLineWidth(.5)
    c.rect((w-MARGIN-25.4)*mm,22*mm,25.4*mm,25.4*mm)
    _text(c,w-MARGIN-25.4,17,"1 inch / 25.4 mm",7)


def _assembly_pages(c,design,plan):
    w,h=plan["paper_width_mm"],plan["paper_height_mm"]
    matched={}
    for t in design["templates"]:
        for instance in t["instances"]:
            for edge in instance["edges"]:
                matched[(instance["face_index"],edge["joint_id"])]=f"{instance['id']} {t['id']}/{edge['label']}"
    rows=plan["assembly_rows"]
    for pi in range(plan["assembly_pages"]):
        page_number=2+len(plan["template_pages"])+pi
        _header(c,design,"ASSEMBLY / MATCHED JOINTS",page_number,plan["page_count"],w,h)
        y=h-54
        _text(c,MARGIN,y,"JOINT",7,True);_text(c,32,y,"PANEL / TEMPLATE EDGE",7,True)
        _text(c,110,y,"MEETS PANEL / EDGE",7,True);_text(c,w-48,y,"TOOL / SIDE",7,True)
        y-=7
        for edge in design["edges"][pi*rows:(pi+1)*rows]:
            _text(c,MARGIN,y,edge["id"],7)
            _text(c,32,y,matched[(edge["faces"][0],edge["id"])],7)
            _text(c,110,y,matched[(edge["faces"][1],edge["id"])],7)
            side="OUT" if edge["cut_side"]=="exterior" else "IN"
            _text(c,w-48,y,f"{edge['angle_deg']:.{design['parameters']['angle_precision']}f} deg {side}",7)
            y-=5
        _text(c,MARGIN,34,"Fxxx = original base face. .n = pyramid subface. Joint IDs occur on both mating panels.",7)
        _ruler(c);c.showPage()


def _collision_pages(c,design,plan):
    collisions=(design.get("thickness_check") or {}).get("collisions",[])
    w,h=plan["paper_width_mm"],plan["paper_height_mm"]
    rows=plan["collision_rows"]
    for pi in range(plan["collision_pages"]):
        page_number=2+len(plan["template_pages"])+plan["assembly_pages"]+pi
        _header(c,design,"OVERLAP / MANUAL RELIEF REFERENCE",page_number,plan["page_count"],w,h)
        _text(c,MARGIN,h-49,"Marked patterns are separate from clear copies. Check the affected instance IDs below.",7)
        _text(c,MARGIN,h-55,"Vn is the shared reference corner at the start of En, in the interior view. Hatching is not a cut line.",7)
        _text(c,MARGIN,h-61,"Overlaps do not rule out assembly: bevel first, then manually shape marked corners to fit and dry-fit.",7)
        _text(c,MARGIN,h-71,"CASE",7,True);_text(c,34,h-71,"PANEL / PATTERN / CORNER",7,True)
        _text(c,113,h-71,"OVERLAPS PANEL / PATTERN / CORNER",7,True)
        y=h-79
        for collision in collisions[pi*rows:(pi+1)*rows]:
            _text(c,MARGIN,y,collision["id"],7)
            for x,panel in zip((34,113),collision["panels"]):
                corners=",".join(panel["corner_labels"]) or "hatched area"
                _text(c,x,y,f"{panel['instance_id']} / {panel['template_id']} / {corners}",7)
            y-=7
        _ruler(c);c.showPage()


def _cover(c, design, plan):
    _reference_cover(c, design, plan)


def pdf_bytes(design):
    plan = page_plan(design)
    if design.get("fabrication_error"):
        raise ValueError(design["fabrication_error"])
    if any(not t["inset_polygon_mm"] for t in design["templates"]):
        raise ValueError("Cannot export: bevels consume an interior face. Reduce thickness or increase edge length.")
    annotations = {t["id"]: edge_annotations(t, design["parameters"]["angle_precision"]) for t in design["templates"]}
    center_labels = {t["id"]: center_annotations(t, annotations[t["id"]]) for t in design["templates"]}
    corner_labels={t["id"]:collision_vertex_annotations(t,annotations[t["id"]]+center_labels[t["id"]]) for t in design["templates"]}
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
        if design.get("phase2"):
            dimensions=" / ".join(f"{e['label']} {e['length_mm']:.2f}" for e in template["edges"])
            _text(c,MARGIN,h-46,"REFERENCE EDGES (working mm): "+dimensions,7)
        ox, oy = page["offset_x"], page["offset_y"]
        c.saveState()
        clip = c.beginPath()
        clip.rect(MARGIN * mm, page["bottom_mm"] * mm, (w - 2 * MARGIN) * mm, page["usable_height_mm"] * mm)
        c.clipPath(clip, stroke=0, fill=0)
        _collision_marks(c,template,ox,oy,corner_labels[template["id"]])
        c.setStrokeColor(INK)
        _outline(c, template["polygon_mm"], ox, oy)
        c.setStrokeColor(GRAY)
        _outline(c, template["inset_polygon_mm"], ox, oy, dashed=True)
        if template.get("phase2"):
            _reference_outline(c,template,ox,oy)
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
            pw, ph = w - 2 * MARGIN, page["usable_height_mm"]
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
        if template.get("collision_regions"):
            _text(c,MARGIN,47,"OVERLAP WARNING / Shape marked corners to fit after beveling. Hatching is not a cut line.",7,True)
            _text(c,MARGIN,41,"Affected copies: "+_copy_summary(template)+". See the overlap reference for the full list.",7)
        if design.get("phase2"):
            _text(c,MARGIN,34,"IN = INTERIOR UP / OUT = EXTERIOR UP. Lengths refer to the exterior reference, not the blank.",7)
        else:
            _text(c, MARGIN, 34, "Cut + bevel: EXTERIOR FACE DOWN / INTERIOR FACE UP. Solid = full outline; dashed = interior inset.", 7)
        _ruler(c)
        c.showPage()
    if design.get("phase2"):
        _assembly_pages(c,design,plan)
        _collision_pages(c,design,plan)
    c.save()
    return stream.getvalue()


def svg_bytes(design, template_id):
    if design.get("fabrication_error"):
        raise ValueError(design["fabrication_error"])
    template = next((t for t in design["templates"] if t["id"] == template_id), None)
    if template is None:
        raise ValueError("Unknown template ID.")
    if not template["inset_polygon_mm"]:
        raise ValueError("Bevels consume the interior face. Reduce thickness or increase edge length.")
    points = template["polygon_mm"]
    w, h = np.array(points).max(axis=0)
    labels = edge_annotations(template, design["parameters"]["angle_precision"])
    center_labels = center_annotations(template, labels)
    corner_labels=collision_vertex_annotations(template,labels+center_labels)
    polygon = lambda p: " ".join(f"{x:.8f},{h-y:.8f}" for x, y in p)
    metadata = [f'{template_id}: MAKE {template["quantity"]} / INTERIOR FACE UP / EXTERIOR FACE DOWN',
                f'Working edge {design["cut_edge_mm"]:.2f} mm / slab {design["parameters"]["thickness_mm"]:g} mm / print at 100%',
                'Keep EXTERIOR FACE DOWN for cutting AND beveling. Remove upper waste.',
                'Solid = full exterior footprint; dashed = remaining upper interior face.',
                'Angles from slab plane: 90 deg = perpendicular; 0 deg = parallel']
    if template.get("phase2"):
        metadata = [f'{template_id}: MAKE {template["quantity"]} / INTERIOR VIEW / CALIBRATION PLAN',
                    'IN = interior face up; OUT = exterior face up. Follow each edge label.',
                    'Solid = extended blank; dash-dot = exterior reference; dashed = interior surface.',
                    'Reference dimensions in working mm; angles from slab plane, 90 deg = normal.',
                    'Test a convex/reflex scrap joint before fabrication. Match edges using the PDF assembly table.']
        metadata[3]="Reference edges (working mm): "+" / ".join(f"{e['label']} {e['length_mm']:.2f}" for e in template["edges"])
        size=" x ".join(f"{value:.1f}" for value in design["dimensions"]["fired_mm"])
        metadata.append(f"Estimated fired model size (W x D x H): {size} mm")
    if template.get("collision_regions"):
        metadata.extend(["OVERLAP WARNING: manually shape hatched corners to fit after beveling; overlaps do not rule out assembly.",
                         "Affected copies: "+_copy_summary(template)+". Match each case using the PDF overlap reference.",
                         "V# marks shared corners. Copies share matching overlap marks; hatching is not a cut line."])
    metadata.append(SITE_LABEL)
    # Keep metadata legible even when the physical panel is very small. Widen
    # the document, preserving one viewBox unit per mm and the cut outline.
    document_width = max(w + 20, max(stringWidth(line, "Helvetica", 2.5 * mm) / mm for line in metadata) + 20)
    document_height=h+max(50,18+5*len(metadata))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{document_width:.8f}mm" height="{document_height:.8f}mm" viewBox="-10 -10 {document_width:.8f} {document_height:.8f}">',
             f'<title>{escape(design["name"])} template {template_id}, make {template["quantity"]}</title>',
             '<g fill="none" stroke="#25332e" stroke-width="0.2">',
             f'<polygon points="{polygon(points)}"/>',
             f'<polygon points="{polygon(template["inset_polygon_mm"])}" stroke-dasharray="1.2 1.2" stroke-width="0.12"/>', '</g>']
    if template.get("collision_regions"):
        parts.append('<defs><pattern id="overlap-hatch" patternUnits="userSpaceOnUse" width="1.5" height="1.5"><path d="M0 1.5L1.5 0" stroke="#6b716c" stroke-width="0.1"/></pattern></defs>')
        for region in template["collision_regions"]:
            parts.append(f'<polygon points="{polygon(region["polygon_mm"])}" fill="url(#overlap-hatch)" stroke="#6b716c" stroke-width="0.1"/>')
        for label in corner_labels:
            x,y=label["center"];px,py=label["point"]
            parts.append(f'<path d="M{px:.8f} {h-py:.8f}L{x:.8f} {h-y:.8f}" stroke="#6b716c" stroke-width="0.1"/>')
            parts.append(f'<text x="{x:.8f}" y="{h-y:.8f}" text-anchor="middle" dominant-baseline="central" font-family="Helvetica,Arial,sans-serif" font-size="{label["font"]/mm:.8f}" font-weight="bold">{label["text"]}</text>')
    if template.get("phase2") and any(e.get("exterior_offset_mm",0)>1e-7 for e in template["edges"]):
        parts.append(f'<polygon points="{polygon(template["reference_polygon_mm"])}" fill="none" stroke="#25332e" stroke-width="0.12" stroke-dasharray="2 0.7 0.4 0.7"/>')
    for label in labels:
        x, y = label["center"]
        parts.append(f'<text transform="translate({x:.8f} {h-y:.8f}) rotate({-label["angle"]:.8f})" text-anchor="middle" dominant-baseline="central" font-family="Helvetica,Arial,sans-serif" font-size="{label["font"]/mm:.8f}" fill="#25332e">{escape(label["text"])}</text>')
    for label in center_labels:
        x, y = label["center"]
        parts.append(f'<text transform="translate({x:.8f} {h-y:.8f})" text-anchor="middle" dominant-baseline="central" font-family="Helvetica,Arial,sans-serif" font-size="{label["font"]/mm:.8f}" font-weight="{"bold" if label["bold"] else "normal"}" fill="#25332e">{escape(label["text"])}</text>')
    parts.extend(f'<text x="0" y="{h+8+i*5}" font-family="Helvetica,Arial,sans-serif" font-size="2.5">{escape(line)}</text>' for i, line in enumerate(metadata))
    parts.append('</svg>')
    return "\n".join(parts).encode()


def calibration_pdf_bytes(parameters):
    """Two reusable, actual-size templates for convex/reflex 60-degree coupons."""
    w,h=PAPER[parameters.page_format]
    stream=BytesIO();c=Canvas(stream,pagesize=(w*mm,h*mm),invariant=1)
    c.setTitle("Convex and reflex miter calibration coupons")
    _text(c,MARGIN,h-18,"SOLIDS / CONVEX + REFLEX CALIBRATION",12,True)
    _text(c,MARGIN,h-28,f"Working slab {parameters.thickness_mm:g} mm / 60 deg tool setting / PRINT ACTUAL SIZE, 100%",9)
    y=h-42
    for line in [
        "Cut TWO copies of each coupon. Their exterior reference edges are 70 x 45 working mm.",
        "Bevel ONLY E1 at 60 deg; leave E2-E4 square. IN means interior up, OUT means exterior up.",
        "Dry-fit the IN pair at 120 deg interior dihedral and the OUT pair at 240 deg (a recess).",
        "Check continuous contact through the slab thickness and preservation of the exterior reference.",
        "Use scrap clay at the working moisture/thickness. Shrinkage is not applied to these tool coupons.",
    ]:
        _text(c,MARGIN,y,line,8);y-=6
    for index,delta in enumerate((120,240)):
        side="interior" if delta==120 else "exterior"
        reference=[[0.,0],[70.,0],[70.,45],[0.,45]]
        distance=signed_inset(delta,parameters.thickness_mm)
        offsets=[distance,0,0,0]
        blank=offset_polygon(reference,[min(0,d) for d in offsets])
        interior=offset_polygon(reference,offsets)
        if not interior:
            raise ValueError("The calibration coupon is too small for this slab thickness.")
        shift=-np.array(blank).min(axis=0)
        reference=(np.array(reference)+shift).tolist();blank=(np.array(blank)+shift).tolist();interior=(np.array(interior)+shift).tolist()
        edges=[{"label":f"E{i+1}","angle_deg":60 if i==0 else 90,"cut_side":side if i==0 else "interior",
                "inset_mm":max(0,offsets[i]),"exterior_offset_mm":max(0,-offsets[i])} for i in range(4)]
        t={"id":"IN" if index==0 else "OUT","quantity":2,"phase2":True,"polygon_mm":blank,
           "reference_polygon_mm":reference,"inset_polygon_mm":interior,"edges":edges}
        labels=edge_annotations(t,2);centers=center_annotations(t,labels)
        ox=MARGIN if index==0 else w/2+4
        oy=h*.45
        top=max(p[1] for p in blank)
        if oy+top+12>h-80:
            raise ValueError("Calibration coupons exceed this paper size at the chosen thickness. Use A3 or thinner scrap.")
        _text(c,ox,oy+top+8,f"{t['id']} / {delta} deg joint / MAKE 2",9,True)
        c.setStrokeColor(INK);_outline(c,blank,ox,oy)
        c.setStrokeColor(GRAY);_outline(c,interior,ox,oy,True)
        _reference_outline(c,t,ox,oy)
        for label in labels:
            c.saveState();c.translate((ox+label["center"][0])*mm,(oy+label["center"][1])*mm)
            c.rotate(label["angle"]);c.setFillColor(INK);c.setFont("Helvetica",label["font"])
            c.drawCentredString(0,-label["font"]*.3,label["text"]);c.restoreState()
        for label in centers:
            c.setFillColor(INK);c.setFont("Helvetica-Bold" if label["bold"] else "Helvetica",label["font"])
            c.drawCentredString((ox+label["center"][0])*mm,(oy+label["center"][1])*mm-label["font"]*.3,label["text"])
        _text(c,ox,oy-8,f"Signed interior offset: {distance:+.4f} mm",7)
    _text(c,MARGIN,76,"SOLID = blank / DASH-DOT = exterior reference / DASHED = interior surface",8)
    _text(c,MARGIN,68,"Record tool indication, measured thickness and dry-fit result before making a full shell.",8)
    _ruler(c,28)
    c.setStrokeColor(INK);c.setLineWidth(.5)
    c.rect((w-MARGIN-25.4)*mm,22*mm,25.4*mm,25.4*mm)
    _text(c,w-MARGIN-25.4,17,"1 inch / 25.4 mm",7)
    _print_footer(c)
    c.showPage();c.save();return stream.getvalue()
