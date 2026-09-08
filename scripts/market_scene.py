"""Dense conservatory market with modeled people; neutral geometry only."""
import math,random
import bpy
from mathutils import Vector
from railway_scene import Parts

def ellipsoid(p,x,y,z,rx,ry,rz):
 n=len(p.vertices);sides=12;rings=8
 for j in range(rings+1):
  a=math.pi*j/rings
  for i in range(sides):
   b=math.tau*i/sides;p.vertices.append((x+rx*math.sin(a)*math.cos(b),y+ry*math.sin(a)*math.sin(b),z+rz*math.cos(a)))
 for j in range(rings):
  for i in range(sides):
   k=n+j*sides+i;l=n+j*sides+(i+1)%sides;p.faces.append((k,l,l+sides,k+sides))
 p.count+=1

def build(closeup=True):
 random.seed(821)
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 floor,arch,detail,stalls,goods,plants,people=[Parts(n) for n in ['Inlaid stone floor','Iron conservatory architecture','Balustrades and architectural fittings','Market stalls and furniture','Individual produce and merchandise','Botanical planting','Shoppers and vendors']]
 floor.box(0,9,-.3,40,58,.6)
 for x in range(-38,39):
  for y in range(-38,79):floor.box(x*.5,y*.5,.01,.48,.48,.025)
 for side in [-1,1]:
  x=side*16
  arch.box(x,10,5.1,4.4,47,.35)
  for y in range(-12,35,4):
   arch.beam((x,y,0),(x,y,12),.23,16)
   for z in [.25,4.8,5.5,10.4]:arch.box(x,y,z,.9,.9,.25)
   # Arched bays and spandrels.
   for z0 in [2.8,8]:
    for k in range(16):
     a=k*math.pi/16;b=(k+1)*math.pi/16
     arch.beam((x,y+2-2*math.cos(a),z0+2*math.sin(a)),(x,y+2-2*math.cos(b),z0+2*math.sin(b)),.09)
  for y in range(-12,35):
   for z in [5.35,6.5]:detail.beam((side*13.8,y,z),(side*13.8,y+1,z),.045)
   for dy in [0,.25,.5,.75]:detail.beam((side*13.8,y+dy,5.35),(side*13.8,y+dy,6.5),.035)
   # Repeated wall panels and louvres.
   for z in [2,7.6]:
    arch.box(side*18.1,y,z,.15,.93,3.2)
    for k in range(12):detail.box(side*17.98,y,z-1.45+k*.25,.16,.82,.035)
 # Open ribbed roof: visible roof edges, clear central sightline.
 for y in range(-8,37,4):
  for k in range(32):
   a=k*math.pi/32;b=(k+1)*math.pi/32
   arch.beam((18*math.cos(a),y,10.4+7*math.sin(a)),(18*math.cos(b),y,10.4+7*math.sin(b)),.10)
 for k in range(17):
  a=k*math.pi/16;x=18*math.cos(a);z=10.4+7*math.sin(a)
  detail.beam((x,-12,z),(x,37,z),.045)
 # Back facade with clock and many panes.
 for x in range(-18,19):
  for z in range(1,15):
   detail.box(x,36,z,.045,.18,.96);detail.box(x,36,z,.96,.18,.045)
 for k in range(60):
  a=k*math.tau/60;detail.beam((1.4*math.sin(a),35.8,11.3+1.4*math.cos(a)),(1.55*math.sin(a),35.8,11.3+1.55*math.cos(a)),.04)
 detail.beam((0,35.7,11.3),(.9,35.7,11.9),.065);detail.beam((0,35.7,11.3),(-.2,35.7,12.5),.05)
 # Broad public stairs to side galleries.
 for side in [-1,1]:
  for i in range(32):
   z=(i+1)*5/32;arch.box(side*15,-10+i*.3,z/2,3.2,.31,z)
  for dx in [-1.5,1.5]:detail.beam((side*15+dx,-10,1),(side*15+dx,-.4,6),.06)
 # Central circular fountain, three basins, radial carved stone rims.
 for radius,z in [(3.1,.45),(1.8,1.15),(.85,2.25)]:
  for k in range(64):
   a=k*math.tau/64;b=(k+1)*math.tau/64
   arch.beam((radius*math.cos(a),7+radius*math.sin(a),z),(radius*math.cos(b),7+radius*math.sin(b),z),.16)
  arch.beam((0,7,.05),(0,7,z-.05),radius-.15,64)
 arch.beam((0,7,0),(0,7,3.5),.22,16)
 ellipsoid(detail,0,7,3.55,.3,.3,.42)
 # Individual market stalls, awning ribs, crates and hundreds of produce pieces.
 for x in [-10,-5.6,5.6,10]:
  for y in [-3,3,13,20,27]:
   if abs(y-7)<3:continue
   stalls.box(x,y,1.0,3.6,2.4,.25)
   for dx in [-1.65,1.65]:
    for dy in [-1.05,1.05]:stalls.beam((x+dx,y+dy,0),(x+dx,y+dy,3.05),.06)
   for k in range(18):stalls.box(x-1.75+k*.2,y,3.1,.19,3,.06)
   for dx in [-1.2,0,1.2]:
    for dy in [-.6,.6]:
     goods.box(x+dx,y+dy,1.25,1.04,.95,.18)
     for q in range(5):
      for r in range(4):ellipsoid(goods,x+dx-.39+q*.19,y+dy-.32+r*.2,1.47+random.random()*.05,.09,.09,.10)
   for k in range(10):stalls.box(x-1.7+k*.37,y-1.2,.5,.33,.06,.9)
   # Overhead pendant.
   detail.beam((x,y,3.8),(x,y,5),.025);ellipsoid(detail,x,y,3.75,.25,.25,.16)
 # Trees, individual leaves, tables and stools around edges.
 for x in [-12,12]:
  for y in [-7,9,17,31]:
   arch.beam((x,y,0),(x,y,.7),.65,16);plants.beam((x,y,.6),(x,y,3.7),.12)
   for k in range(22):
    a=random.random()*math.tau;rad=random.uniform(.2,1.1);z=random.uniform(2.4,4.2)
    plants.beam((x,y,2.4),(x+rad*math.cos(a),y+rad*math.sin(a),z),.025)
    for j in range(8):
     ellipsoid(plants,x+rad*math.cos(a)+random.uniform(-.3,.3),y+rad*math.sin(a)+random.uniform(-.3,.3),z+random.uniform(-.25,.25),.18,.08,.04)
 for y in [-6,16,24,31]:
  for x in [-2.8,2.8]:
   stalls.beam((x,y,0),(x,y,.82),.06);stalls.beam((x,y,.82),(x,y,.89),.55,24)
   for dx,dy in [(-.85,0),(.85,0)]:
    stalls.box(x+dx,y+dy,.47,.42,.42,.08)
    for ex in [-.16,.16]:
     for ey in [-.16,.16]:stalls.beam((x+dx+ex,y+dy+ey,0),(x+dx+ex,y+dy+ey,.44),.025)
 def person(x,y,z,angle):
  # Smooth anatomical proxy with face, hair, hands, fingers, shoes and clothing.
  ca,sa=math.cos(angle),math.sin(angle)
  def pt(a,b,c):return (x+ca*a-sa*b,y+sa*a+ca*b,z+c)
  def e(a,b,c,rx,ry,rz):ellipsoid(people,*pt(a,b,c),rx,ry,rz)
  stride=random.uniform(-.19,.19)
  e(0,0,1.15,.24,.15,.34);e(0,0,.88,.19,.14,.15)
  people.beam(pt(0,0,1.4),pt(0,0,1.58),.075)
  e(0,0,1.69,.13,.115,.17);e(0,-.025,1.77,.135,.12,.10);e(0,.11,1.69,.035,.035,.04)
  for side in [-1,1]:
   hip=pt(side*.12,0,.87);knee=pt(side*.13,side*stride,.47);foot=pt(side*.13,side*stride*.9,.08)
   people.beam(hip,knee,.087,12);people.beam(knee,foot,.065,12)
   e(side*.13,side*stride*.9+.055,.065,.085,.15,.055)
   shoulder=pt(side*.22,0,1.36);elbow=pt(side*.29,.07,.99);hand=pt(side*.30,.20,.89)
   people.beam(shoulder,elbow,.075,12);people.beam(elbow,hand,.055,12);ellipsoid(people,*hand,.052,.035,.07)
   for f in range(4):people.beam(Vector(hand)+Vector((f*.018-.027,0,-.035)),Vector(hand)+Vector((f*.018-.027,.02,-.09)),.009,6)
  people.count+=1
 # Broad clear circulation lanes populated at believable human scale.
 count=0
 for i in range(115):
  x=random.choice([-3.4,0,3.4,-13,13])+random.uniform(-.6,.6);y=random.uniform(-9,33)
  if x*x+(y-7)**2<14:continue
  person(x,y,0,random.random()*math.tau);count+=1
 for side in [-1,1]:
  for i in range(18):person(side*15+random.uniform(-.5,.5),random.uniform(-1,34),5.28,random.random()*math.tau);count+=1
 objects=[p.finish() for p in [floor,arch,detail,stalls,goods,plants,people]]
 for obj in objects:
  if obj.name in ['Shoppers and vendors','Botanical planting','Individual produce and merchandise']:
   for poly in obj.data.polygons:poly.use_smooth=True
 scene=bpy.context.scene;bpy.ops.object.camera_add(location=(10,-16,10))
 cam=bpy.context.object;cam.name='Locked market balcony camera';cam.rotation_euler=(Vector((0,12,3.2))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=27;cam.data.show_passepartout=True;cam.data.passepartout_alpha=1;scene.camera=cam
 scene.render.engine='BLENDER_WORKBENCH';s=scene.display.shading;s.light='STUDIO';s.color_type='SINGLE';s.single_color=(.57,.57,.57);s.show_shadows=True;s.show_cavity=True;s.cavity_type='BOTH';s.background_type='WORLD'
 scene.world.color=(.07,.07,.07);scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
 scene['modeled_parts']=sum(o['modeled_parts'] for o in objects);scene['mesh_faces']=sum(len(o.data.polygons) for o in objects);scene['people_count']=count
 return objects
