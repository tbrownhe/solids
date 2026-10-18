"""Compare vector visibility with independent 3D ray/triangle intersections."""
import numpy as np
import pytest

from solids.geometry import Parameters, make_design
from solids.schematics import project_schematic, view_direction


CASES = [
    Parameters(solid_id="cube"),
    Parameters(solid_id="cube", preset_id="excavated-cube-single", apex_offset_mm=45),
    Parameters(solid_id="cube", preset_id="excavated-cube", apex_offset_mm=20),
    Parameters(solid_id="octahedron", preset_id="excavated-octahedron", apex_offset_mm=8),
    Parameters(solid_id="cube", preset_id="stellated-cube", apex_offset_mm=30),
    Parameters(solid_id="dodecahedron", preset_id="stellated-dodecahedron",
               face_transforms={"F001": {"mode": "flat"}}),
    Parameters(solid_id="snub-dodecahedron"),
]


@pytest.mark.parametrize("parameters", CASES, ids=lambda p: p.preset_id or p.solid_id)
@pytest.mark.parametrize("side", [1, -1])
def test_projected_surfaces_match_nearest_3d_ray_hits(parameters, side):
    design = make_design(parameters)
    direction = view_direction(design) * side
    view = project_schematic(design, direction)
    toward = direction / np.linalg.norm(direction)
    right = np.cross([0., 1., 0.], toward)
    right /= np.linalg.norm(right)
    up = np.cross(toward, right)
    # An exterior view must preserve handedness.
    assert np.linalg.det(np.array([right, up, toward])) == pytest.approx(1)
    vertices = np.asarray(design["vertices"])
    vertices = (vertices - vertices.mean(axis=0)) / np.ptp(vertices, axis=0).max()
    low, high = view["bounds"]
    samples = np.array([[x,y] for x in np.linspace(low[0]+.001,high[0]-.001,17)
                        for y in np.linspace(low[1]+.001,high[1]-.001,19)])
    origins = samples[:, :1] * right + samples[:, 1:] * up + toward * 10
    nearest = np.full(len(samples), np.inf)
    hits = [[] for _ in samples]
    # Raycast the actual 3D mesh; no projected clipping or face sorting here.
    for index, face in enumerate(design["faces"]):
        a = vertices[face[0]]
        for j in range(1,len(face)-1):
            b,c=vertices[face[j]],vertices[face[j+1]]
            ab,ac=b-a,c-a
            normal=np.cross(ab,ac)
            denominator=normal@toward
            if abs(denominator)<1e-10:
                continue
            distance=(origins-a)@normal/denominator
            contact=origins-distance[:,None]*toward-a
            d00,d01,d11=ab@ab,ab@ac,ac@ac
            u=(d11*(contact@ab)-d01*(contact@ac))/(d00*d11-d01*d01)
            v=(d00*(contact@ac)-d01*(contact@ab))/(d00*d11-d01*d01)
            inside=(u>=-1e-8)&(v>=-1e-8)&(u+v<=1+1e-8)
            for k in np.flatnonzero(inside):
                if distance[k]<nearest[k]-1e-8:
                    nearest[k]=distance[k];hits[k]=[index]
                elif abs(distance[k]-nearest[k])<=1e-8:
                    hits[k].append(index)
    def contains(polygon, point):
        return all((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])>=-1e-8
                   for a,b in zip(polygon,polygon[1:]+polygon[:1]))
    for point, expected in zip(samples,hits):
        actual={f["face_index"] for f in view["faces"] if any(contains(r,point) for r in f["regions"])}
        assert bool(actual)==bool(expected), (point,expected,actual)
        assert actual.issubset(set(expected)), (point,expected,actual)


def test_individual_edit_faces_the_first_view_and_appears_in_only_one_side():
    design=make_design(Parameters(solid_id="dodecahedron",preset_id="stellated-dodecahedron",
                                  face_transforms={"F001":{"mode":"flat"}}))
    direction=view_direction(design)
    index=next(i for i,r in enumerate(design["face_records"]) if r["id"]=="F001")
    front=project_schematic(design,direction)
    back=project_schematic(design,-direction)
    assert index in {f["face_index"] for f in front["faces"]}
    assert index not in {f["face_index"] for f in back["faces"]}
