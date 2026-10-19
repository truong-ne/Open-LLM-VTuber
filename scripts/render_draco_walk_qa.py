"""Offline preview of actual skinned vertices with source texture samples.

Painter preview for motion QA, not a screenshot or a replacement renderer.
"""
import io
import json
import struct
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
name=sys.argv[1] if len(sys.argv)>1 else 'draco-walk-qa'
if not name.replace('-','').isalnum(): raise ValueError('Invalid QA output name')
meta=json.loads((ROOT/f'private/{name}.json').read_text())
binary=(ROOT/f'private/{name}.bin').read_bytes()
raw=(ROOT/'web_tool/mao-5070/draco/character.glb').read_bytes()
offset=12
while offset<len(raw):
    length,kind=struct.unpack_from('<II',raw,offset);offset+=8
    if kind==0x4E4F534A: doc=json.loads(raw[offset:offset+length])
    if kind==0x004E4942: glb=raw[offset:offset+length]
    offset+=length
textures={}
for material in doc['materials']:
    tex=material.get('pbrMetallicRoughness',{}).get('baseColorTexture',{})
    if 'index' not in tex: continue
    source=doc['images'][doc['textures'][tex['index']]['source']]
    view=doc['bufferViews'][source['bufferView']];start=view.get('byteOffset',0)
    textures[material['name']]=np.asarray(Image.open(io.BytesIO(glb[start:start+view['byteLength']])).convert('RGBA'))
def read(info,dtype): return np.frombuffer(binary,dtype=dtype,count=info['count'],offset=info['offset'])
indices=[];colors=[];base=0
for mesh in meta['meshes']:
    ids=read(mesh['index'],np.uint32).reshape(-1,3)
    uv=read(mesh['uv'],np.float32).reshape(-1,2)
    count=meta['frames'][0]['positions'][len(indices)]['count']//3
    if mesh['name'] in textures:
        texture=textures[mesh['name']];coord=np.clip(uv[ids].mean(1),0,1)
        rgb=texture[(coord[:,1]*(texture.shape[0]-1)).astype(int),(coord[:,0]*(texture.shape[1]-1)).astype(int)]
    else:
        value=mesh.get('color',0x503037);rgb=np.tile([(value>>16)&255,(value>>8)&255,value&255,255],(len(ids),1))
    if mesh['name'] in ['V13_Face_Reference_Lashes_Paint','CEL5','V13_Reference_Upper_Lash_Curved_Mask.001','V8_Hair_Fine_Luminous_Strands']:
        rgb=rgb.copy();rgb[rgb[:,:3].max(1)<5,3]=0
    colors.append(rgb);indices.append(ids.astype(np.int32)+base);base+=count
