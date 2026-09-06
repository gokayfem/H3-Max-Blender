import os as _os
import sys as _sys

_vendor_dir = _os.path.join(_os.path.dirname(__file__), "vendor")
if _os.path.isdir(_vendor_dir) and _vendor_dir not in _sys.path:
    _sys.path.insert(0, _vendor_dir)

import bpy

from . import branding as _branding
from . import live_preview as _live_preview
from . import live_stream as _live_stream
from . import live_grid as _live_grid
from .app import (
    FAL_PT_3D_JobsPanel,
    FAL_PT_3D_MainPanel,
    FAL_PT_VSE_JobsPanel,
    FAL_PT_VSE_MainPanel,
    FalAI3DSceneProperties,
    FalAIVSESceneProperties,
)
from .controllers import FalController
from .controllers import advanced_params as _advanced_params
from .job_queue import JobManager
from .preferences import FAL_OT_OpenOutputFolder, FalPreferences


def register() -> None:
    """
    Register the fal.ai addon.
    """
    _branding.register()
    _advanced_params.register()
    bpy.utils.register_class(FAL_OT_OpenOutputFolder)
    bpy.utils.register_class(FalPreferences)
    bpy.utils.register_class(FalAI3DSceneProperties)
    bpy.utils.register_class(FalAIVSESceneProperties)
    bpy.types.Scene.fal_3d = bpy.props.PointerProperty(type=FalAI3DSceneProperties)
    bpy.types.Scene.fal_vse = bpy.props.PointerProperty(type=FalAIVSESceneProperties)
    bpy.utils.register_class(FAL_PT_3D_MainPanel)
    bpy.utils.register_class(FAL_PT_VSE_MainPanel)
    FalController.register_all(
        parent_id_3d=FAL_PT_3D_MainPanel.bl_idname,
        parent_id_vse=FAL_PT_VSE_MainPanel.bl_idname,
        parent_props_alias_3d="fal_3d",
        parent_props_alias_vse="fal_vse",
    )
    bpy.utils.register_class(FAL_PT_3D_JobsPanel)
    bpy.utils.register_class(FAL_PT_VSE_JobsPanel)
    _live_preview.register()
    _live_stream.register()
    _live_grid.register()


def unregister() -> None:
    """
    Unregister the fal.ai addon.
    """
    _live_grid.unregister()
    _live_stream.unregister()
    _live_preview.unregister()
    _advanced_params.unregister()
    bpy.utils.unregister_class(FAL_OT_OpenOutputFolder)
    bpy.utils.unregister_class(FalPreferences)
    bpy.utils.unregister_class(FalAI3DSceneProperties)
    bpy.utils.unregister_class(FalAIVSESceneProperties)
    if hasattr(bpy.types.Scene, "fal_3d"):
        del bpy.types.Scene.fal_3d
    if hasattr(bpy.types.Scene, "fal_vse"):
        del bpy.types.Scene.fal_vse
    bpy.utils.unregister_class(FAL_PT_3D_MainPanel)
    bpy.utils.unregister_class(FAL_PT_VSE_MainPanel)
    FalController.unregister_all()
    bpy.utils.unregister_class(FAL_PT_3D_JobsPanel)
    bpy.utils.unregister_class(FAL_PT_VSE_JobsPanel)
    JobManager.reset()
    _branding.unregister()
