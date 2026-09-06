from __future__ import annotations

import bpy

from ..base import FalOperator


class FalExampleOperator(FalOperator):
    """
    Example operator.
    """

    label = "Example"  # text in button in UI

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """
        Return True if the operator is enabled (i.e. if the button can be clicked)
        """
        return True

    def modal(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event,
    ) -> set[str]:
        """
        Modal handler for the operator (called by Blender's render system.)
        """
        return {"PASS_THROUGH"}

    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """
        Invoke the operator.
        """
        return {"FINISHED"}
