from abc import ABCMeta
from typing import ClassVar

import bpy

from ..utils import snake_case
from .operators import FalOperator
from .ui import FalControllerPanel


class FalController(metaclass=ABCMeta):
    """Base class for all fal.ai controller integrations in Blender."""

    enabled: ClassVar[bool] = True
    display_name: ClassVar[str | None] = None
    description: ClassVar[str | None] = None
    icon: ClassVar[str] = "FILE_IMAGE"
    operator_class: ClassVar[type[FalOperator]]
    properties_class: ClassVar[type[bpy.types.PropertyGroup]]
    panel_3d: ClassVar[FalControllerPanel | None] = None
    panel_vse: ClassVar[FalControllerPanel | None] = None

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if the controller is available.
        """
        return (
            getattr(cls, "properties_class", None) is not None
            and getattr(cls, "operator_class", None) is not None
            and cls.enabled
        )

    @classmethod
    def is_3d_panel_available(cls) -> bool:
        """
        Check if the 3D panel is available.
        """
        return cls.panel_3d is not None

    @classmethod
    def is_vse_panel_available(cls) -> bool:
        """
        Check if the VSE panel is available.
        """
        return cls.panel_vse is not None

    @classmethod
    def get_display_name(cls) -> str:
        """
        Return the display name for the controller.
        """
        return cls.display_name or cls.__name__

    @classmethod
    def get_description(cls) -> str:
        """
        Return the description for the controller.
        """
        return cls.description or ""

    @classmethod
    def get_props_alias(cls) -> str:
        """
        Return the alias for the properties class.
        """
        return f"{cls.__name__.lower()}_props"

    @classmethod
    def operator(cls) -> type[bpy.types.Operator]:
        """
        Return the operator class for the controller.
        """
        if getattr(cls, "operator_class", None) is None:
            raise NotImplementedError("operator_class must be set")
        return cls.operator_class.operator(
            props_alias=cls.get_props_alias(),
        )

    @classmethod
    def create_panel_class(
        cls,
        ui: FalControllerPanel,
        space_type: str,
        parent_id: str,
        parent_props_alias: str,
    ) -> type[bpy.types.Panel]:
        """
        Return the panel class for the controller.
        """
        operator_class = cls.operator()

        class Panel(bpy.types.Panel):
            """Dynamically generated panel for a FalController."""

            bl_idname = f"FAL_PT_{space_type.upper()}_{snake_case(cls.__name__)}"
            bl_label = getattr(operator_class, "label", operator_class.__name__)
            bl_description = str(
                getattr(operator_class, "description", operator_class.__doc__)
            )
            bl_space_type = space_type
            bl_region_type = "UI"
            bl_category = "fal.ai"
            bl_parent_id = parent_id

            @classmethod
            def poll(panel_cls, context: bpy.types.Context) -> bool:
                """Return whether this panel should be visible."""
                return (
                    cls.is_available()
                    and getattr(context.scene, parent_props_alias).active_controller
                    == cls.__name__
                )

            def draw(self, context: bpy.types.Context) -> None:
                """Draw the panel UI elements."""
                layout = self.layout
                props = getattr(context.scene, cls.get_props_alias())
                ui.draw(
                    layout,
                    context,
                    props,
                    operator_name=cls.operator_class.get_name(),
                    operator_icon=cls.icon,
                )

        return Panel

    @classmethod
    def get_panel_3d(
        cls,
        parent_id: str,
        parent_props_alias: str,
    ) -> type[bpy.types.Panel]:
        """
        Return the 3D panel class for the controller.
        """
        if cls.panel_3d is None:
            raise NotImplementedError("panel_3d must be set")
        if getattr(cls, "_panel_3d_class", None) is None:
            cls._panel_3d_class = cls.create_panel_class(
                ui=cls.panel_3d,
                space_type="VIEW_3D",
                parent_id=parent_id,
                parent_props_alias=parent_props_alias,
            )
        return cls._panel_3d_class

    @classmethod
    def get_panel_vse(
        cls,
        parent_id: str,
        parent_props_alias: str,
    ) -> type[bpy.types.Panel]:
        """
        Return the VSE panel class for the controller.
        """
        if cls.panel_vse is None:
            raise NotImplementedError("panel_vse must be set")
        if getattr(cls, "_panel_vse_class", None) is None:
            cls._panel_vse_class = cls.create_panel_class(
                ui=cls.panel_vse,
                space_type="SEQUENCE_EDITOR",
                parent_id=parent_id,
                parent_props_alias=parent_props_alias,
            )
        return cls._panel_vse_class

    @classmethod
    def register_properties(cls) -> None:
        """
        Register the properties class for the controller.
        """
        if getattr(cls, "properties_class", None) is None:
            raise NotImplementedError("properties_class must be set")
        bpy.utils.register_class(cls.properties_class)

    @classmethod
    def unregister_properties(cls) -> None:
        """
        Unregister the properties class for the controller.
        """
        if getattr(cls, "properties_class", None) is None:
            raise NotImplementedError("properties_class must be set")
        bpy.utils.unregister_class(cls.properties_class)

    @classmethod
    def register_operator(cls) -> None:
        """
        Register the operator class for the controller.
        """
        if getattr(cls, "operator_class", None) is None:
            raise NotImplementedError("operator_class must be set")
        bpy.utils.register_class(cls.operator())

    @classmethod
    def unregister_operator(cls) -> None:
        """
        Unregister the operator class for the controller.
        """
        operator_cls = cls.operator_class
        if hasattr(operator_cls, "_operator_class"):
            bpy.utils.unregister_class(operator_cls._operator_class)
            operator_cls.clear_operator_cache()

    @classmethod
    def register_panel_3d(cls, parent_id: str, parent_props_alias: str) -> None:
        """
        Register the 3D panel class for the controller.
        """
        if cls.panel_3d is not None:
            bpy.utils.register_class(
                cls.get_panel_3d(
                    parent_id=parent_id,
                    parent_props_alias=parent_props_alias,
                )
            )

    @classmethod
    def register_panel_vse(cls, parent_id: str, parent_props_alias: str) -> None:
        """
        Register the VSE panel class for the controller.
        """
        if cls.panel_vse is not None:
            bpy.utils.register_class(
                cls.get_panel_vse(
                    parent_id=parent_id,
                    parent_props_alias=parent_props_alias,
                )
            )

    @classmethod
    def unregister_panel_3d(cls) -> None:
        """
        Unregister the 3D panel class for the controller.
        """
        if hasattr(cls, "_panel_3d_class"):
            bpy.utils.unregister_class(cls._panel_3d_class)
            del cls._panel_3d_class

    @classmethod
    def unregister_panel_vse(cls) -> None:
        """
        Unregister the VSE panel class for the controller.
        """
        if hasattr(cls, "_panel_vse_class"):
            bpy.utils.unregister_class(cls._panel_vse_class)
            del cls._panel_vse_class

    @classmethod
    def register_properties_pointer(cls) -> None:
        """
        Register the properties pointer for the controller.
        """
        if getattr(cls, "properties_class", None) is None:
            raise NotImplementedError("properties_class must be set")
        setattr(
            bpy.types.Scene,
            cls.get_props_alias(),
            bpy.props.PointerProperty(type=cls.properties_class),
        )

    @classmethod
    def unregister_properties_pointer(cls) -> None:
        """
        Unregister the properties pointer for the controller.
        """
        if getattr(cls, "properties_class", None) is None:
            raise NotImplementedError("properties_class must be set")
        delattr(bpy.types.Scene, cls.get_props_alias())

    @classmethod
    def register(
        cls,
        parent_id_3d: str,
        parent_props_alias_3d: str,
        parent_id_vse: str,
        parent_props_alias_vse: str,
    ) -> None:
        """
        Register the controller.
        """
        if not cls.is_available():
            return
        cls.register_properties()
        cls.register_operator()
        cls.register_panel_3d(
            parent_id=parent_id_3d, parent_props_alias=parent_props_alias_3d
        )
        cls.register_panel_vse(
            parent_id=parent_id_vse, parent_props_alias=parent_props_alias_vse
        )
        cls.register_properties_pointer()

    @classmethod
    def unregister(cls) -> None:
        """
        Unregister the controller.
        """
        if not cls.is_available():
            return
        cls.unregister_properties()
        cls.unregister_operator()
        cls.unregister_panel_3d()
        cls.unregister_panel_vse()
        cls.unregister_properties_pointer()

    @classmethod
    def _create_dispatch_panel_class(
        cls,
        space_type: str,
        parent_id: str,
        parent_props_alias: str,
        panel_attr: str,
    ) -> type[bpy.types.Panel]:
        """Create a single dispatch panel that renders the active controller's UI.

        Instead of one Panel per controller (toggled via poll()), a single
        headerless panel looks up the active controller and delegates to its
        FalControllerPanel.draw().  This avoids a Blender quirk where
        child-panel visibility doesn't refresh in some editor types (e.g.
        SEQUENCE_EDITOR) when poll() transitions from False to True.
        """

        class DispatchPanel(bpy.types.Panel):
            bl_idname = f"FAL_PT_{space_type.upper()}_active_controller"
            bl_label = "Controller"
            bl_space_type = space_type
            bl_region_type = "UI"
            bl_category = "fal.ai"
            bl_parent_id = parent_id
            bl_options = {"HIDE_HEADER"}

            def draw(self, context: bpy.types.Context) -> None:
                layout = self.layout
                active_name = getattr(
                    context.scene, parent_props_alias
                ).active_controller

                for subcls in cls.__subclasses__():
                    if subcls.__name__ != active_name or not subcls.is_available():
                        continue
                    ui = getattr(subcls, panel_attr, None)
                    if ui is None:
                        break
                    props = getattr(context.scene, subcls.get_props_alias())
                    ui.draw(
                        layout,
                        context,
                        props,
                        operator_name=subcls.operator_class.get_name(),
                        operator_icon=subcls.icon,
                    )
                    break

        return DispatchPanel

    @classmethod
    def register_all(
        cls,
        parent_id_3d: str,
        parent_props_alias_3d: str,
        parent_id_vse: str,
        parent_props_alias_vse: str,
    ) -> None:
        """
        Register all controllers and create dispatch panels.
        """
        for subcls in cls.__subclasses__():
            if subcls.is_available():
                subcls.register_properties()
                subcls.register_operator()
                subcls.register_properties_pointer()

        cls._dispatch_panel_3d_class = cls._create_dispatch_panel_class(
            space_type="VIEW_3D",
            parent_id=parent_id_3d,
            parent_props_alias=parent_props_alias_3d,
            panel_attr="panel_3d",
        )
        bpy.utils.register_class(cls._dispatch_panel_3d_class)

        cls._dispatch_panel_vse_class = cls._create_dispatch_panel_class(
            space_type="SEQUENCE_EDITOR",
            parent_id=parent_id_vse,
            parent_props_alias=parent_props_alias_vse,
            panel_attr="panel_vse",
        )
        bpy.utils.register_class(cls._dispatch_panel_vse_class)

    @classmethod
    def unregister_all(cls) -> None:
        """
        Unregister all controllers and dispatch panels.
        """
        if hasattr(cls, "_dispatch_panel_3d_class"):
            bpy.utils.unregister_class(cls._dispatch_panel_3d_class)
            del cls._dispatch_panel_3d_class
        if hasattr(cls, "_dispatch_panel_vse_class"):
            bpy.utils.unregister_class(cls._dispatch_panel_vse_class)
            del cls._dispatch_panel_vse_class

        for subcls in cls.__subclasses__():
            if subcls.is_available():
                subcls.unregister_properties_pointer()
                subcls.unregister_operator()
                subcls.unregister_properties()

    @classmethod
    def enumerate(
        cls,
        for_3d_panel: bool = False,
        for_vse_panel: bool = False,
    ) -> list[tuple[str, str, str]]:
        """
        Returns a list of all available controllers.
        """
        unique_id = 0

        def _get_unique_id() -> int:
            nonlocal unique_id
            unique_id += 1
            return unique_id

        return [
            (
                subcls.__name__,
                subcls.get_display_name(),
                subcls.get_description(),
                subcls.icon,
                _get_unique_id(),
            )
            for subcls in cls.__subclasses__()
            if subcls.is_available()
            and (
                (for_3d_panel and subcls.is_3d_panel_available())
                or (for_vse_panel and subcls.is_vse_panel_available())
                or (not for_3d_panel and not for_vse_panel)
            )
        ]
