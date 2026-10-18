from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from .geometry import Parameters, make_design
from .printing import center_annotations, edge_annotations, page_plan, pdf_bytes, svg_bytes, calibration_pdf_bytes
from .registry import list_solids
from .transforms import PRESETS, SUPPORTED_BASES

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
    return [{**solid,"transform_supported":solid["id"] in SUPPORTED_BASES} for solid in list_solids()]


@app.get("/api/presets")
def presets():
    return PRESETS


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
            template["center_annotations"] = center_annotations(template, template["annotations"])
        except ValueError as error:
            template["annotations"] = []
            template["center_annotations"] = []
            result["export_error"] = str(error)
    if any(not template["inset_polygon_mm"] for template in result["templates"]):
        result["export_error"] = "Bevels consume an interior face. Reduce slab thickness or increase edge length."
    if result.get("fabrication_error"):
        result["export_error"] = result["fabrication_error"]
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


@app.post("/api/export/calibration")
def export_calibration(parameters: Parameters):
    try:
        output=calibration_pdf_bytes(parameters)
    except ValueError as error:
        raise HTTPException(status_code=422,detail=str(error)) from error
    return Response(output,media_type="application/pdf",headers={
        "Content-Disposition":'attachment; filename="convex-reflex-calibration.pdf"',"Cache-Control":"no-store"})


@app.get("/guide/slab-polyhedra", include_in_schema=False)
def guide_canonical():
    return RedirectResponse("/guide/slab-polyhedra/", status_code=308)


frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class StudioFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            if path.startswith("assets/"):
                # Vite fingerprints every file in this directory.
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            elif response.headers.get("content-type", "").startswith("text/html") or path in {"robots.txt", "sitemap.xml"}:
                response.headers["Cache-Control"] = "no-cache"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response


if frontend.is_dir():
    app.mount("/", StudioFiles(directory=frontend, html=True), name="studio")
