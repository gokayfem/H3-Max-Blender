import bpy

from .controllers import FalController
from .job_queue import JobManager
from .utils import get_request_playground_url

CONTROLLERS_3D = FalController.enumerate(for_3d_panel=True)
CONTROLLERS_VSE = FalController.enumerate(for_vse_panel=True)

if not CONTROLLERS_3D:
    CONTROLLERS_3D = [("NONE", "No Workflows Available", "")]

if not CONTROLLERS_VSE:
    CONTROLLERS_VSE = [("NONE", "No Workflows Available", "")]


def _on_active_controller_update(self, context: bpy.types.Context) -> None:
    """Force a full region redraw so child panels re-evaluate poll()."""
    if context.area:
        context.area.tag_redraw()


# ---------------------------------------------------------------------------
# Scene properties for UI state
# ---------------------------------------------------------------------------
class FalAI3DSceneProperties(bpy.types.PropertyGroup):
    """
    Per-scene properties for fal.ai 3D UI state.
    """

    # Active tab
    active_controller: bpy.props.EnumProperty(
        name="Workflow",
        items=CONTROLLERS_3D,
        default=CONTROLLERS_3D[0][0],
        update=_on_active_controller_update,
    )


class FalAIVSESceneProperties(bpy.types.PropertyGroup):
    """
    Per-scene properties for fal.ai VSE UI state.
    """

    # Active tab
    active_controller: bpy.props.EnumProperty(
        name="Workflow",
        items=CONTROLLERS_VSE,
        default=CONTROLLERS_VSE[0][0],
        update=_on_active_controller_update,
    )


# ---------------------------------------------------------------------------
# Main Panels
# ---------------------------------------------------------------------------
class FAL_PT_3D_MainPanel(bpy.types.Panel):
    """
    Main panel for fal.ai 3D UI.
    """

    bl_label = "fal.ai"
    bl_idname = "FAL_PT_3D_MainPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "fal.ai"

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the 3D viewport panel with workflow selector."""
        layout = self.layout
        scene = context.scene
        fal_3d = scene.fal_3d

        # Tab row
        row = layout.row(align=True)
        row.prop(fal_3d, "active_controller")


class FAL_PT_VSE_MainPanel(bpy.types.Panel):
    """
    Main panel for fal.ai VSE UI.
    """

    bl_label = "fal.ai"
    bl_idname = "FAL_PT_VSE_MainPanel"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_region_type = "UI"
    bl_category = "fal.ai"

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the VSE panel with workflow selector."""
        layout = self.layout
        scene = context.scene
        fal_vse = scene.fal_vse

        # Tab row
        row = layout.row(align=True)
        row.prop(fal_vse, "active_controller")


# ---------------------------------------------------------------------------
# Jobs Panel (always visible)
# ---------------------------------------------------------------------------
def _draw_error(layout: bpy.types.UILayout, error_text: str) -> None:
    """
    Draw a word-wrapped error message in the panel.

    Args:
        layout: The layout to draw the error message in.
        error_text: The error message to draw.
    """
    col = layout.column(align=True)
    # Split on structured delimiters
    parts = error_text.split(" — ")
    for part in parts:
        while len(part) > 55:
            col.label(text=part[:55], icon="BLANK1")
            part = part[55:]
        if part.strip():
            col.label(text=part, icon="BLANK1")


class BaseJobsPanel(bpy.types.Panel):
    """
    Jobs panel for fal.ai UI.
    """

    bl_label = "Active Jobs"
    bl_region_type = "UI"
    bl_category = "fal.ai"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        """
        Draw the jobs panel.
        """
        layout = self.layout
        mgr = JobManager.get()

        if not mgr.jobs and not mgr.history:
            layout.label(text="No active jobs", icon="INFO")
            return

        # Active jobs
        for job in mgr.active_jobs:
            box = layout.box()
            row = box.row()
            if job.status == "error":
                row.label(text=job.label, icon="ERROR")
            else:
                row.label(text=job.label, icon="TIME")
                row.label(text=f"{job.duration_str}")
            # Show endpoint
            row = box.row()
            row.scale_y = 0.7
            row.label(text=f"{job.endpoint_short}", icon="BLANK1")
            if job.error:
                _draw_error(box, job.error)
            elif job.progress_message:
                box.label(text=job.progress_message)

        # Recent history
        if mgr.history:
            layout.separator()
            layout.label(text="Recent:", icon="TIME")
            for job in reversed(mgr.history[-5:]):
                box = layout.box()
                # Title row with status icon and label
                row = box.row()
                icon = "CHECKMARK" if job.status == "complete" else "ERROR"
                row.label(text=job.label, icon=icon)
                # Metadata row: endpoint, time, duration
                row = box.row()
                row.scale_y = 0.7
                meta_parts = [job.endpoint_short]
                if job.start_time_str:
                    meta_parts.append(job.start_time_str)
                if job.duration_str:
                    meta_parts.append(f"({job.duration_str})")
                row.label(text=" · ".join(meta_parts), icon="BLANK1")
                # Playground link
                if job.request_id:
                    row = box.row(align=True)
                    row.scale_y = 0.9
                    playground_url = get_request_playground_url(
                        job.endpoint, job.request_id
                    )
                    op = row.operator(
                        "wm.url_open",
                        text="View on fal.ai",
                        icon="URL",
                    )
                    op.url = playground_url
                if job.error:
                    _draw_error(box, job.error)

        # Quick access to output folder
        layout.separator()
        row = layout.row()
        row.operator("fal.open_output_folder", icon="FILE_FOLDER")


class FAL_PT_3D_JobsPanel(BaseJobsPanel):
    """
    Jobs panel for fal.ai 3D UI.
    """

    bl_idname = "FAL_PT_3D_JobsPanel"
    bl_space_type = "VIEW_3D"
    bl_parent_id = FAL_PT_3D_MainPanel.bl_idname


class FAL_PT_VSE_JobsPanel(BaseJobsPanel):
    """
    Jobs panel for fal.ai VSE UI.
    """

    bl_idname = "FAL_PT_VSE_JobsPanel"
    bl_space_type = "SEQUENCE_EDITOR"
    bl_parent_id = FAL_PT_VSE_MainPanel.bl_idname
