import argparse
from pathlib import Path

from .geometry import Parameters, make_design
from .printing import page_plan, pdf_bytes
from .transforms import PRESETS


def main():
    parser = argparse.ArgumentParser(description="Generate actual-size ceramic panel templates.")
    parser.add_argument("--solid", default=None)
    parser.add_argument("--preset", choices=[p["id"] for p in PRESETS])
    parser.add_argument("--offset", type=float, default=20, help="Apex depth/height after firing, mm")
    parser.add_argument("--edge", type=float, default=120, help="Desired fired exterior edge, mm")
    parser.add_argument("--thickness", type=float, default=6, help="Working slab-roller thickness, mm")
    parser.add_argument("--shrinkage", type=float, default=0, help="Linear cut-to-fired shrinkage, percent")
    parser.add_argument("--paper", choices=["letter", "a4", "a3"], default="letter")
    parser.add_argument("--precision", type=int, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    preset = next((p for p in PRESETS if p["id"]==args.preset),None)
    solid = args.solid or (preset["solid_id"] if preset else "rhombicuboctahedron")
    destination = args.output or Path(f"artifacts/{args.preset or solid}-{args.edge:g}mm-{args.paper}.pdf")
    try:
        design = make_design(Parameters(solid_id=solid, preset_id=args.preset, apex_offset_mm=args.offset, edge_length_mm=args.edge,
                             thickness_mm=args.thickness, shrinkage_percent=args.shrinkage,
                             page_format=args.paper, angle_precision=args.precision))
        output = pdf_bytes(design)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(output)
    print(f"{design['name']}: {design['total_faces']} faces / {design['total_edges']} edges")
    for template in design["templates"]:
        angles = " / ".join(f"{e['angle_deg']:.8f}" + (f" {e['cut_side'].upper()} UP" if design["phase2"] else "") for e in template["edges"])
        print(f"{template['id']}: {template['sides']} sides, make {template['quantity']}, tool angles {angles}")
    print(f"{page_plan(design)['page_count']} sheets, working edge {design['cut_edge_mm']:.8f} mm")
    print(destination)


if __name__ == "__main__":
    main()
