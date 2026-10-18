import argparse
from pathlib import Path

from .geometry import Parameters, make_design
from .printing import page_plan, pdf_bytes


def main():
    parser = argparse.ArgumentParser(description="Generate actual-size ceramic panel templates.")
    parser.add_argument("--solid", default="rhombicuboctahedron")
    parser.add_argument("--edge", type=float, default=120, help="Desired fired exterior edge, mm")
    parser.add_argument("--thickness", type=float, default=6, help="Working slab-roller thickness, mm")
    parser.add_argument("--shrinkage", type=float, default=0, help="Linear cut-to-fired shrinkage, percent")
    parser.add_argument("--paper", choices=["letter", "a4", "a3"], default="letter")
    parser.add_argument("--precision", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("artifacts/rhombicuboctahedron-120mm-letter.pdf"))
    args = parser.parse_args()
    try:
        design = make_design(Parameters(solid_id=args.solid, edge_length_mm=args.edge,
                             thickness_mm=args.thickness, shrinkage_percent=args.shrinkage,
                             page_format=args.paper, angle_precision=args.precision))
        output = pdf_bytes(design)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output)
    print(f"{design['name']}: {design['total_faces']} faces / {design['total_edges']} edges")
    for template in design["templates"]:
        angles = " / ".join(f"{e['angle_deg']:.8f}" for e in template["edges"])
        print(f"{template['id']}: {template['sides']} sides, make {template['quantity']}, tool angles {angles}")
    print(f"{page_plan(design)['page_count']} sheets, working edge {design['cut_edge_mm']:.8f} mm")
    print(args.output)


if __name__ == "__main__":
    main()
