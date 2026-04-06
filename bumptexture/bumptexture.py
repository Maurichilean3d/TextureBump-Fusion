"""
BumpTexture Add-in for Fusion 360
Applies grayscale displacement maps to BRep faces and generates BRep geometry.
Pipeline: BRep Face → UV Sampling → Displacement Map → MeshBody → BRep conversion
"""

import adsk.core
import adsk.fusion
import traceback
import os
import sys

# Ensure core package is importable
_addin_dir = os.path.dirname(os.path.abspath(__file__))
if _addin_dir not in sys.path:
    sys.path.insert(0, _addin_dir)

from ui.command_handler import BumpTextureCommandCreatedHandler

# Global list to hold event handlers (prevents garbage collection)
_handlers = []
_cmd_def = None

COMMAND_ID = 'BumpTextureCmd'
COMMAND_NAME = 'BumpTexture'
COMMAND_TOOLTIP = 'Apply a grayscale displacement map to BRep faces to generate 3D textured geometry'
WORKSPACE_ID = 'FusionSolidEnvironment'
FALLBACK_PANEL_IDS = ('SolidCreatePanel', 'SolidScriptsAddinsPanel')


def run(context):
    global _handlers, _cmd_def
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        # Clean up any existing command definition
        existing = ui.commandDefinitions.itemById(COMMAND_ID)
        if existing:
            existing.deleteMe()

        # Create command definition
        resources_path = os.path.join(_addin_dir, 'resources', 'icons')
        _cmd_def = ui.commandDefinitions.addButtonDefinition(
            COMMAND_ID,
            COMMAND_NAME,
            COMMAND_TOOLTIP,
            resources_path
        )

        # Register created handler
        on_cmd_created = BumpTextureCommandCreatedHandler()
        _cmd_def.commandCreated.add(on_cmd_created)
        _handlers.append(on_cmd_created)

        # Add button to Create panel in Solid workspace
        workspace = ui.workspaces.itemById(WORKSPACE_ID)
        if workspace:
            panel = None
            for panel_id in FALLBACK_PANEL_IDS:
                panel = workspace.toolbarPanels.itemById(panel_id)
                if panel:
                    break

            if panel:
                ctrl = panel.controls.addCommand(_cmd_def)
                ctrl.isPromotedByDefault = False
                ctrl.isPromoted = False
            elif ui:
                ui.messageBox(
                    'BumpTexture loaded, but no supported toolbar panel was found.\n'
                    'Please open the Solid workspace and reload the add-in.'
                )

        adsk.autoTerminate(False)

    except Exception:
        if ui:
            ui.messageBox(f'BumpTexture initialization failed:\n{traceback.format_exc()}')


def stop(context):
    global _handlers, _cmd_def
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        # Remove controls from all known panels
        workspace = ui.workspaces.itemById(WORKSPACE_ID)
        if workspace:
            for panel_id in FALLBACK_PANEL_IDS:
                panel = workspace.toolbarPanels.itemById(panel_id)
                if panel:
                    ctrl = panel.controls.itemById(COMMAND_ID)
                    if ctrl:
                        ctrl.deleteMe()

        # Delete command definition
        cmd_def = ui.commandDefinitions.itemById(COMMAND_ID)
        if cmd_def:
            cmd_def.deleteMe()

        _handlers = []
        _cmd_def = None

    except Exception:
        if ui:
            ui.messageBox(f'BumpTexture stop failed:\n{traceback.format_exc()}')
