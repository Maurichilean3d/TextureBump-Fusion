"""
command_handler.py
Handles the BumpTexture command lifecycle:
- CommandCreated → creates the HTML palette
- Incoming messages from the palette HTML:
    'selectFace'   → prompts user to pick a BRep face
    'applyTexture' → runs the displacement pipeline
    'previewClose' → closes palette
"""

import adsk.core
import adsk.fusion
import traceback
import os
import json
import base64

from core.image_reader import load_image, load_image_from_bytes
from core.displacement import compute_displaced_mesh
from core.mesh_builder import build_mesh_and_convert

_addin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PALETTE_ID = 'BumpTexturePalette'
# Forward slashes required: Fusion passes this path as a file:// URL to its
# Chromium WebView, which rejects backslashes (Windows os.path.join uses \).
PALETTE_HTML = os.path.join(_addin_dir, 'ui', 'palette.html').replace('\\', '/')

# Store selected face globally for async palette ↔ Python communication
_selected_face: adsk.fusion.BRepFace = None
_handlers = []


class BumpTextureCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface

            # Remove existing palette
            existing = ui.palettes.itemById(PALETTE_ID)
            if existing:
                existing.deleteMe()

            # Create HTML palette
            palette = ui.palettes.add(
                PALETTE_ID,
                'BumpTexture – Displacement Map',
                PALETTE_HTML,
                True,   # isVisible
                True,   # showCloseButton
                True,   # isResizable
                820,    # width
                680     # height
            )
            palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight

            # Register palette event handlers
            on_html = _PaletteHTMLEventHandler()
            palette.incomingFromHTML.add(on_html)
            _handlers.append(on_html)

            on_closed = _PaletteClosedHandler()
            palette.closed.add(on_closed)
            _handlers.append(on_closed)

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(
                f'BumpTexture command error:\n{traceback.format_exc()}'
            )


class _PaletteHTMLEventHandler(adsk.core.HTMLEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        global _selected_face
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            palette = ui.palettes.itemById(PALETTE_ID)

            html_args = adsk.core.HTMLEventArgs.cast(args)
            action = html_args.action
            data_str = html_args.data

            data = {}
            if data_str:
                try:
                    data = json.loads(data_str)
                except Exception:
                    data = {}

            # -----------------------------------------------------------
            # Action: Select a BRep face
            # -----------------------------------------------------------
            if action == 'selectFace':
                # Temporarily hide palette to allow viewport selection
                if palette:
                    palette.isVisible = False

                sel = ui.selectEntity('Select a face on a BRep body', 'Faces')

                if palette:
                    palette.isVisible = True

                if sel and sel.entity:
                    _selected_face = adsk.fusion.BRepFace.cast(sel.entity)
                    if _selected_face:
                        body_name = _selected_face.body.name if _selected_face.body else 'Unknown'
                        palette.sendInfoToHTML(
                            'faceSelected',
                            json.dumps({'bodyName': body_name, 'ok': True})
                        )
                    else:
                        palette.sendInfoToHTML(
                            'faceSelected',
                            json.dumps({'ok': False, 'error': 'Not a valid BRep face'})
                        )
                else:
                    palette.sendInfoToHTML(
                        'faceSelected',
                        json.dumps({'ok': False, 'error': 'No face selected'})
                    )

            # -----------------------------------------------------------
            # Action: Apply displacement texture
            # -----------------------------------------------------------
            elif action == 'applyTexture':
                if _selected_face is None:
                    palette.sendInfoToHTML('applyResult', json.dumps({
                        'ok': False,
                        'error': 'No face selected. Click "Select Face" first.'
                    }))
                    return

                # Parse parameters from palette
                texture_path = data.get('texturePath', '')
                texture_b64 = data.get('textureB64', '')
                resolution = int(data.get('resolution', 32))
                amplitude_mm = float(data.get('amplitude', 2.0))
                scale_u = float(data.get('scaleU', 1.0))
                scale_v = float(data.get('scaleV', 1.0))
                offset_u = float(data.get('offsetU', 0.0))
                offset_v = float(data.get('offsetV', 0.0))
                blur_sigma = float(data.get('blur', 0.0))
                symmetric = bool(data.get('symmetric', False))
                invert = bool(data.get('invert', False))
                auto_convert = bool(data.get('autoConvert', True))

                # Clamp resolution (keep triangles under ~8000 for BRep conversion)
                resolution = max(4, min(resolution, 64))

                # Convert mm to cm (Fusion internal units)
                amplitude_cm = amplitude_mm / 10.0

                # Load the displacement map
                gray_map = None
                if texture_b64:
                    img_data = base64.b64decode(texture_b64)
                    gray_map = load_image_from_bytes(img_data, blur_sigma)
                elif texture_path and os.path.isfile(texture_path):
                    gray_map = load_image(texture_path, blur_sigma)
                else:
                    palette.sendInfoToHTML('applyResult', json.dumps({
                        'ok': False, 'error': 'No displacement map loaded.'
                    }))
                    return

                # Run displacement pipeline
                palette.sendInfoToHTML('progress', json.dumps({'msg': 'Computing displacement...'}))

                coords, indices, normals = compute_displaced_mesh(
                    face=_selected_face,
                    gray_map=gray_map,
                    resolution_u=resolution,
                    resolution_v=resolution,
                    amplitude=amplitude_cm,
                    scale_u=scale_u,
                    scale_v=scale_v,
                    offset_u=offset_u,
                    offset_v=offset_v,
                    symmetric=symmetric,
                    invert=invert
                )

                palette.sendInfoToHTML('progress', json.dumps({'msg': 'Building mesh...'}))

                design = adsk.fusion.Design.cast(app.activeProduct)
                component = design.rootComponent

                build_mesh_and_convert(
                    component=component,
                    coords=coords,
                    indices=indices,
                    normals=normals,
                    auto_convert=auto_convert
                )

                tri_count = len(indices) // 3
                palette.sendInfoToHTML('applyResult', json.dumps({
                    'ok': True,
                    'triangles': tri_count,
                    'vertices': len(coords) // 3
                }))

            # -----------------------------------------------------------
            # Action: Close palette
            # -----------------------------------------------------------
            elif action == 'closePalette':
                if palette:
                    palette.isVisible = False

        except Exception:
            app = adsk.core.Application.get()
            ui = app.userInterface
            err = traceback.format_exc()
            palette = ui.palettes.itemById(PALETTE_ID)
            if palette:
                palette.sendInfoToHTML('applyResult', json.dumps({
                    'ok': False,
                    'error': err
                }))


class _PaletteClosedHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        global _selected_face
        _selected_face = None
