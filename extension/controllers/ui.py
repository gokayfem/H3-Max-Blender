from __future__ import annotations

import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias

import bpy

from ..utils import get_endpoint_description, get_playground_url
from .advanced_params import ADVANCED_PARAMS_FIELDS, draw_advanced_params

if TYPE_CHECKING:
    from ..models.base import FalModel

ConditionFunc: TypeAlias = Callable[[bpy.types.Context, bpy.types.PropertyGroup], bool]


@dataclass
class FalControllerPanel:
    """Declarative UI layout definition for a fal.ai controller panel."""

    field_orders: list[str] = field(default_factory=list)
    field_separators: list[str] = field(default_factory=list)
    field_conditions: dict[str, ConditionFunc] = field(default_factory=dict)
    field_groupings: list[set[str]] = field(default_factory=list)
    endpoint_models: dict[str, type[FalModel]] = field(default_factory=dict)
    show_advanced_params: bool = True

    _current_group_seen: set[str] = field(default_factory=set)
    _current_group: set[str] | None = None
    _current_row: bpy.types.UILayout | None = None

    def __post_init__(self) -> None:
        """
        Post-init hook, validate field groupings.

        Fields can only be in one grouping.
        """
        seen_fields = set()
        for group in self.field_groupings:
            for field in group:
                if field in seen_fields:
                    raise ValueError(f"Field {field} is in multiple groupings")
                seen_fields.add(field)

    def _get_group_for_field(self, field_name: str) -> set[str] | None:
        """
        Get the group for a field.
        """
        for group in self.field_groupings:
            if field_name in group:
                return group
        return None

    def _flush_current_group(self) -> None:
        """
        Flush the current group.
        """
        self._current_group = None
        self._current_row = None
        self._current_group_seen.clear()

    def status_message(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> str | None:
        """
        Return the status message for the controller.
        """
        return None

    def show_field(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        field_name: str,
    ) -> bool:
        """
        Check if a field should be shown in the UI.
        """
        if not self.field_conditions or field_name not in self.field_conditions:
            return True
        return self.field_conditions[field_name](context, props)

    def draw_field(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        field_name: str,
    ) -> None:
        """
        Draw a field in the UI.
        """
        if self.show_field(context, props, field_name):
            group = self._get_group_for_field(field_name)
            if group:
                if self._current_group != group:
                    self._current_group = group
                    self._current_row = layout.row()
                    self._current_group_seen.clear()

                self._current_row.prop(props, field_name)
                self._current_group_seen.add(field_name)

                if len(self._current_group_seen) == len(group):
                    self._flush_current_group()
                    if any(field_name in self.field_separators for field_name in group):
                        layout.separator()
            else:
                layout.prop(props, field_name)
                if field_name in self.field_separators:
                    layout.separator()

    def _get_active_model(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> type[FalModel] | None:
        """Resolve the currently-visible endpoint property to its model class."""
        for field_name, model_base in self.endpoint_models.items():
            if not self.show_field(context, props, field_name):
                continue
            model_key = getattr(props, field_name, None)
            if not model_key:
                continue
            catalog = model_base.catalog()
            return catalog.get(model_key)
        return None

    def draw_endpoint_info(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        wrap_width: int = 45,
    ) -> None:
        """Display endpoint description, pricing, and playground link."""
        if not self.endpoint_models:
            return
        model = self._get_active_model(context, props)
        if model is None:
            return

        box = layout.box()

        # Description (fetched from llms.txt)
        try:
            description = get_endpoint_description(model.endpoint)
            if description:
                col = box.column(align=True)
                col.scale_y = 0.7
                for wrapped in textwrap.wrap(description, wrap_width) or [""]:
                    col.label(text=wrapped)
                box.separator()
        except Exception:
            pass

        # Pricing
        try:
            pricing = model.get_pricing()
            if pricing:
                col = box.column(align=True)
                col.scale_y = 0.7
                for line in pricing.splitlines():
                    if not line.strip():
                        continue
                    for wrapped in textwrap.wrap(line, wrap_width) or [""]:
                        col.label(text=wrapped)
        except Exception:
            pass

        # Playground link
        row = box.row()
        row.scale_y = 0.9
        op = row.operator("wm.url_open", text="Open Playground", icon="URL")
        op.url = get_playground_url(model.endpoint)

    def draw_pricing(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        wrap_width: int = 40,
    ) -> None:
        """Display pricing for the currently selected endpoint.

        DEPRECATED: Use draw_endpoint_info() instead.
        """
        self.draw_endpoint_info(layout, context, props, wrap_width)

    def draw_status(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> None:
        """
        Draw the status message for the controller.
        """
        message = self.status_message(context, props)
        if message:
            layout.label(text=message)

    def current_dimensions(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> tuple[int, int] | None:
        """Return the WxH the active model will receive, or None if not known.

        Convention: controllers surface ``use_scene_resolution`` plus
        ``width`` / ``height`` props. When ``use_scene_resolution`` is True,
        derive from the scene render settings; otherwise use the explicit
        manual values.
        """
        if getattr(props, "use_scene_resolution", False):
            scene = context.scene
            scale = scene.render.resolution_percentage / 100.0
            return (
                int(scene.render.resolution_x * scale),
                int(scene.render.resolution_y * scale),
            )
        if hasattr(props, "width") and hasattr(props, "height"):
            return int(props.width), int(props.height)
        return None

    def output_size_hint(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> str | None:
        """Return hint text when the model will reshape the requested size.

        Returns ``None`` when no active model is found, dimensions can't be
        resolved, or the effective size matches the request (no surprise to
        warn about).
        """
        model = self._get_active_model(context, props)
        if model is None or not hasattr(model, "describe_output_size"):
            return None
        dims = self.current_dimensions(context, props)
        if dims is None:
            return None
        w, h = dims
        try:
            effective = model.describe_output_size(w, h)
        except Exception:
            return None
        requested = f"{w}x{h}"
        if effective == requested:
            return None
        return f"Will generate at: {effective}"

    def draw_output_size_hint(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> None:
        """Render the output-size hint above the Generate button, if any."""
        hint = self.output_size_hint(context, props)
        if hint is None:
            return
        row = layout.row()
        row.scale_y = 0.8
        row.label(text=hint, icon="INFO")

    def draw_operator(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        operator_name: str,
        operator_icon: str,
        operator_size: float = 1.5,
    ) -> None:
        """
        Draw the operator for the controller.
        """
        row = layout.row()
        row.scale_y = operator_size
        row.operator(operator_name, icon=operator_icon)

    def draw(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        operator_name: str,
        operator_icon: str,
        operator_size: float = 1.5,
    ) -> None:
        """
        Draw the UI for the controller.
        """
        # Clear any stale group state from previous draws
        self._flush_current_group()

        # Skip the advanced-params bookkeeping fields — the collapsible
        # section below owns them; otherwise they'd render twice.
        visited_fields = set(ADVANCED_PARAMS_FIELDS)
        for field_name in self.field_orders:
            if field_name in visited_fields:
                continue
            self.draw_field(layout, context, props, field_name)
            visited_fields.add(field_name)

        for field_name in props.keys():
            if field_name in visited_fields:
                continue
            self.draw_field(layout, context, props, field_name)
            visited_fields.add(field_name)

        self.draw_endpoint_info(layout, context, props)

        # Draw advanced parameters section if enabled for this panel
        if self.show_advanced_params and hasattr(props, "advanced_params"):
            layout.separator()
            self.draw_advanced_params(layout, context, props)

        self.draw_status(layout, context, props)
        self.draw_output_size_hint(layout, context, props)
        self.draw_operator(
            layout, context, props, operator_name, operator_icon, operator_size
        )
        self._flush_current_group()

    def draw_advanced_params(
        self,
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
    ) -> None:
        """Draw the advanced parameters section."""
        # RNA path from the owning ID (the scene) — resolved operator-side via path_resolve.
        props_path = props.path_from_id()
        draw_advanced_params(layout, props, props_path)
