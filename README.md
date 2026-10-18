# Solids Studio

A ceramic slab template generator with all 13 Archimedean and five Platonic
solids. Inspect the joints in 3D and export reusable, actual-size vector panels.
No accounts, database, external runtime requests, or persistent server state.

## Run locally with Docker Desktop

From this directory:

```bash
docker compose up -d --build
```

Open **http://localhost:8081**. Port 8080 is already used by the local personal
website. The app binds only to loopback.

```bash
docker compose ps
docker compose logs --tail=50 studio
docker compose down
```

One non-root, read-only container serves the React build and FastAPI on a single
origin. Exports are generated in memory; no volumes or secrets are needed.
Dependencies are locked in `uv.lock` and `frontend/package-lock.json`.

## Develop without Docker

Requires Python 3.11+ with [uv](https://docs.astral.sh/uv/) and Node 22.12+.
Docker uses Python 3.12 and Node 24.

```bash
uv sync
PYTHONPATH=backend uv run uvicorn solids.api:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to Python. Alternatively,
`npm run build` produces `frontend/dist`, which FastAPI serves directly on its
next startup. Fonts ship in the frontend bundle.

## Dimensions and geometry

- **Exterior edge:** desired final dimension after firing, in mm.
- **Slab thickness:** slab-roller setpoint in working clay, before drying/firing.
- **Shrinkage:** total isotropic linear shrinkage from cutting to fired, percent.
  Working edge = fired edge / (1 - shrinkage / 100).
- **Tool angle:** measured from the slab plane. The Kelly Hofer convention was
  confirmed by the owner: 90° is perpendicular, 0° is parallel.
- **Cutting and beveling orientation:** keep the **exterior face down** and the
  **interior face up** throughout both operations. Trace and cut the full solid
  outline onto the upper interior side, then bevel away the upper waste in that
  same position. Preserve the full exterior edge underneath. The dashed polygon
  shows the remaining upper interior face after beveling, never a cut outline.
- **Quantities:** one reusable copy of each unique panel, with MAKE # printed
  inside its cut outline so the quantity stays on the cutout. Grouping includes
  shape and ordered bevel/adjacency sequence modulo
  rotation. Reflection is never used to merge groups. Each panel is displayed
  from the interior for working face up; edge order is reversed from its exterior
  view to retain the assembled solid's handedness. Each snub has one explicit hand.

The workflow is optimized for adjustable wire bevelers that remove upper waste,
such as the [Precision Beveler – Pottery Bevel Cutter – Custom Angle Beveler
by KellyHoferStudios](https://www.etsy.com/listing/4466016418/precision-beveler-pottery-bevel-cutter).

For outward face normals with angle alpha, interior dihedral = 180° - alpha;
symmetric tool angle = dihedral / 2. Thickness changes the interior-face inset
(`thickness / tan(tool angle)`), not the bevel angle. Convex half-plane
intersection handles corners. A collapsed interior blocks export.

The registry generates solids locally from Coxeter reflection/rotation groups.
Coplanar Qhull triangles are merged into true polygon faces before computing
adjacency. Provenance is documented in `backend/solids/registry.py`; no
third-party mesh tables are used. Geometry and print code are separate pure
modules; the API and CLI use the same pipeline.

## Generate the acceptance PDF

```bash
PYTHONPATH=backend uv run python -m solids \
  --solid rhombicuboctahedron --edge 120 --thickness 6 --shrinkage 0 \
  --paper letter --precision 2 \
  --output artifacts/rhombicuboctahedron-120mm-letter.pdf
```

Verified output: 26 faces, 48 edges, three unique templates, four Letter sheets
(calibration/instructions plus one sheet per reusable panel).

| Template | Quantity | Ordered tool settings from slab plane |
| --- | ---: | --- |
| A: triangle | 8 | 72.36780516° on every edge |
| B: square | 6 | 67.5° on every edge |
| C: square | 12 | 67.5°, 72.36780516°, 67.5°, 72.36780516° |

The triangle-facing edges on C are opposite. At 6 mm slab thickness, the insets
are approximately 1.9070 mm at 72.36780516° and 2.4853 mm at 67.5°.

The truncated octahedron produces six squares at 62.63219484° and eight hexagons
alternating 54.73561032° / 62.63219484°.

## Export and print

PDF supports US Letter, A4 and A3 at 1:1, with 14 mm side margins. Oversized panels
tile with 10 mm overlap, template IDs, row/column labels, and matching registration
crosses. Align common crosses and join the complete outline before tracing. The
UI reports the sheet count. Designs requiring more than 120 sheets are rejected.

Every PDF includes a true 100 mm ruler on each page and a 1-inch square on the
instructions sheet. Geometry is vector, with `72 / 25.4` PDF points per mm.
Polygons never scale to fit. Labels decrease in size if needed; export is blocked
if they cannot fit legibly. Screen annotations are enlarged for readability.
Each card also downloads a physical-unit SVG. DXF and connected folding nets
are outside this initial implementation.

Print at **Actual Size / 100%**, disable Fit to Page and borderless enlargement,
then measure the calibration marks. Dimensional tests cannot compensate for
printer scaling or ceramic material variation; test a scrap joint first.

The supplied reference PDF informed the initial design. Generated PDFs are saved
under `artifacts/` by the CLI; browser downloads use the chosen download folder.

## Verification

```bash
uv run pytest -q
cd frontend
npm run build
```

Tests cover independent inventories for all 18 solids, regular polygons,
planarity, winding, closed manifold connectivity, Euler characteristic, reference
angles and cyclic patterns, quantities, shrinkage, insets, invalid inputs, PDF
units and outline bounds, collision-free edge labels, page bounds, deterministic
exports, calibration, tiling, SVG units, and the API workflow. PDF checks inspect
vector paths and text using PyMuPDF.

With the Docker app running, browser QA can use a disposable container. First
install frontend dependencies with `npm ci` in `frontend`, then run from the
repository root:

```bash
docker run --rm --init --shm-size=1g --network solids_default \
  --user "$(id -u):$(id -g)" -e STUDIO_URL=http://studio:8000 \
  -v "$PWD:/work" -w /work/frontend \
  mcr.microsoft.com/playwright:v1.64.1-noble npm run test:browser
```

The browser package is pinned to 1.64.1; update the image tag with it. On a host
with Chromium system dependencies, `npx playwright install chromium` then
`npm run test:browser` also works. QA covers parameters, previews, persistence,
edge details, downloads, errors, the guide, mobile overflow, JS errors, and
absence of external runtime requests. Screenshots and test exports are saved
under ignored `artifacts/browser/`.

## Later deployment to silicide

Public hostname: **solids.tobiasbrownheft.xyz**, without login. No server or DNS
changes have been made. `compose.production.yaml` uses `traefik-public`, existing
opt-in discovery labels, the `le` certificate resolver, shared rate-limit/security
middleware, and an explicit HTTP redirect. It publishes no host port.

Before deployment, create the proxied Cloudflare DNS record and arrange dynamic
IP updates for its zone. Existing infra DDNS is zone-specific; a different zone
may need separate setup. Preserve its existing allowlist. From a future checkout
at `/srv/solids`:

```bash
docker compose -f compose.production.yaml config --quiet
docker compose -f compose.production.yaml up -d --build
```

The review found existing infra USB backup failures due to insufficient
destination space. Fixing that and extending the ParseTrail-specific backup
boundary are separate infra work. This app currently has no irreplaceable
server-side user data; browser preferences live in local storage.
