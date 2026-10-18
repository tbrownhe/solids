"""Centered face-pyramid construction recipes, with fired-unit input offsets."""
import numpy as np

from .presets import PRESETS, SUPPORTED_BASES


def transform_mesh(base, parameters, working_scale):
    vertices=(base["vertices"]*working_scale).tolist()
    original=np.asarray(vertices)
    transforms={}
    preset=next((p for p in PRESETS if p["id"]==parameters.preset_id),None)
    if parameters.preset_id and (preset is None or preset["solid_id"]!=parameters.solid_id):
        raise ValueError("The construction preset does not match this base solid.")
    if preset:
        ids=range(1) if preset["scope"]=="one" else range(len(base["faces"]))
        transforms={f"F{i+1:03d}":{"mode":preset["mode"],"offset_mm":parameters.apex_offset_mm} for i in ids}
    transforms.update({key:value.model_dump() for key,value in parameters.face_transforms.items()})
    valid_ids={f"F{i+1:03d}" for i in range(len(base["faces"]))}
    if set(transforms)-valid_ids:
        raise ValueError("A transformation refers to a missing base face.")
    if transforms and parameters.solid_id not in SUPPORTED_BASES:
        raise ValueError("Face transformations are not yet supported for this base solid.")
    faces,records,base_faces=[],[],[]
    shrink_scale=1/(1-parameters.shrinkage_percent/100)
    active=False
    for fi,face in enumerate(base["faces"]):
        source_id=f"F{fi+1:03d}"
        transform=transforms.get(source_id,{"mode":"flat","offset_mm":0})
        offset=transform["offset_mm"]*shrink_scale
        changed=transform["mode"]!="flat" and offset>1e-7
        center=original[face].mean(axis=0)
        base_faces.append({"id":source_id,"index":fi,"sides":len(face),"transform":transform,
                           "recess_limit_mm":float(base["normals"][fi] @ center)/shrink_scale})
        if not changed:
            faces.append(list(face))
            records.append({"id":source_id,"source_face_id":source_id,"base_face_index":fi,"subface_index":None})
            continue
        active=True
        normal=base["normals"][fi]
        # Recesses must stay in their original face's radial cell. This
        # conservative bound also prevents opposite apex collapse/inversion.
        if transform["mode"]=="inward" and offset>=float(normal @ center)-1e-7:
            raise ValueError(f"Recess {source_id} reaches or passes the solid center. Reduce depth.")
        apex=center+normal*offset*(-1 if transform["mode"]=="inward" else 1)
        ai=len(vertices);vertices.append(apex.tolist())
        for i,(a,b) in enumerate(zip(face,face[1:]+face[:1])):
            faces.append([a,b,ai])
            records.append({"id":f"{source_id}.{i+1}","source_face_id":source_id,"base_face_index":fi,"subface_index":i})
    return {"vertices":np.array(vertices),"faces":faces,"face_records":records,
            "base_faces":base_faces,"active":active,"preset":preset}
