"""Advanced parameters UI for power users.

Provides a UIList-based interface for arbitrary key-value parameters
that get merged into API requests.
"""

from __future__ import annotations

import json

import bpy

__all__ = [
    "FalAdvancedParameter",
    "FAL_UL_AdvancedParamsList",
    "FAL_OT_AddAdvancedParam",
    "FAL_OT_RemoveAdvancedParam",
    "draw_advanced_params",
    "get_advanced_params_dict",
    "advanced_params_annotations",
    "with_advanced_params",
    "ADVANCED_PARAMS_FIELDS",
]

# Field names injected by `with_advanced_params`. The controller panel's
# auto-draw loop must skip these so they don't render as normal fields —
# they're managed by the collapsible Advanced Parameters section instead.
ADVANCED_PARAMS_FIELDS: frozenset[str] = frozenset(
    {"show_advanced_params", "advanced_params", "advanced_params_index"}
)


def _resolve_props(
    context: bpy.types.Context, props_path: str
) -> bpy.types.PropertyGroup | None:
    """Resolve an RNA path (from PropertyGroup.path_from_id) against context.scene."""
    try:
        return context.scene.path_resolve(props_path)
    except (ValueError, TypeError):
        return None


class FalAdvancedParameter(bpy.types.PropertyGroup):
    """A single key-value parameter for API requests."""

    key: bpy.props.StringProperty(
        name="Key",
        description="Parameter name (e.g. 'guidance_scale')",
        default="",
    )
    value: bpy.props.StringProperty(
        name="Value",
        description="Parameter value (strings, numbers, booleans supported)",
        default="",
    )
    value_type: bpy.props.EnumProperty(
        name="Type",
        description="Value type for proper JSON encoding",
        items=[
            ("STRING", "String", "Text value"),
            ("INT", "Integer", "Whole number"),
            ("FLOAT", "Float", "Decimal number"),
            ("BOOL", "Boolean", "True/False"),
            ("JSON", "JSON", "Raw JSON (object, array, number, etc.)"),
        ],
        default="STRING",
    )


class FAL_UL_AdvancedParamsList(bpy.types.UIList):
    """UIList for displaying advanced parameters."""

    bl_idname = "FAL_UL_AdvancedParamsList"

    def draw_item(
        self,
        context: bpy.types.Context,
        layout: bpy.types.UILayout,
        data: bpy.types.AnyType,
        item: FalAdvancedParameter,
        icon: int,
        active_data: bpy.types.AnyType,
        active_property: str,
        index: int = 0,
        flt_flag: int = 0,
    ) -> None:
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.prop(item, "key", text="", emboss=False)
            row.prop(item, "value_type", text="", emboss=True)
            row.prop(item, "value", text="", emboss=False)
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=item.key or "(empty)")


