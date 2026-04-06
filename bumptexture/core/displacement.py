"""
displacement.py
Combines face_sampler + image_reader to compute displaced vertex positions.
Each surface point is offset along its normal by: amplitude * gray_value
Returns flat arrays ready for addByTriangleMeshData.
"""

import adsk.core
import adsk.fusion
from typing import List, Tuple

from core.face_sampler import sample_face
from core.image_reader import GrayscaleMap


def compute_displaced_mesh(
    face: adsk.fusion.BRepFace,
    gray_map: GrayscaleMap,
    resolution_u: int,
    resolution_v: int,
    amplitude: float,          # in cm (Fusion internal units)
    scale_u: float = 1.0,
    scale_v: float = 1.0,
    offset_u: float = 0.0,
    offset_v: float = 0.0,
    symmetric: bool = False,
    invert: bool = False
) -> Tuple[List[float], List[int], List[float]]:
    """
    Build a displaced triangle mesh from a BRep face + displacement map.

    Args:
        face:         Source BRep face.
        gray_map:     Loaded grayscale displacement map.
        resolution_u: Grid columns (U direction).
        resolution_v: Grid rows (V direction).
        amplitude:    Max displacement in cm (Fusion units).
        scale_u/v:    UV tiling scale.
        offset_u/v:   UV offset.
        symmetric:    If True, displacement is ±amplitude/2 (centered around surface).
        invert:       Flip bright/dark.

    Returns:
        coords:        Flat [x0,y0,z0, x1,y1,z1,...] for all vertices.
        indices:       Flat triangle index list.
        normals_flat:  Flat normal vectors per vertex.
    """
    points, normals, uvs = sample_face(face, resolution_u, resolution_v)

    coords: List[float] = []
    normals_flat: List[float] = []

    for i, (pt, normal, (u_norm, v_norm)) in enumerate(zip(points, normals, uvs)):
        # Apply UV transform (tile + offset)
        su = (u_norm * scale_u + offset_u) % 1.0
        sv = (v_norm * scale_v + offset_v) % 1.0

        # Sample displacement map
        gray = gray_map.sample(su, sv)
        if invert:
            gray = 1.0 - gray

        # Compute displacement amount
        if symmetric:
            disp = (gray - 0.5) * amplitude
        else:
            disp = gray * amplitude

        # Displace point along normal
        nx, ny, nz = normal.x, normal.y, normal.z
        dx = pt.x + nx * disp
        dy = pt.y + ny * disp
        dz = pt.z + nz * disp

        coords.extend([dx, dy, dz])
        normals_flat.extend([nx, ny, nz])

    # Build quad grid → 2 triangles per quad
    indices: List[int] = []
    for iv in range(resolution_v - 1):
        for iu in range(resolution_u - 1):
            # Indices for the four corners of this quad
            i00 = iv * resolution_u + iu
            i10 = iv * resolution_u + iu + 1
            i01 = (iv + 1) * resolution_u + iu
            i11 = (iv + 1) * resolution_u + iu + 1

            # Triangle 1: i00, i10, i01
            indices.extend([i00, i10, i01])
            # Triangle 2: i10, i11, i01
            indices.extend([i10, i11, i01])

    return coords, indices, normals_flat
