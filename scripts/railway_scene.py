"""Procedural hillside railway district. Geometry only; no external assets."""
import math
import random
import bpy
from mathutils import Vector


class Parts:
    def __init__(self, name):
        self.name, self.vertices, self.faces = name, [], []
        self.count = 0

    def box(self, x, y, z, w, d, h):
        n = len(self.vertices)
        self.vertices.extend((x+a*w/2, y+b*d/2, z+c*h/2)
                             for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                                           (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)])
        self.faces.extend(tuple(n+i for i in f) for f in
                          [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        self.count += 1

    def beam(self, start, end, radius=.06, sides=8):
        start, end = Vector(start), Vector(end)
        axis = (end-start).normalized()
        u = axis.cross(Vector((0,0,1)))
        if u.length < .01: u = axis.cross(Vector((0,1,0)))
        u.normalize(); v = axis.cross(u)
        n = len(self.vertices)
        for p in (start,end):
            self.vertices.extend(tuple(p+radius*(math.cos(i*math.tau/sides)*u+math.sin(i*math.tau/sides)*v)) for i in range(sides))
        self.faces.extend((n+i,n+(i+1)%sides,n+(i+1)%sides+sides,n+i+sides) for i in range(sides))
        self.faces.extend([tuple(n+i for i in reversed(range(sides))),tuple(n+sides+i for i in range(sides))])
        self.count += 1

    def finish(self):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], self.faces); mesh.update()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        obj.color = (.57,.57,.57,1)
        obj['modeled_parts'] = self.count
        return obj


