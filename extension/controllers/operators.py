from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import ClassVar

import bpy

from ..utils import snake_case
from .advanced_params import get_advanced_params_dict


class FalOperator(metaclass=ABCMeta):
    """Abstract base class for fal.ai Blender operators."""

    label: ClassVar[str]
    description: ClassVar[str]
    _operator_class: ClassVar[type[bpy.types.Operator]]
    _operator_instance: bpy.types.Operator

    def __init__(self, operator_instance: bpy.types.Operator) -> None:
        """Initialize with a reference to the Blender operator instance."""
        self._operator_instance = operator_instance

    @classmethod
    def enabled(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """
        Check if the operator is enabled.
        """
        return True

    @classmethod
    def needs_confirm(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> bool:
        """Return True to show an "Are you sure?" dialog before running.

        Video generation (render animation, t2v, i2v) opts in because a single
        job can cost several dollars; cheaper image/audio/3D paths don't.
        """
        return False

    @classmethod
    def confirm_title(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> str:
        """Title shown in the confirmation dialog."""
        return "Submit video generation?"

    @classmethod
    def confirm_message(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> str:
        """Body shown in the confirmation dialog — typically model and size."""
        return "This will submit a paid generation job to fal.ai."

    @classmethod
    def confirm_button(
        cls, context: bpy.types.Context, props: bpy.types.PropertyGroup
    ) -> str:
        """Label for the confirm button."""
        return "Generate"

    @classmethod
    def get_name(cls) -> str:
        """
        Return the name of the operator.
        """
        return f"fal.{snake_case(cls.__name__)}"

    def modal(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event,
    ) -> set[str]:
        """
        Modal handler for the operator.
        """
        print(
            "modal() called but not implemented - you should implement this in your subclass if you want to use modal operators"
        )
        return {"PASS_THROUGH"}

    def report(self, levels: set[str], message: str) -> None:
        """
        Report a message to the user.
        """
        self._operator_instance.report(levels, message)

    @staticmethod
    def with_advanced_params(params: dict, props: bpy.types.PropertyGroup) -> dict:
        """Return ``params`` merged with the user's advanced parameters.

        Advanced params override model params, so power users can inject or
        replace any field the SDK accepts.
        """
        return {**params, **get_advanced_params_dict(props)}

    @abstractmethod
    def __call__(
        self,
        context: bpy.types.Context,
        props: bpy.types.PropertyGroup,
        event: bpy.types.Event | None = None,
        invoke: bool = False,
    ) -> set[str]:
        """Execute the operator logic and return a Blender status set."""
        pass

    @classmethod
    def clear_operator_cache(cls) -> None:
        """Remove the cached operator class so it can be re-created on re-register."""
        if hasattr(cls, "_operator_class"):
            delattr(cls, "_operator_class")

    @classmethod
    def operator(
        cls,
        props_alias: str,
    ) -> bpy.types.Operator:
        """
        Dynamically create a new operator class that wraps the operator.
        """
        if not hasattr(cls, "_operator_class"):

            class Operator(bpy.types.Operator):
                """Blender operator wrapper generated for a FalOperator subclass."""

                bl_idname = cls.get_name()
                bl_label = getattr(cls, "label", cls.__name__)
                bl_description = str(getattr(cls, "description", cls.__doc__))
                bl_options = {"REGISTER", "UNDO"}

                @classmethod
                def poll(operator_cls, context: bpy.types.Context) -> bool:
                    """Return whether the operator can be executed in the current context."""
                    props = getattr(context.scene, props_alias)
                    return cls.enabled(context, props)

                def _get_operator_instance(self) -> FalOperator:
                    """Return the cached FalOperator instance, creating it if needed."""
                    if not hasattr(self, "_operator_instance"):
                        self._operator_instance = cls(self)
                    return self._operator_instance

                def execute(self, context: bpy.types.Context) -> set[str]:
                    """Execute the operator.

                    When re-entered after a confirm dialog, route through the
                    invoke path — the modal render operator rejects
                    ``invoke=False``, and the post-dialog event reference
                    would be stale anyway.
                    """
                    props = getattr(context.scene, props_alias)
                    if getattr(self, "_fal_confirmed", False):
                        self._fal_confirmed = False
                        return self._get_operator_instance()(
                            context, props, None, invoke=True
                        )
                    return self._get_operator_instance()(context, props)

                def invoke(
                    self, context: bpy.types.Context, event: bpy.types.Event
                ) -> set[str]:
                    """Invoke the operator with the triggering event.

                    If the controller opts into confirmation, show a dialog
                    first; on OK Blender calls back into execute(), which
                    re-enters the invoke path using the stashed event.
                    """
                    props = getattr(context.scene, props_alias)
                    if cls.needs_confirm(context, props):
                        self._fal_confirmed = True
                        wm = context.window_manager
                        return wm.invoke_confirm(
                            self,
                            event,
                            title=cls.confirm_title(context, props),
                            message=cls.confirm_message(context, props),
                            confirm_text=cls.confirm_button(context, props),
                            icon="INFO",
                        )
                    return self._get_operator_instance()(
                        context, props, event, invoke=True
                    )

                def modal(
                    self, context: bpy.types.Context, event: bpy.types.Event
                ) -> set[str]:
                    """Handle modal events during long-running operations."""
                    props = getattr(context.scene, props_alias)
                    return self._get_operator_instance().modal(context, props, event)

            cls._operator_class = Operator
        return cls._operator_class
