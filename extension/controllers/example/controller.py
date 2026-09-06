from __future__ import annotations

from ..base import FalController
from .operator import FalExampleOperator
from .props import FalExamplePropertyGroup


class FalExampleController(FalController):
    """
    Example controller.
    """

    display_name = "Example"
    description = "This is an example controller"
    icon = "FILE_IMAGE"
    operator_class = FalExampleOperator
    properties_class = FalExamplePropertyGroup
    # Optional: 3D panel configuration
    panel_3d = FalControllerPanel(
        # Order of fields in the UI
        field_orders=[
            "example_property",
        ],
        # Separators between fields in the UI
        field_separators=[
            "example_property",
        ],
        # Conditions for showing fields in the UI
        field_conditions={
            "example_property": lambda context, props: True,
        },
    )
    # Optional: VSE panel configuration
    # Can be different or the same as the 3D panel
    panel_vse = FalControllerPanel(
        field_orders=[
            "example_property",
        ],
        field_separators=[
            "example_property",
        ],
        field_conditions={
            "example_property": lambda context, props: True,
        },
    )
