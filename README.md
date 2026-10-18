# Solids Studio

A ceramic slab template generator with all 13 Archimedean and five Platonic
solids, plus experimental recessed and outward-pyramid construction recipes.
Inspect the joints in 3D and export reusable, actual-size vector panels.
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

- **Finished base edge:** desired original solid edge after firing, in mm.
  Transformed triangular panels can have unequal edges; their individual
  dimensions are calculated from the transformed mesh.
- **Slab thickness:** slab-roller setpoint in working clay, before drying/firing.
- **Shrinkage:** total isotropic linear shrinkage from cutting to fired, percent.
  Working edge = fired edge / (1 - shrinkage / 100).
- **Tool angle:** measured from the slab plane. The Kelly Hofer convention was
  confirmed by the owner: 90° is perpendicular, 0° is parallel.
- **Convex cutting and beveling orientation:** keep the **exterior face down** and the
  **interior face up** throughout both operations. Trace and cut the full solid
  outline onto the upper interior side, then bevel away the upper waste in that
  same position. Preserve the full exterior edge underneath. The dashed polygon
  shows the remaining upper interior face after beveling, never a cut outline.
  Recessed constructions can require exterior-side bevels; follow the explicit
  IN/OUT instructions below instead of applying this convex-only workflow.
- **Quantities:** one reusable copy of each unique panel, with MAKE # printed
  inside its cut outline so the quantity stays on the cutout. Grouping includes
  shape and ordered bevel/adjacency sequence modulo
  rotation. Reflection is never used to merge groups. Each panel is displayed
  from the interior for working face up; edge order is reversed from its exterior
  view to retain the assembled solid's handedness. Each snub has one explicit hand.

