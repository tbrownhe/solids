"""Original vector social artwork from the registry mesh; no third-party imagery.

PYTHONPATH=backend uv run python scripts/generate-social.py
Then render PNGs with frontend/scripts/render-social.mjs in Playwright.
"""
import base64
from pathlib import Path
import numpy as np
from solids.geometry import topology

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'frontend/public'
PUBLIC.joinpath('og').mkdir(exist_ok=True)
fonts={
    'StudioSerif':ROOT/'frontend/node_modules/@fontsource/dm-serif-display/files/dm-serif-display-latin-400-normal.woff2',
    'StudioSans':ROOT/'frontend/node_modules/@fontsource-variable/dm-sans/files/dm-sans-latin-wght-normal.woff2',
}
styles=''.join(f"@font-face{{font-family:{name};src:url(data:font/woff2;base64,{base64.b64encode(path.read_bytes()).decode()}) format('woff2');font-weight:{'100 900' if name=='StudioSans' else '400'};}}" for name,path in fonts.items())
mesh=topology('rhombicuboctahedron')
view=np.array([3.6,2.7,4.4]);view/=np.linalg.norm(view)
right=np.cross([0,1,0],view);right/=np.linalg.norm(right)
up=np.cross(view,right)
vertices=mesh['vertices'];scale=179/max(np.linalg.norm(v) for v in vertices)
points=np.column_stack((vertices@right,-vertices@up))*scale+[919,300]
light=np.array([-2,5,7.]);light/=np.linalg.norm(light)
polygons=[]
for fi in sorted(range(len(mesh['faces'])),key=lambda fi: vertices[mesh['faces'][fi]].mean(axis=0)@view):
    normal=mesh['normals'][fi]
    if normal@view<=0:continue
    face=mesh['faces'][fi]
    brightness=.68+.32*max(0,float(normal@light))
    color='#'+''.join(f'{round(channel*brightness):02x}' for channel in [203,151,115])
    coords=' '.join(f'{x:.2f},{y:.2f}' for x,y in points[face])
    polygons.append(f'<polygon points="{coords}" fill="{color}" stroke="#68513e" stroke-opacity=".36" stroke-width="1.2" stroke-linejoin="round"/>')

svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc">
<title id="title">Solids — Geometry, made tangible.</title><desc id="desc">An original illustrated rhombicuboctahedron in warm clay tones, beside a triangular slab panel with a 72.37 degree bevel annotation.</desc>
<defs><style>{styles}</style></defs>
<rect width="1200" height="630" fill="#f7f5f0"/>
<g fill="none" stroke="#bcc2ae" stroke-width="1" opacity=".4"><circle cx="919" cy="300" r="208" stroke-dasharray="3 7"/><path d="M678 300H1140M919 74V513"/><path d="M72 555H1128"/></g>
<g fill="#303d31"><text x="72" y="87" font-family="StudioSans" font-size="13" letter-spacing="3" fill="#657153">GEOMETRY × CERAMICS</text>
<text x="68" y="207" font-family="StudioSerif" font-size="102">Solids<tspan fill="#ad5d3b">.</tspan></text>
<text x="72" y="324" font-family="StudioSerif" font-size="48">Geometry,</text><text x="72" y="384" font-family="StudioSerif" font-size="48">made tangible.</text>
<text x="74" y="493" font-family="StudioSans" font-size="19" fill="#5e6b53">Printable templates for slab clay.</text>
<text x="74" y="590" font-family="StudioSans" font-size="14" fill="#657153">solids.tobiasbrownheft.xyz</text></g>
<g>{''.join(polygons)}</g>
<g transform="translate(610 425)"><path d="M0 105 61 0 122 105Z" fill="#f7f5f0" stroke="#6d7c5e" stroke-width="1.6"/><path d="M8 100 61 8 114 100Z" fill="none" stroke="#8e9b7c" stroke-dasharray="4 4"/><text x="61" y="67" text-anchor="middle" font-family="StudioSans" font-size="13" fill="#4e5d43">MAKE 8</text><text x="61" y="127" text-anchor="middle" font-family="StudioSans" font-size="13" fill="#985032">72.37° · IN</text></g>
</svg>'''
PUBLIC.joinpath('og/solids-social.svg').write_text(svg)
print('Created original 1200 × 630 vector social card.')