def build(closeup=False):
    random.seed(27)
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    ground, buildings, trim, transport, street = [Parts(n) for n in
        ['Terraced foundations and retaining walls','District architecture','Windows balconies and services','Grand station and rail infrastructure','Market and street furniture']]
    ground.box(0,2,-1,68,51,2)
    # Three stepped urban terraces: the railway cuts across the middle.
    for row, y in enumerate([3,14,25]):
        base = row*3.3
        ground.box(0,y,base-.4,64,9.8,.8)
        ground.box(0,y-4.9,base/2-.3,64,.45,max(.6,base))
        for x in range(-31,32,2):
            ground.box(x,y-5.15,base/2-.3,.2,.3,max(.6,base))
        for col in range(9):
            x = -28+col*7
            if row == 0 and col in [3,4,5]: continue
            floors = random.randint(3,7)
            w,d = random.uniform(4.6,5.8),random.uniform(5.3,6.6)
            h=floors*1.75
            buildings.box(x,y,base+h/2,w,d,h)
            for floor in range(floors+1):
                trim.box(x,y,base+floor*1.75,w+.2,d+.2,.13)
            buildings.box(x,y,base+h+.18,w+.45,d+.45,.25)
            # Deep reveals, mullions, lintels and balcony rails, on all facades.
            for floor in range(floors):
                z=base+floor*1.75+.95
                for side in [-1,1]:
                    for k in range(5):
                        xx=x+(k-2)*w/5.6; yy=y+side*(d/2+.04)
                        trim.box(xx,yy,z,.62,.07,.98)
                        for dx in [-.37,0,.37]:trim.box(xx+dx,yy+side*.065,z,.055,.12,1.13)
                        for dz in [-.57,.02,.57]:trim.box(xx,yy+side*.07,z+dz,.8,.13,.055)
                        if k%2 == 0:
                            trim.box(xx,yy+side*.42,z-.62,.95,.9,.1)
                            for q in range(7):
                                trim.box(xx+(q-3)*.14,yy+side*.82,z-.24,.025,.025,.72)
                            trim.box(xx,yy+side*.82,z+.12,.98,.04,.045)
                    for k in range(4):
                        yy=y+(k-1.5)*d/4.8;xx=x+side*(w/2+.04)
                        trim.box(xx,yy,z,.08,.73,1.0)
                        for dy in [-.41,0,.41]:trim.box(xx+side*.05,yy+dy,z,.14,.045,1.1)
                        for dz in [-.56,.56]:trim.box(xx+side*.05,yy,z+dz,.14,.9,.06)
            for k in range(3):
                xx=x+(k-1)*1.1
                trim.box(xx,y+.4,base+h+.6,.7,1,.6)
                for fin in range(9): trim.box(xx-.3+fin*.075,y-.12,base+h+.6,.025,.03,.5)
                trim.beam((xx,y+1,base+h),(xx,y+1,base+h+1.8),.12)
            # Rooftop water tank / antenna.
            trim.beam((x,y-1,base+h+.2),(x,y-1,base+h+1.7),.62,16)
            trim.beam((x+1,y,base+h),(x+1,y,base+h+3),.045)
            for z in [1.9,2.3,2.7]:trim.beam((x+.35,y,base+h+z),(x+1.65,y,base+h+z),.024)
    # Long viaduct with paired railway tracks and hundreds of sleepers.
    transport.box(0,-7,3.65,66,6,.7)
    for x in range(-30,31,5):
        for y in [-9.1,-4.9]:
            transport.box(x,y,1.75,.8,.8,3.5)
            transport.beam((x-2,y,3.3),(x,y,1.7),.15)
            transport.beam((x+2,y,3.3),(x,y,1.7),.15)
    for y in [-8.2,-5.8]:
        for rail in [-.62,.62]:transport.box(0,y+rail,4.17,66,.08,.14)
        for i in range(220):transport.box(-32.7+i*.3,y,4.03,.13,1.65,.12)
    for side in [-1,1]:
        y=-7+side*3
        transport.box(0,y,4.9,66,.065,.075)
        for i in range(260):transport.box(-32.5+i*.25,y,4.49,.035,.035,.8)
    # The hero: a legible barrel-vaulted central station hall.
    transport.box(0,-.5,1.2,20,7,2.4)
    for x in [-9.7,9.7]:
        transport.box(x,-.5,3.7,.5,7,2.8)
    for ix in range(25):
        x=-10+ix*20/24
        for i in range(32):
            a,b=i*math.pi/32,(i+1)*math.pi/32
            transport.beam((x,-.5+3.5*math.cos(a),5+3.1*math.sin(a)),
                           (x,-.5+3.5*math.cos(b),5+3.1*math.sin(b)),.075)
    for i in range(17):
        a=i*math.pi/16
        transport.beam((-10,-.5+3.5*math.cos(a),5+3.1*math.sin(a)),(10,-.5+3.5*math.cos(a),5+3.1*math.sin(a)),.055)
    for x in range(-9,10,2):
        for y in [-3.8,2.8]:
            transport.box(x,y,3.75,.22,.22,2.5)
            transport.box(x,y,2.6,1.45,.2,.1)
    # Clock tower frames the central hall.
    buildings.box(11,1,5.5,2.8,3,11)
    buildings.box(11,1,11.25,3.4,3.6,.4)
    for k in range(12):
        a=k*math.tau/12
        trim.box(11+.9*math.sin(a),-.53,9.1+.9*math.cos(a),.12,.1,.12)
    trim.beam((11,-.65,9.1),(11,-.65,9.85),.045)
    trim.beam((11,-.65,9.1),(11.5,-.65,8.9),.045)
    # Parked three-car commuter train: full windows, wheels, rooftop hardware.
    for x in [-19,-13,-7]:
        transport.box(x,-8.2,5.15,5.65,1.8,1.75)
        transport.box(x,-8.2,6.07,5.4,1.75,.16)
        for side in [-1,1]:
            for k in range(8):transport.box(x-2.35+k*.66,-8.2+side*.92,5.45,.49,.06,.66)
            for dx in [-1.9,1.9]:transport.beam((x+dx,-8.2+side*.7,4.35),(x+dx,-8.2+side*1.02,4.35),.32,16)
    # Catenary and its suspended wiring.
    for x in range(-30,31,6):
        transport.beam((x,-10,3.9),(x,-10,8.1),.07)
        transport.beam((x,-10,8.1),(x,-4,8.1),.055)
    for y in [-8.2,-5.8]:transport.beam((-32,y,7.9),(32,y,7.9),.022)
    # Grand public stairs, streets and market plaza in the foreground.
    for i in range(26):
        street.box(1,-11-i*.24,3.8-i*.145,9,.26,.16)
    for x in [-3.4,5.4]:street.beam((x,-11,4.8),(x,-17,1),.065)
    for x in [-22,-14,15,23]:
        for y in [-15,-20]:
            street.box(x,y,1,4,2.5,1.4)
            for k in range(11):street.box(x-2+k*.4,y,2.3,.39,3.1,.14)
            for dx in [-1.85,1.85]:
                for dy in [-1.2,1.2]:street.beam((x+dx,y+dy,0),(x+dx,y+dy,2.35),.045)
            for q in range(12):street.box(x-1.6+(q%6)*.64,y+(q//6-.5)*.8,1.9,.5,.6,.28)
    for x in range(-30,31,3):
        for y in [-11,-23]:
            street.beam((x,y,0),(x,y,3.4),.055)
            street.box(x,y,3.45,.55,.4,.16)
    for x in [-29,-10,10,29]:
        for y in [-18,8,19]:
            street.box(x,y,.3,1.3,1.3,.6)
            street.beam((x,y,.4),(x,y,2.9),.12)
            # Stylized solid foliage volumes, still neutral gray.
            for k in range(6):
                a=k*math.tau/6
                street.beam((x+.35*math.cos(a),y+.35*math.sin(a),2),(x+.35*math.cos(a),y+.35*math.sin(a),3.3),.65,10)
    # Terrace connectors: real stairs linking each level at both edges.
    for x in [-32.5,32.5]:
        for row in [1,2]:
            for i in range(24):street.box(x,7.6+(row-1)*11+i*.25,(row-1)*3.3+i*.14,1.8,.27,.17)
    objects=[part.finish() for part in [ground,buildings,trim,transport,street]]
    scene=bpy.context.scene
    bpy.ops.object.camera_add(location=(66,-91,68))
    camera=bpy.context.object; camera.name='Locked district camera'
    camera.rotation_euler=(Vector((0,2,5))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO';camera.data.ortho_scale=106;scene.camera=camera
    if closeup:
        target=Vector((0,-1,4.5))
        camera.location=target+Vector((66,-93,63))
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale=36
    scene.render.engine='BLENDER_WORKBENCH'
    shading=scene.display.shading
    shading.light='STUDIO';shading.color_type='SINGLE';shading.single_color=(.57,.57,.57)
    shading.show_shadows=True;shading.show_cavity=True;shading.cavity_type='BOTH'
    shading.background_type='WORLD';scene.world.color=(.055,.055,.055)
    scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='Standard'
    scene['modeled_parts']=sum(p['modeled_parts'] for p in objects)
    scene['mesh_faces']=sum(len(o.data.polygons) for o in objects)
    return objects
