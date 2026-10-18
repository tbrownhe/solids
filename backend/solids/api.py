from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles

from .geometry import Parameters, make_design
from .printing import center_annotations, edge_annotations, page_plan, pdf_bytes, svg_bytes
from .registry import list_solids

app = FastAPI(title="Solids Studio", version="0.1.0")


def _design(parameters):
    try:
        return make_design(parameters)
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/solids")
def catalog():
    return list_solids()


@app.post("/api/design")
def design(parameters: Parameters):
    result = _design(parameters)
    try:
        result["layout"] = page_plan(result)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    result["export_error"] = None
    for template in result["templates"]:
        try:
            template["annotations"] = edge_annotations(template, parameters.angle_precision)
            center_annotations(template, template["annotations"])
        except ValueError as error:
            template["annotations"] = []
            result["export_error"] = str(error)
    if any(not template["inset_polygon_mm"] for template in result["templates"]):
        result["export_error"] = "Bevels consume an interior face. Reduce slab thickness or increase edge length."
    return result


@app.post("/api/export/pdf")
def export_pdf(parameters: Parameters):
    result = _design(parameters)
    try:
        output = pdf_bytes(result)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(output, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{parameters.solid_id}-templates.pdf"',
        "Cache-Control": "no-store",
    })


@app.post("/api/export/svg/{template_id}")
def export_svg(template_id: str, parameters: Parameters):
    result = _design(parameters)
    try:
        output = svg_bytes(result, template_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return Response(output, media_type="image/svg+xml", headers={
        "Content-Disposition": f'attachment; filename="{parameters.solid_id}-{template_id}.svg"',
        "Cache-Control": "no-store",
    })


frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend.is_dir():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="studio")
