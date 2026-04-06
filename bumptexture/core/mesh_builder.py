"""
mesh_builder.py
Creates a MeshBody in the active Fusion 360 component from displaced vertex data,
then automatically triggers the Mesh → BRep conversion command.
"""

import adsk.core
import adsk.fusion
import traceback
import time
from typing import List, Optional


def build_mesh_and_convert(
    component: adsk.fusion.Component,
    coords: List[float],
    indices: List[int],
    normals: List[float],
    auto_convert: bool = True
) -> Optional[adsk.fusion.MeshBody]:
    """
    Create a MeshBody from vertex data, then optionally trigger BRep conversion.

    Args:
        component:    Target component where the mesh body will be created.
        coords:       Flat vertex coordinate array [x0,y0,z0, ...].
        indices:      Flat triangle index array [i0,i1,i2, ...].
        normals:      Flat normal array [nx0,ny0,nz0, ...].
        auto_convert: If True, execute ParaMeshConvertCommand after creation.

    Returns:
        The MeshBody created (before conversion).
    """
    app = adsk.core.Application.get()
    ui = app.userInterface

    try:
        mesh_body = component.meshBodies.addByTriangleMeshData(
            coords,
            indices,
            normals,
            indices   # same indices for normals
        )

        if mesh_body is None:
            raise RuntimeError('addByTriangleMeshData returned None — check geometry data.')

        mesh_body.name = 'BumpTexture_Mesh'

        if auto_convert:
            _trigger_brep_conversion(app, ui, mesh_body)

        return mesh_body

    except Exception:
        raise RuntimeError(f'Mesh creation failed:\n{traceback.format_exc()}')


def _trigger_brep_conversion(
    app: adsk.core.Application,
    ui: adsk.core.UserInterface,
    mesh_body: adsk.fusion.MeshBody
):
    """
    Select the mesh body and invoke the Mesh → BRep conversion command.
    Uses executeTextCommand with ParaMeshConvertCommand (Fusion 360 2.0+).
    """
    try:
        # Make sure we're in the right design
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            return

        # Clear selections and select our mesh body
        selections = ui.activeSelections
        selections.clear()
        selections.add(mesh_body)

        # Small yield to let Fusion process the selection
        adsk.doEvents()

        # Switch to the Mesh workspace first if needed
        # Then execute the conversion
        app.executeTextCommand('Commands.Start ParaMeshConvertCommand')

        # Wait briefly for command to start
        adsk.doEvents()

    except Exception:
        # Non-fatal: mesh was created, conversion dialog is optional
        ui.messageBox(
            'MeshBody created successfully!\n\n'
            'Auto-conversion to BRep could not be triggered automatically.\n'
            'Please use Mesh → Convert Mesh in the toolbar to convert manually.',
            'BumpTexture – Manual Step Required'
        )