class FAL_OT_AddAdvancedParam(bpy.types.Operator):
    """Add a new advanced parameter."""

    bl_idname = "fal.add_advanced_param"
    bl_label = "Add Parameter"
    bl_description = "Add a new advanced parameter"
    bl_options = {"REGISTER", "UNDO"}

    props_path: bpy.props.StringProperty(
        name="Props Path",
        description="Dotted path to the PropertyGroup on context.scene",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = _resolve_props(context, self.props_path)
        if props is None:
            self.report({"ERROR"}, f"Could not resolve props at '{self.props_path}'")
            return {"CANCELLED"}
        item = props.advanced_params.add()
        item.key = ""
        item.value = ""
        props.advanced_params_index = len(props.advanced_params) - 1
        return {"FINISHED"}


class FAL_OT_RemoveAdvancedParam(bpy.types.Operator):
    """Remove the selected advanced parameter."""

    bl_idname = "fal.remove_advanced_param"
    bl_label = "Remove Parameter"
    bl_description = "Remove the selected advanced parameter"
    bl_options = {"REGISTER", "UNDO"}

    props_path: bpy.props.StringProperty(
        name="Props Path",
        description="Dotted path to the PropertyGroup on context.scene",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = _resolve_props(context, self.props_path)
        if props is None:
            self.report({"ERROR"}, f"Could not resolve props at '{self.props_path}'")
            return {"CANCELLED"}
        idx = props.advanced_params_index
        if 0 <= idx < len(props.advanced_params):
            props.advanced_params.remove(idx)
            props.advanced_params_index = max(0, idx - 1)
        return {"FINISHED"}


def draw_advanced_params(
    layout: bpy.types.UILayout,
    props: bpy.types.PropertyGroup,
    props_path: str,
    collapsed: bool = True,
) -> None:
    """Draw the advanced parameters UI section.

    Args:
        layout: Parent layout to draw into
        props: PropertyGroup containing advanced_params CollectionProperty
        props_path: Dotted path from context.scene used by the operators to resolve props
        collapsed: Whether to start collapsed (default True)
    """
    # Collapsible header
    box = layout.box()
    row = box.row()
    row.prop(
        props,
        "show_advanced_params",
        icon="TRIA_DOWN" if props.show_advanced_params else "TRIA_RIGHT",
        icon_only=True,
        emboss=False,
    )
    row.label(text="Advanced Parameters")

    if not props.show_advanced_params:
        return

    # UIList
    row = box.row()
    row.template_list(
        FAL_UL_AdvancedParamsList.bl_idname,
        "",
        props,
        "advanced_params",
        props,
        "advanced_params_index",
        rows=3,
    )

    # Add/Remove buttons — pass props_path as an operator property
    col = row.column(align=True)
    add = col.operator(FAL_OT_AddAdvancedParam.bl_idname, icon="ADD", text="")
    add.props_path = props_path
    remove = col.operator(FAL_OT_RemoveAdvancedParam.bl_idname, icon="REMOVE", text="")
    remove.props_path = props_path


def get_advanced_params_dict(props: bpy.types.PropertyGroup) -> dict:
    """Convert advanced params collection to a dict for API requests.

    Handles type conversion based on value_type.
    """
    result = {}
    if not hasattr(props, "advanced_params"):
        return result

    for param in props.advanced_params:
        key = param.key.strip()
        if not key:
            continue

        value = param.value
        try:
            if param.value_type == "INT":
                result[key] = int(value)
            elif param.value_type == "FLOAT":
                result[key] = float(value)
            elif param.value_type == "BOOL":
                result[key] = value.lower() in ("true", "1", "yes", "on")
            elif param.value_type == "JSON":
                result[key] = json.loads(value)
            else:  # STRING
                result[key] = value
        except (ValueError, AttributeError, json.JSONDecodeError):
            # Fall back to string on conversion errors
            result[key] = value

    return result


def advanced_params_annotations() -> dict:
    """Return the three PropertyGroup annotations required to host advanced params.

    Merge into a PropertyGroup's ``__annotations__`` (see ``with_advanced_params``)
    rather than restating them inline on every group.
    """
    return {
        "show_advanced_params": bpy.props.BoolProperty(
            name="Show Advanced Parameters",
            description="Toggle visibility of advanced parameters section",
            default=False,
        ),
        "advanced_params": bpy.props.CollectionProperty(
            type=FalAdvancedParameter,
            name="Advanced Parameters",
            description="Additional API parameters for power users",
        ),
        "advanced_params_index": bpy.props.IntProperty(
            name="Advanced Parameter Index",
            default=0,
        ),
    }


def with_advanced_params(cls: type) -> type:
    """Class decorator that injects advanced-params fields into a PropertyGroup."""
    existing = cls.__dict__.get("__annotations__", {})
    cls.__annotations__ = {**existing, **advanced_params_annotations()}
    return cls


_CLASSES: tuple[type, ...] = (
    FalAdvancedParameter,
    FAL_UL_AdvancedParamsList,
    FAL_OT_AddAdvancedParam,
    FAL_OT_RemoveAdvancedParam,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
