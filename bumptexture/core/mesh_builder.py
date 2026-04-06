"""
mesh_builder.py
Creates a MeshBody in the active Fusion 360 component from displaced vertex data,
then automatically triggers the Mesh → BRep conversion command.
"""

import adsk.core
import adsk.fusion
import traceback
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
    Convert a MeshBody to BRep.
    Strategy 1: Use the convertMeshFeatures API (Fusion 360 2.0.12918+).
    Strategy 2: Fall back to executeTextCommand with selection.
    Strategy 3: Show a manual instruction message box.
    """
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        return

    # --- Strategy 1: Direct API conversion ---
    try:
        component = mesh_body.parentComponent
        convert_features = component.features.convertMeshFeatures
        convert_input = convert_features.createInput(
            mesh_body, adsk.fusion.ConvertMeshAccuracy.LowMeshAccuracy
        )
        convert_features.add(convert_input)
        return  # success
    except Exception:
        pass  # API not available in this Fusion version; try next strategy

    # --- Strategy 2: executeTextCommand with selection ---
    try:
        selections = ui.activeSelections
        selections.clear()
        selections.add(mesh_body)
        adsk.doEvents()
        app.executeTextCommand('Commands.Start ParaMeshConvertCommand')
        adsk.doEvents()
        return  # success (command launched)
    except Exception:
        pass

    # --- Strategy 3: Manual fallback ---
    ui.messageBox(
        'MeshBody "BumpTexture_Mesh" created successfully!\n\n'
        'Auto-conversion to BRep could not be triggered.\n'
        'To convert manually: select the mesh body → Mesh tab → Convert Mesh.',
        'BumpTexture – Manual Step Required'
    )