The workflow is optimized for adjustable wire bevelers that remove upper waste,
such as the [Precision Beveler – Pottery Bevel Cutter – Custom Angle Beveler
by KellyHoferStudios](https://www.etsy.com/listing/4466016418/precision-beveler-pottery-bevel-cutter).

For convex joints with outward face normals separated by alpha, interior
dihedral = 180° - alpha and symmetric tool angle = dihedral / 2. Thickness
changes the interior-face inset (`thickness / tan(tool angle)`), not the bevel
angle. A collapsed interior blocks export. The signed convention for reflex
joints is described below.

The registry generates solids locally from Coxeter reflection/rotation groups.
Coplanar Qhull triangles are merged into true polygon faces before computing
adjacency. Provenance is documented in `backend/solids/registry.py`; no
third-party mesh tables are used. Geometry and print code are separate pure
modules; the API and CLI use the same pipeline.

## Recessed and outward-pyramid constructions

Choose a construction preset, or select a base face in 3D and use **Flat / Recess /
Extrude**. Numeric and slider offsets are measured from the original face plane,
in fired mm, along its normal. The apex is centered on the original regular
polygon's centroid. Its perimeter vertices remain fixed. Apply the edit to all
faces with the same number of sides, or reset transformations to the base solid.

| Preset | Construction |
| --- | --- |
| One-face excavated cube | One square replaced by four inward triangles |
| Excavated cube | All six squares replaced by inward pyramids |
| Excavated tetrahedron / octahedron | All faces replaced by inward pyramids |
| Stellated cube / octahedron / dodecahedron | All faces replaced by outward pyramids |

These are construction-recipe names, rather than claims of standard mathematical
solid identity. Editable bases are cube, tetrahedron, octahedron, cuboctahedron,
rhombicuboctahedron and dodecahedron. Recesses are conservatively limited before
the original solid's center; surface and thick-panel checks may impose a smaller
usable offset. The default shallow offsets are starting points, not material
limits.

The edge tangent follows the first incident face's outward boundary. The signed
fold is `atan2(tangent · (normal1 × normal2), normal1 · normal2)`, positive for
convex edges. Interior dihedral is `delta = 180° - signed_fold`:

| Joint | Interior dihedral | Wire angle from slab | Face up for beveling |
| --- | ---: | ---: | --- |
| Convex example | 120° | 60° | IN: interior |
| Reflex example | 240° | 60° | OUT: exterior |
| Flat seam | 180° | 90° | Square cut |

The tool setting is `min(delta, 360° - delta) / 2`. Relative to the exterior
reference surface, clay thickness extends inward. The signed displacement of
the interior edge is `d = working_thickness * cot(delta / 2)`. Positive d insets
the interior face; negative d extends it beyond the exterior reference. At 6 mm
thickness the examples above give +3.4641 mm and -3.4641 mm respectively.
Base dimensions and apex offsets receive shrinkage scaling once; slab-roller
thickness is already a working-clay dimension.

The PDF cover and cutting guide illustrate the sections. On transformed panels:

- **Solid outline:** raw blank, extended wherever a reflex joint needs material.
- **Dash-dot outline:** final exterior reference surface, used for dimensions.
- **Dashed outline:** final interior surface after beveling.
- **IN / OUT:** bevel with that face up so the wire removes upper waste. Mixed
  panels require turning the clay over between the two sets of bevels. The
  interior-view template and its exterior view retain matching edge labels.

Every reusable cutout carries its panel ID and MAKE quantity. Separate assembly
sheets map each joint Jxxx to its two panel instances and template edge labels;
F001.1 retains its source face F001. Front/back previews mirror the layout while
keeping text upright. Save project writes version 2 JSON with geometry and
registry versions; Load accepts that format and legacy parameter-only projects.

**Physical validation is pending.** Transformed exports are explicitly marked
experimental. Use **Download 60° test coupons** before cutting a full set: print
at 100%, verify the ruler, cut two IN coupons and two OUT coupons in scrap at
the stated slab thickness, and dry-fit both joints. IN should make a 120° interior
joint, OUT a 240° interior joint. Check that both exterior reference edges meet
and the inner edges close. The coupon uses working dimensions directly and
does not apply project shrinkage. Clay deformation, wire kerf, assembly access
and firing behavior are not simulated.

Surface validation rejects open/nonmanifold meshes, bad winding, degenerate
panels and self-intersections. Transformed designs also check intersections of
the actual finite-thickness mitered panel solids. A valid surface can still fail
this fabrication check: high-valence corners in cuboctahedron and
rhombicuboctahedron can require additional corner relief, even where the base
surface is untouched. Such edits remain inspectable but their exports are
blocked. Corner-relief design is not implemented. Original Phase 1 convex
exports retain their prior behavior; their preservation does not certify these
multi-face corners physically.

Phase 1 compatibility is covered by frozen PDF hashes for all 18 default solids;
their PDF bytes remain unchanged. Phase 2 extends the mesh and export pipeline
without replacing the original convex template path. Self-intersecting star
polyhedra, a stella-octangula exterior-boundary construction, general CSG,
noncentral apices and automatic assembly sequencing remain outside this release.

Generate a one-face calibration project locally:

```bash
PYTHONPATH=backend uv run python -m solids \
  --preset excavated-cube-single --edge 120 --offset 20 --thickness 6 \
  --output artifacts/excavated-cube-single-120mm.pdf
```

This example has nine panels and 16 joints. The four triangular panels have
reference lengths 120 mm, 87.17798 mm and 87.17798 mm. Their reflex joints use
77.07903° with the exterior up. All-face excavation at the same depth has 24
triangles, 36 joints and one reusable template.

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
if they cannot fit legibly. Phase 1 screen annotations are enlarged for
readability; transformed previews use the printable annotation positions.
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
vector paths and text using PyMuPDF. Phase 2 adds analytic signed joints, miter
solid contact/overlap, all seven presets, variable edge lengths, stable face and
joint IDs, shrinkage, surface rejection, thickness rejection, assembly references,
calibration coupons and byte-identical Phase 1 PDF regressions.

With the Docker app running, browser QA can use a disposable container. First
install frontend dependencies with `npm ci` in `frontend`, then run from the
repository root:

```bash
docker run --rm --init --shm-size=1g --network solids_default \
  --user "$(id -u):$(id -g)" -e STUDIO_URL=http://studio:8000 \
  -v "$PWD:/work" -w /work/frontend \
  mcr.microsoft.com/playwright:v1.64.1-noble npm run test:browser
```

Run the same command with `npm run test:phase2` to cover transformed recipes,
3D face selection, per-face/equivalent-face editing, front/back previews,
versioned and legacy project loading, coupons and fabrication rejection.

Run it with `npm run test:seo` to check raw response metadata, no-JavaScript
content, the standalone guide, social PNG dimensions, JSON-LD, sitemap, robots,
canonical routing, keyboard anchor focus, saved preferences and hydration.

The browser package is pinned to 1.64.1; update the image tag with it. On a host
with Chromium system dependencies, `npx playwright install chromium` then
`npm run test:browser` also works. QA covers parameters, previews, persistence,
edge details, downloads, errors, the guide, mobile overflow, JS errors, and
absence of external runtime requests. Screenshots and test exports are saved
under ignored `artifacts/browser/`.

## Production on silicide

Public hostname: **https://solids.tobiasbrownheft.xyz**, without login. The first
release was deployed from commit `217db66` on 2026-10-18 at `/srv/solids`.
`compose.production.yaml` uses `traefik-public`, existing
opt-in discovery labels, the `le` certificate resolver, shared rate-limit/security
middleware, and an explicit HTTP redirect. It publishes no host port.

Keep Cloudflare proxying enabled (orange cloud), with SSL/TLS set to Full
(strict). Traefik obtains and renews the Let's Encrypt origin certificate.
The existing origin firewall requires requests to pass through Cloudflare.

The `.xyz` apex is a proxied CNAME to `parsetrail.com`, whose A record the
existing DDNS service updates. `solids`, `turing` and `www` are proxied CNAMEs
to `tobiasbrownheft.xyz`. Both zones are in the same Cloudflare account.
Cloudflare's CNAME flattening permits the apex alias alongside the zone's
SOA, NS and TXT records. All these sites therefore follow the existing DDNS
updates without another service or token. New subdomains on this server can
follow the same pattern; Traefik still needs a router for each application.

For updates after committing and pushing the desired version:

```bash
ssh tbrownhe@silicide
cd /srv/solids
git pull --ff-only
docker compose -f compose.production.yaml config --quiet
docker build --network=host -t solids-studio .
docker compose -f compose.production.yaml up -d --no-build --wait
docker compose -f compose.production.yaml ps
curl --fail https://solids.tobiasbrownheft.xyz/api/health
```

The first build stalled during npm installation with default BuildKit networking;
host networking completed successfully. The explicit build command above uses
that workaround only during image creation. The running service joins only the
shared Traefik network. Do not start the local `compose.yaml` on the server.

Inspect application logs with
`docker compose -f compose.production.yaml logs --tail=100 studio`.
The app has no persistent server-side user data; project files and browser
preferences remain on the user's device.

## Search and sharing

`npm run build` creates the Vite bundle and prerenders the homepage using React
at build time. The client hydrates the same initial markup, then restores saved
parameters. The 3D viewer loads separately. FastAPI serves the completed HTML;
there is no Node rendering process in production. The guide at
`/guide/slab-polyhedra/` is fully static and needs no JavaScript. Its short URL
redirects permanently to the canonical trailing-slash URL; unknown pages stay 404.
Cloudflare may append its configured analytics beacon to the public HTML; the
guide's content and navigation do not depend on it. The SEO test distinguishes
that edge injection from application JavaScript.

`frontend/src/seo.ts` owns titles, descriptions, canonical URLs, Open Graph,
Twitter cards and JSON-LD. `Editorial.tsx` contains the homepage prose and guide.
The build emits robots.txt and a sitemap containing only the homepage and guide.
Cloudflare can prepend its managed robots policy; preserve the zone's existing
crawler controls. HTML and crawler files revalidate; Vite's fingerprinted assets
are cached for one year. Social images and icons have a one-hour browser cache.

The social card is an original illustration from registry geometry, not a photo
of a completed ceramic piece. The public PNG is 1200 × 630; its vector source
is kept separately. To regenerate it after changing the artwork or branding:

```bash
PYTHONPATH=backend uv run python scripts/generate-social.py
docker run --rm --init --shm-size=1g --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" -w /work/frontend \
  mcr.microsoft.com/playwright:v1.64.1-noble node scripts/render-social.mjs
```

Commit the generated public PNG/SVG and icon files; deployment does not need a
browser to build the app. Replace the illustration with authentic ceramic photos
when available, keeping image URLs/metadata and page copy independently editable.
Add descriptive alt text and dimensions to future gallery images, lazy-load
below-fold images, and include a real example's dimensions, joins and outcomes.
There is currently no gallery or automatically generated per-solid content.

Owner actions after deployment:

1. Open [Google Search Console](https://search.google.com/search-console/).
   An already verified `tobiasbrownheft.xyz` Domain property covers this subdomain.
   For separate reporting, add the URL-prefix property
   `https://solids.tobiasbrownheft.xyz/`. Retain the existing DNS verification TXT.
2. Submit `https://solids.tobiasbrownheft.xyz/sitemap.xml`. Inspect the homepage
   and `/guide/slab-polyhedra/` with URL Inspection, run the live test and request
   indexing. Monitor indexing and search queries; submission does not guarantee
   inclusion or rankings.
3. Add the site in [Bing Webmaster Tools](https://www.bing.com/webmasters/),
   importing the verified Search Console property if desired, and submit the
   same sitemap. No anonymous sitemap-ping endpoint is used.
4. Recheck the public pages with the
   [Schema Markup Validator](https://validator.schema.org/) when metadata changes.
   Generic WebApplication/Article markup describes real content; it has no
   fabricated reviews, ratings or promised FAQ rich results.

Reference instructions: [Search Console property coverage](https://support.google.com/webmasters/answer/34592),
[URL Inspection](https://support.google.com/webmasters/answer/9012289), and
[Bing site verification/import](https://www.bing.com/webmasters/help/add-and-verify-site-12184f8b).
