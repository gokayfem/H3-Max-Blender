from __future__ import annotations

import os

import bpy

# For extensions, __package__ is "bl_ext.user_default.fal_ai" (or similar).
# AddonPreferences.bl_idname MUST match this, not a hardcoded string.
_addon_package = __package__


class FAL_OT_OpenOutputFolder(bpy.types.Operator):
    """Open the fal.ai output folder in the system file browser."""

    bl_idname = "fal.open_output_folder"
    bl_label = "Open Output Folder"
    bl_description = "Open the folder where generated assets are saved"

    def execute(self, context: bpy.types.Context) -> set[str]:
        from .utils import open_folder

        output_dir = get_output_dir()
        try:
            open_folder(output_dir)
            self.report({"INFO"}, f"Opened {output_dir}")
        except Exception as e:
            self.report({"ERROR"}, f"Could not open folder: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class FalPreferences(bpy.types.AddonPreferences):
    """
    Preferences for the fal.ai addon.
    """

    bl_idname = _addon_package

    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Your fal.ai API key (get one at fal.ai/dashboard/keys)",
        subtype="PASSWORD",
        default="",
    )

    output_dir: bpy.props.StringProperty(
        name="Output Directory",
        description="Override output location (leave empty to use Blender's output path)",
        subtype="DIR_PATH",
        default="",
    )

    auto_import: bpy.props.BoolProperty(
        name="Auto-Import Results",
        description="Automatically import generated assets into the scene",
        default=True,
    )

    def draw(self, context: bpy.types.Context) -> None:
        """
        Draw the preferences.
        """
        from . import branding

        layout = self.layout
        branding.draw_header(layout, scale=6.0)
        layout.prop(self, "api_key")

        env_key = os.environ.get("FAL_KEY", "")
        if not self.api_key and env_key:
            box = layout.box()
            box.label(
                text=f"Using FAL_KEY from environment (…{env_key[-4:]})",
                icon="CHECKMARK",
            )
        elif not self.api_key and not env_key:
            box = layout.box()
            box.label(text="No API key set!", icon="ERROR")
            box.label(text="Set above, or export FAL_KEY in your shell")
            box.operator("wm.url_open", text="Get a key at fal.ai").url = (
                "https://fal.ai/dashboard/keys"
            )

        row = layout.row(align=True)
        row.prop(self, "output_dir")
        row.operator("fal.open_output_folder", text="", icon="FILE_FOLDER")

        layout.prop(self, "auto_import")


def get_api_key() -> str | None:
    """
    Get the fal API key from preferences or environment.

    Returns:
        The API key if found, otherwise None.
    """
    try:
        prefs = bpy.context.preferences.addons[_addon_package].preferences
        key = prefs.api_key
    except (KeyError, AttributeError):
        key = ""
    if not key:
        key = os.environ.get("FAL_KEY", "")
    return key or None


def get_output_dir() -> str:
    """
    Get the output directory for generated assets.

    Priority:
    1. User preference override (if set)
    2. Blender scene output path directory
    3. Fallback to ~/fal.ai

    Returns:
        Absolute path to the output directory.
    """
    output_dir = ""

    # Check preference override
    try:
        prefs = bpy.context.preferences.addons[_addon_package].preferences
        output_dir = prefs.output_dir.strip()
    except (KeyError, AttributeError):
        pass

    # If no override, use Blender's scene output path
    if not output_dir:
        try:
            scene_path = bpy.context.scene.render.filepath
            if scene_path:
                # filepath might include filename pattern, get just the directory
                scene_path = bpy.path.abspath(scene_path)
                if os.path.isfile(scene_path):
                    output_dir = os.path.dirname(scene_path)
                elif scene_path.endswith(os.sep) or not os.path.splitext(scene_path)[1]:
                    # Looks like a directory path
                    output_dir = scene_path
                else:
                    # Has extension, treat as file pattern
                    output_dir = os.path.dirname(scene_path)
        except (AttributeError, RuntimeError):
            pass

    # Final fallback
    if not output_dir:
        output_dir = os.path.expanduser("~/fal.ai")

    # Expand ~ and make absolute
    output_dir = os.path.expanduser(output_dir)
    output_dir = os.path.abspath(output_dir)

    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    return output_dir
