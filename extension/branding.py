"""fal.ai brand assets exposed to the Blender UI."""

import os

import bpy
import bpy.utils.previews

_BRANDING_DIR = os.path.join(os.path.dirname(__file__), "assets", "branding")
_previews = None


def register() -> None:
    global _previews
    if _previews is not None:
        return
    _previews = bpy.utils.previews.new()
    _previews.load(
        "fal_wordmark",
        os.path.join(_BRANDING_DIR, "fal-wordmark.png"),
        "IMAGE",
    )
    _previews.load(
        "fal_icon",
        os.path.join(_BRANDING_DIR, "fal-icon.png"),
        "IMAGE",
    )


def unregister() -> None:
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None


def wordmark_icon_id() -> int:
    return _previews["fal_wordmark"].icon_id if _previews else 0


def icon_id() -> int:
    return _previews["fal_icon"].icon_id if _previews else 0


def draw_header(
    layout: bpy.types.UILayout,
    scale: float = 2.5,
) -> None:
    """Render the fal wordmark centered at the top of a panel."""
    if _previews is None:
        return
    row = layout.row()
    row.alignment = "CENTER"
    row.template_icon(icon_value=wordmark_icon_id(), scale=scale)
