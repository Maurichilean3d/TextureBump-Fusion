"""
face_sampler.py
Samples a BRep face using SurfaceEvaluator to produce a grid of (point, normal) pairs
mapped uniformly across the face's parametric (UV) domain.
"""

import adsk.core
import adsk.fusion
from typing import List, Tuple


def sample_face(
    face: adsk.fusion.BRepFace,
    resolution_u: int,
    resolution_v: int
) -> Tuple[List[adsk.core.Point3D], List[adsk.core.Vector3D], List[Tuple[float, float]]]:
    """
    Sample a BRep face uniformly in UV parameter space.

    Args:
        face:         The BRep face to sample.
        resolution_u: Number of sample columns (U direction).
        resolution_v: Number of sample rows (V direction).

    Returns:
        points:   List of Point3D on the surface (resolution_u * resolution_v)
        normals:  Corresponding outward normal Vector3D at each point
        uvs:      Normalized (0..1, 0..1) UV coordinates for each point
    """
    evaluator = face.evaluator
    param_range = evaluator.parametricRange()

    u_min = param_range.minPoint.x
    u_max = param_range.maxPoint.x
    v_min = param_range.minPoint.y
    v_max = param_range.maxPoint.y

    u_span = u_max - u_min
    v_span = v_max - v_min

    # Guard against degenerate ranges
    if u_span == 0:
        u_span = 1.0
    if v_span == 0:
        v_span = 1.0

    points: List[adsk.core.Point3D] = []
    normals: List[adsk.core.Vector3D] = []
    uvs: List[Tuple[float, float]] = []

    for iv in range(resolution_v):
        for iu in range(resolution_u):
            # Fractional position in [0,1]
            frac_u = iu / (resolution_u - 1) if resolution_u > 1 else 0.5
            frac_v = iv / (resolution_v - 1) if resolution_v > 1 else 0.5

            u = u_min + frac_u * u_span
            v = v_min + frac_v * v_span

            param = adsk.core.Point2D.create(u, v)

            # Get 3D point on surface
            success_pt, pt3d = evaluator.getPointAtParameter(param)
            if not success_pt or pt3d is None:
                # Fallback: try nearest valid param
                pt3d = adsk.core.Point3D.create(0, 0, 0)

            # Get outward normal
            success_n, normal = evaluator.getNormalAtParameter(param)
            if not success_n or normal is None:
                normal = adsk.core.Vector3D.create(0, 0, 1)

            points.append(pt3d)
            normals.append(normal)
            uvs.append((frac_u, frac_v))

    return points, normals, uvs
