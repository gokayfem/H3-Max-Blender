"""Fixed-camera image buffers for the measured four-style experiment."""
import uuid
from pathlib import Path
import bpy


def capture(session):
    original = session['scene']
    if not original.camera:
        raise ValueError('Per-style guidance requires a scene camera')
    scene = original.copy()
    colors = {o: tuple(o.color) for o in scene.objects}
    material = None
    prefix = Path(session['folder']) / ('guides-' + uuid.uuid4().hex[:10])
    try:
        scene.render.resolution_x = 832
        scene.render.resolution_y = 480
        scene.render.resolution_percentage = 100
        scene.render.use_sequencer = False
        scene.render.use_compositing = False
        scene.render.film_transparent = False
        scene.render.engine = 'BLENDER_WORKBENCH'
        sh = scene.display.shading
        sh.light = 'STUDIO'; sh.color_type = 'OBJECT'; sh.single_color = (.55,.55,.55)
        for obj in scene.objects:
            obj.color = (.16,.16,.16,1) if obj.get('h3_background') or obj.name.startswith('Ground plane') else (.55,.55,.55,1)
        sh.show_shadows = True; sh.show_cavity = True
        sh.background_type = 'WORLD'
        scene.render.image_settings.file_format = 'JPEG'
        scene.render.image_settings.quality = 94
        def render(suffix):
            path = Path(str(prefix) + suffix)
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True, scene=scene.name)
            return path.read_bytes()
        source = render('-source.jpg')
        scene.render.image_settings.file_format = 'PNG'
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        sh.light = 'FLAT'; sh.color_type = 'OBJECT'
        sh.show_shadows = False; sh.show_cavity = False
        sh.show_specular_highlight = False
        sh.background_type = 'VIEWPORT'; sh.background_color = (1,1,1)
        for obj in scene.objects:
            obj.color = (1,1,1,1) if obj.get('h3_background') or obj.name.startswith('Ground plane') else (0,0,0,1)
        mask = render('-mask.png')
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 1; scene.cycles.use_denoising = False
        material = bpy.data.materials.new('Temporary camera normals')
        material.use_nodes = True
        n=material.node_tree.nodes; l=material.node_tree.links; n.clear()
        output=n.new('ShaderNodeOutputMaterial'); em=n.new('ShaderNodeEmission')
        geo=n.new('ShaderNodeNewGeometry'); trans=n.new('ShaderNodeVectorTransform')
        trans.convert_from='WORLD'; trans.convert_to='CAMERA'; trans.vector_type='NORMAL'
        scale=n.new('ShaderNodeVectorMath'); scale.operation='MULTIPLY_ADD'
        scale.inputs[1].default_value=(.5,.5,.5); scale.inputs[2].default_value=(.5,.5,.5)
        l.new(geo.outputs['Normal'],trans.inputs[0]); l.new(trans.outputs[0],scale.inputs[0])
        l.new(scale.outputs[0],em.inputs[0]); l.new(em.outputs[0],output.inputs['Surface'])
        scene.view_layers[0].material_override=material
        normal=render('-normal.png')
        return source, normal, mask
    finally:
        for obj, color in colors.items(): obj.color=color
        bpy.data.scenes.remove(scene)
        if material: bpy.data.materials.remove(material)