ids=np.concatenate(indices);color=np.concatenate(colors)
actor_ids=ids;actor_color=color
hem='--hem' in sys.argv
hands='--hands' in sys.argv or hem
room_mode='--room' in sys.argv
images=[]
samples=[(meta['frames'][-1],kind) for kind in ['room','follow']] if room_mode else [(frame,angle) for frame in ([meta['frames'][min(1,len(meta['frames'])-1)]] if hands else meta['frames']) for angle in ([0,-65] if hands else [0])]
for frame,angle in samples:
    vertex=np.concatenate([read(info,np.float32).reshape(-1,3) for info in frame['positions']])
    ids=actor_ids;color=actor_color;sides=np.full(len(ids),2)
    if room_mode:
        vertices=[vertex];all_ids=[ids];all_colors=[color];all_sides=[sides];base=len(vertex)
        for mesh in meta['room']['meshes']:
            positions=read(mesh['position'],np.float32).reshape(-1,3);tri=read(mesh['index'],np.uint32).reshape(-1,3)
            vertices.append(positions);all_ids.append(tri+base);all_colors.append(read(mesh['colors'],np.uint8).reshape(-1,4));all_sides.append(np.full(len(tri),mesh['side']));base+=len(positions)
        vertex=np.concatenate(vertices);ids=np.concatenate(all_ids);color=np.concatenate(all_colors);sides=np.concatenate(all_sides)
    # Front view, matching the desktop: a horizontal path must become a profile.
    if room_mode:
        matrices=frame['roomCameras'][angle]
        view=np.array(matrices['view']).reshape(4,4,order='F');projection=np.array(matrices['projection']).reshape(4,4,order='F')
        def project(points):
            world=np.c_[points,np.ones(len(points))];eye=world@view.T;clip=eye@projection.T
            xy=(clip[:,:2]/np.maximum(clip[:,3:4],.001)*[1,-1]+1)*[360,320]
            return xy,eye[:,2],clip[:,3]>.01
        xy,depth,in_front=project(vertex)
    elif hands:
        vertex=vertex-np.array([frame.get('x',0),0,frame.get('z',0)])
        radians=np.radians(angle)+frame.get('yaw',0);x=vertex[:,0]*np.cos(radians)-vertex[:,2]*np.sin(radians)
        depth=vertex[:,0]*np.sin(radians)+vertex[:,2]*np.cos(radians)
        zoom=1600 if hem else 1150;target_y=.95 if hem else 1.25
        xy=np.stack([360+x*zoom,440-(vertex[:,1]-target_y)*zoom],-1)
    else:
        depth=vertex[:,2]
        xy=np.stack([180+vertex[:,0]*230,475-vertex[:,1]*230],-1)
    triangles=xy[ids];area=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    visible=(np.abs(area)>.16)&(color[:,3]>100)
    if room_mode:visible &= in_front[ids].all(1)&((sides==2)|((sides==0)&(area<0))|((sides==1)&(area>0)))
    order=np.argsort(depth[ids].mean(1));order=order[visible[order]]
    image=Image.new('RGB',(720,640) if room_mode else (720,800) if hands else (360,510),'#1b1c22' if room_mode else '#eeeaf1');draw=ImageDraw.Draw(image)
    if not room_mode and not hands:
        draw.ellipse((40,455,320,491),fill='#d9d5df');draw.line((15,475,345,475),fill='#aaa4b2')
    if hem or room_mode:
        # The skirt and lining overlap closely. A per-triangle painter sort
        # can invent jagged patches; use a pixel depth buffer for this review.
        pixels=np.array(image);zbuffer=np.full(pixels.shape[:2],-np.inf)
        for triangle in order:
            p=triangles[triangle];lo=np.maximum(np.floor(p.min(0)).astype(int),0);hi=np.minimum(np.ceil(p.max(0)).astype(int),[pixels.shape[1]-1,pixels.shape[0]-1])
            if np.any(hi<lo):continue
            x,y=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
            den=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
            if abs(den)<1e-8:continue
            a=((p[1,1]-p[2,1])*(x-p[2,0])+(p[2,0]-p[1,0])*(y-p[2,1]))/den
            b=((p[2,1]-p[0,1])*(x-p[2,0])+(p[0,0]-p[2,0])*(y-p[2,1]))/den;c=1-a-b
            z=a*depth[ids[triangle,0]]+b*depth[ids[triangle,1]]+c*depth[ids[triangle,2]]
            target_z=zbuffer[lo[1]:hi[1]+1,lo[0]:hi[0]+1];target_rgb=pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            mask=(a>=0)&(b>=0)&(c>=0)&(z>target_z);target_z[mask]=z[mask];target_rgb[mask]=color[triangle,:3]
        image=Image.fromarray(pixels);draw=ImageDraw.Draw(image)
    else:
        for triangle in order:draw.polygon([tuple(p) for p in triangles[triangle]],fill=tuple(int(c) for c in color[triangle,:3]))
    draw.text((10,10),f"{angle} / room 8 x 6 m" if room_mode else f"{frame['time']:.1f}s  {frame['phase']}",fill='#c8bfd8' if room_mode else '#453a50')
    if not room_mode:draw.text((10,28),f"view {angle} deg" if hands else f"heading {np.degrees(frame['yaw']):.0f} deg",fill='#64566c')
    images.append(image)
selected=list(range(len(images))) if len(images)<9 else [0,3,6,10,13,17,21,30] if 'sidestep' in name else [0,6,12,16,20,24,32,44]
sheet=Image.new('RGB',(1440,640) if room_mode else (1440,800) if hands else (1440,510*((len(selected)+3)//4)),'#eeeaf1')
for slot,index in enumerate(selected): sheet.paste(images[index],(slot*720,0) if hands or room_mode else ((slot%4)*360,(slot//4)*510))
sheet.save(ROOT/f'private/{name}.png')
images[0].save(ROOT/f'private/{name}.gif',save_all=True,append_images=images[1:],duration=100,loop=0)
print(f'private/{name}.png; private/{name}.gif')
