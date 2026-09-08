"""Three independent gray Blender scenes for multi-image H3 experiments."""
import argparse
import json
import math
from pathlib import Path
import random
import sys
import time

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
from railway_scene import Parts
from market_scene import ellipsoid


def ring(parts, center, radius, thickness=.06, plane='XY', segments=64):
    def point(a):
        u, v = radius * math.cos(a), radius * math.sin(a)
        return Vector(center) + Vector({'XY': (u, v, 0), 'XZ': (u, 0, v), 'YZ': (0, u, v)}[plane])
    for i in range(segments):
        parts.beam(point(i*math.tau/segments), point((i+1)*math.tau/segments), thickness)


def person(p, x, y, z=0):
    ellipsoid(p,x,y,z+1.25,.23,.16,.35)
    ellipsoid(p,x,y,z+1.78,.13,.12,.17)
    p.beam((x,y,z+1.45),(x,y,z+1.64),.075)
    for s in [-1,1]:
        p.beam((x+s*.12,y,z+.96),(x+s*.15,y+s*.1,z+.1),.09,12)
        ellipsoid(p,x+s*.15,y+s*.1-.07,z+.08,.10,.17,.07)
        p.beam((x+s*.23,y,z+1.47),(x+s*.32,y-.12,z+1.0),.07,12)
        ellipsoid(p,x+s*.32,y-.12,z+.97,.06,.04,.08)


def base(name):
    scene=bpy.data.scenes.new(name)
    bpy.context.window.scene=scene
    scene.world=bpy.data.worlds.new(name+' world')
    p=[Parts(n) for n in ['Structure','Machinery and furnishings','Fine detail','Fictional adult visitors']]
    p[0].box(0,3,-.25,26,32,.5)
    for x in range(-13,14):
        for y in range(-12,20):
            p[2].box(x*.94,y*.94,.015,.91,.91,.025)
    for x,y in [(-3,-1),(3,2),(-4,7),(2,10)]:person(p[3],x,y)
    return scene,p


def abyss(p):
    structure, machine, detail, humans=p
    # Pressure tunnel ribs, floor-to-ceiling observation aperture, suspended jellyfish.
    for y in [-5,-1,3,7,11,15]:
        for k in range(48):
            a=k*math.pi/48;b=(k+1)*math.pi/48
            structure.beam((8*math.cos(a),y,4+8*math.sin(a)),(8*math.cos(b),y,4+8*math.sin(b)),.17,12)
        for x in [-8,8]:structure.beam((x,y,0),(x,y,4),.22,16)
    for r in [4.8,5,5.2]:ring(structure,(0,13,5.8),r,.14,'XZ',96)
    for i in range(64):
        a=i*math.tau/64
        ellipsoid(detail,5.05*math.cos(a),12.8,5.8+5.05*math.sin(a),.08,.08,.08)
    for x in [-6.9,6.9]:
        for z in [.4,2.4,3.0]:machine.beam((x,-6,z),(x,15,z),.07,12)
        for y in range(-5,15):machine.beam((x,y,.3),(x,y,2.4),.035)
        for y in [0,5,10]:
            machine.box(x*.76,y,.95,1.3,1.0,1.7)
            machine.box(x*.76,y-.53,1.50,1.1,.08,.6)
            for i in range(12):detail.box(x*.76-.48+i*.085,y-.58,1.13,.045,.025,.035)
    # Central research table with microscope-like instruments and trays.
    machine.beam((0,2,0),(0,2,1.05),1.6,64)
    ring(machine,(0,2,1.1),1.85,.08)
    for i in range(18):
        a=i*math.tau/18
        machine.beam((1.4*math.cos(a),2+1.4*math.sin(a),1.1),(1.4*math.cos(a),2+1.4*math.sin(a),1.4),.1,12)
    for x,y,z in [(-2,14,6),(1.5,14.5,8),(0,14.8,4),(3,15,5.6),(-3.2,15,8.5)]:
        ellipsoid(machine,x,y,z,.6,.45,.3)
        for i in range(9):
            a=i*math.tau/9
            last=(x+.35*math.cos(a),y+.35*math.sin(a),z)
            for k in range(12):
                end=(x+.35*math.cos(a)+.1*math.sin(k*.7+i),y+.35*math.sin(a),z-(k+1)*.13)
                detail.beam(last,end,.016,6);last=end
    for i in range(50):
        x=random.uniform(-8,8); y=random.uniform(14,18)
        ellipsoid(machine,x,y,.2,.3,.3,random.uniform(.15,.65))


