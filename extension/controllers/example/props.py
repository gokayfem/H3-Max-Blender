import bpy


class FalExamplePropertyGroup(bpy.types.PropertyGroup):
    """
    Example property group.
    """

    example_property: bpy.props.StringProperty(
        name="Example Property",
        description="This is an example property",
        default="Example",
    )