def helios(p):
    structure,machine,detail,humans=p
    # Terraced courtyard, central astronomical mechanism, tracking mirror fields.
    for side in [-1,1]:
        for k in range(5):
            z=k*.35;structure.box(side*(7+k*.65),5,z/2,1.1,23,z+.2)
        for y in [-3,3,9,15]:
            structure.box(side*9,y,3.5,1.0,1.0,7)
            for z in [0,3,6.9]:structure.box(side*9,y,z,1.4,1.4,.22)
        structure.box(side*9,6,7.1,1.7,20,.35)
    machine.beam((0,5,0),(0,5,2.2),1.25,64)
    for z,r in [(1.1,1.7),(1.4,1.5),(2,1.4)]:ring(machine,(0,5,z),r,.1)
    for plane,r in [('XY',3),('XZ',3.4),('YZ',2.7)]:
        ring(machine,(0,5,5),r,.1,plane,120)
        ring(detail,(0,5,5),r+.16,.03,plane,120)
    ellipsoid(machine,0,5,5,.75,.75,.75)
    for k in range(72):
        a=k*math.tau/72
        detail.beam((3.4*math.cos(a),4.97,5+3.4*math.sin(a)),(3.62*math.cos(a),4.97,5+3.62*math.sin(a)),.032)
    for x in [-5.3,5.3]:
        for y in [-2,3,8,13]:
            machine.beam((x,y,0),(x,y,1.7),.09)
            machine.box(x,y,1.85,2.1,1.5,.12)
            for i in range(10):
                for j in range(7):detail.box(x-.95+i*.21,y-.63+j*.21,1.93,.195,.195,.025)
    for x in range(-12,13):
        for y in range(20,36):
            h=1.0+1.5*math.sin(x*.3+y*.2)**2
            structure.box(x*1.2,y,h/2,1.2,1.1,h)
    for i in range(100):
        a=i*math.tau/100
        detail.box(4*math.cos(a),5+4*math.sin(a),.05,.12,.12,.06)


def canopy(p):
    structure,machine,detail,humans=p
    # Living tree laboratory with elevated galleries and a tightly modeled spiral stair.
    structure.beam((0,7,0),(.7,7,15),.9,32)
    for z in [3.5,7,10.5]:
        for k in range(100):
            a=k*math.tau/100;b=(k+1)*math.tau/100
            structure.beam((4*math.cos(a),7+4*math.sin(a),z),(4*math.cos(b),7+4*math.sin(b),z),.16)
            detail.beam((4*math.cos(a),7+4*math.sin(a),z),(4*math.cos(a),7+4*math.sin(a),z+1.1),.025)
        ring(detail,(0,7,z+1.1),4,.045)
        for k in range(60):
            a=k*math.tau/60
            structure.beam((1.3*math.cos(a),7+1.3*math.sin(a),z),(4*math.cos(a),7+4*math.sin(a),z),.085)
    for k in range(100):
        a=k*.12;z=k*.105
        structure.beam((1.3*math.cos(a),7+1.3*math.sin(a),z),(2.5*math.cos(a),7+2.5*math.sin(a),z),.12)
        detail.beam((2.5*math.cos(a),7+2.5*math.sin(a),z),(2.5*math.cos(a),7+2.5*math.sin(a),z+1.05),.028)
        if k:detail.beam(last,(2.5*math.cos(a),7+2.5*math.sin(a),z+1.05),.04)
        last=(2.5*math.cos(a),7+2.5*math.sin(a),z+1.05)
    for x in [-6,6]:
        for y in [0,5,11,16]:
            structure.beam((x,y,0),(x,y,14),.32,20)
            machine.box(x,y,1.1,2.2,1.1,1.8)
            for j in range(6):
                for i in range(3):
                    xx=x-.9+j*.35;yy=y-.35+i*.35
                    machine.beam((xx,yy,2),(xx,yy,2.4),.11,12)
    for i in range(90):
        x=random.choice([-1,1])*random.uniform(4.8,10);y=random.uniform(-2,18);z=random.uniform(4,15)
        structure.beam((x,y,0),(x,y,z),.05)
        for k in range(22):
            a=k*2.4;r=random.uniform(.15,1)
            ellipsoid(detail,x+r*math.cos(a),y+r*math.sin(a),z+random.uniform(-.7,.7),.45,.18,.055)
    person(humans,2.4,8,3.5);person(humans,-2.5,7,7)
    for y in [-3,2,7,12,17]:
        structure.beam((-8,y,13),(8,y,13),.12)
        for x in range(-8,9,2):detail.beam((x,y,13),(x,y+5,13),.04)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();manifest=[]
    for name,builder,target in [('ABYSS',abyss,(0,6,5)),('HELIOS',helios,(0,5,3.8)),('CANOPY',canopy,(0,6,6.4))]:
        random.seed(829)
        scene,parts=base(name);builder(parts)
        objects=[p.finish() for p in parts]
        bpy.ops.object.camera_add(location=(12,-19,11))
        camera=bpy.context.object;camera.name=name+' reference camera'
        camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.lens=36;scene.camera=camera
        scene.render.engine='BLENDER_WORKBENCH'
        s=scene.display.shading;s.light='STUDIO';s.color_type='SINGLE';s.single_color=(.57,.57,.57)
        s.show_shadows=True;s.show_cavity=True;s.cavity_type='BOTH';s.background_type='WORLD'
        scene.world.color=(.09,.09,.09)
        scene.render.resolution_x=960;scene.render.resolution_y=960;scene.render.resolution_percentage=100
        scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
        scene.render.filepath=str(out/(name.lower()+'.png'))
        t=time.perf_counter();bpy.ops.render.render(write_still=True)
        manifest.append(dict(name=name,image=scene.render.filepath,parts=sum(p.count for p in parts),
                             faces=sum(len(o.data.polygons) for o in objects),capture_seconds=time.perf_counter()-t))
    # Keep the three genuinely independent scenes together in one editable file.
    bpy.context.window.scene=bpy.data.scenes['ABYSS']
    if bpy.data.scenes.get('Scene'):bpy.data.scenes.remove(bpy.data.scenes['Scene'])
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.overlay.show_overlays=False
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'three-observatories.blend'))
    (out/'sources.json').write_text(json.dumps(dict(scenes=manifest,build_and_capture_seconds=time.perf_counter()-started),indent=2))
    print(json.dumps(manifest),flush=True)


if __name__=='__main__':main()
