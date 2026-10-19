// Capture actual skinned GLB geometry offline, without browser/desktop control.
import fs from 'node:fs';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {createMeshFixture} from '../tests/helpers/draco_mesh_fixture.mjs';
import {BodyActor} from '../web_tool/mao-5070/draco/motion.mjs';
import {FaceRig} from '../web_tool/mao-5070/draco/face-rig.mjs';
import {DesktopSpace,FloorFeet,locomotionFrame} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {ROOM,createDesktopRoom} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {configureAvatarCamera} from '../web_tool/mao-5070/draco/room-view.mjs';
const output=process.argv[2]||'draco-walk-qa';if(!/^[a-z0-9-]+$/.test(output))throw Error('Invalid QA output name');
const pose=process.argv[3]?.startsWith('--')?undefined:process.argv[3],stills=process.argv.includes('--stills'),roomMode=process.argv.includes('--room');
const storyWalk=process.argv.includes('--story-walk'),sampleOption=process.argv.indexOf('--frames'),sampleFrames=sampleOption<0?null:process.argv[sampleOption+1].split(',').map(Number);
const asset=createMeshFixture(),root=new T.Group(),wrapper=new T.Group();root.add(wrapper);wrapper.add(asset);root.updateMatrixWorld(true);
const bounds=new T.Box3().setFromObject(asset),center=bounds.getCenter(new T.Vector3()),scale=1.8/bounds.getSize(new T.Vector3()).y;
wrapper.scale.setScalar(scale);wrapper.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale);wrapper.updateMatrixWorld(true);
const footCenter=asset.getObjectByName('draco_ankleL').getWorldPosition(new T.Vector3()).add(asset.getObjectByName('draco_ankleR').getWorldPosition(new T.Vector3())).multiplyScalar(.5);wrapper.position.x-=footCenter.x;wrapper.position.z-=footCenter.z;wrapper.updateMatrixWorld(true);
const actor=new BodyActor(asset),face=new FaceRig(asset),space=new DesktopSpace(roomMode||storyWalk?{bounds:ROOM.walk,roam:'room',speed:.32}:{}),feet=new FloorFeet(actor.feet);
for(let i=0;i<180;i++)actor.update(1/120);face.update(0,false,1/60);
const meshes=[];asset.traverse(mesh=>{if(mesh.isMesh&&mesh.visible)meshes.push(mesh);});
const chunks=[];let offset=0;
function put(array){const bytes=Buffer.from(array.buffer,array.byteOffset,array.byteLength);const result={offset,count:array.length};chunks.push(bytes);offset+=bytes.length;return result;}
const meta={meshes:meshes.map(mesh=>({name:mesh.material.name,color:mesh.material.color.getHex(),uv:put(new Float32Array(mesh.geometry.attributes.uv?.array||[])),index:put(new Uint32Array(mesh.geometry.index.array))})),frames:[]};
if(roomMode){
  const room=createDesktopRoom();room.setMode('window');for(let i=0;i<120;i++)room.update(1/60);room.group.updateMatrixWorld(true);
  const decor=[],transform=new T.Matrix4(),instance=new T.Matrix4(),normalMatrix=new T.Matrix3(),p=new T.Vector3(),a=new T.Vector3(),b=new T.Vector3(),normal=new T.Vector3(),key=new T.Vector3(-.4,.8,.6).normalize();
  room.group.traverse(o=>{
    if(!o.isMesh||!o.visible||o.material.opacity<.4)return;
    for(let item=0;item<(o.isInstancedMesh?o.count:1);item++){
      if(o.isInstancedMesh){o.getMatrixAt(item,instance);transform.multiplyMatrices(o.matrixWorld,instance);}else transform.copy(o.matrixWorld);
      normalMatrix.getNormalMatrix(transform);
      const positions=new Float32Array(o.geometry.attributes.position.count*3),index=o.geometry.index?.array||Uint32Array.from({length:positions.length/3},(_,i)=>i);
      for(let i=0;i<positions.length/3;i++)p.fromBufferAttribute(o.geometry.attributes.position,i).applyMatrix4(transform).toArray(positions,i*3);
      const base=o.material.color.clone();if(o.isInstancedMesh&&o.instanceColor){const c=new T.Color();o.getColorAt(item,c);base.multiply(c);}
      const colors=new Uint8Array(index.length/3*4);
      for(let i=0;i<index.length;i+=3){
        p.fromBufferAttribute(o.geometry.attributes.position,index[i]);a.fromBufferAttribute(o.geometry.attributes.position,index[i+1]).sub(p);b.fromBufferAttribute(o.geometry.attributes.position,index[i+2]).sub(p);normal.crossVectors(a,b).applyNormalMatrix(normalMatrix);
        const shade=o.material.isMeshBasicMaterial?1:Math.max(.35,.58+.2*normal.y+.3*Math.max(0,normal.dot(key)));
        const c=base.clone().multiplyScalar(shade).convertLinearToSRGB();colors.set([c.r*255,c.g*255,c.b*255,o.material.opacity*255],i/3*4);
      }
      decor.push({position:put(positions),index:put(new Uint32Array(index)),colors:put(colors),side:o.material.side});
    }
  });
  meta.room={meshes:decor,theme:room.theme};room.dispose();
}
if(pose){if(!actor.play(pose))throw Error('Invalid pose');space.perform('stop');}else if(storyWalk)space.perform('walk');else if(roomMode)space.moveTo(2.8,-3.6);else space.perform('left');
for(let frame=0;frame<=60*(roomMode||storyWalk?18:5);frame++){
  if(storyWalk&&frame%120===0)actor.play(['laugh','surprise','think','shy','sad','shrug','emphasize','reassure','celebrate'][frame/120%9]);
  space.update(1/60);root.position.set(0,0,0);root.rotation.y=0;root.updateMatrixWorld(true);actor.setLocomotion(locomotionFrame(space,feet,1/60));actor.update(1/60);root.position.set(space.x,0,space.z);root.rotation.y=space.yaw;root.updateMatrixWorld(true);
  if(sampleFrames?!sampleFrames.includes(frame):stills?!(roomMode?[120,360,660,960]:[90,120,150,180]).includes(frame):frame%6)continue;
  const p=new T.Vector3(),positions=meshes.map(mesh=>{mesh.skeleton?.update();const array=new Float32Array(mesh.geometry.attributes.position.count*3);for(let i=0;i<array.length/3;i++){mesh.getVertexPosition(i,p).applyMatrix4(mesh.matrixWorld);p.toArray(array,i*3);}return put(array);});
  const entry={time:frame/60,phase:pose||space.phase,x:space.x,z:space.z,yaw:space.yaw,positions};
  if(roomMode){entry.roomCameras={};for(const kind of ['room','follow']){const camera=new T.PerspectiveCamera(32,1,.02,30);configureAvatarCamera(camera,{mode:'window',view:{zoom:1.15},width:720,height:640,roomView:{kind,focus:{x:space.x,z:space.z}}});entry.roomCameras[kind]={projection:camera.projectionMatrix.toArray(),view:camera.matrixWorldInverse.toArray()};}}
  meta.frames.push(entry);
}
fs.writeFileSync(`private/${output}.bin`,Buffer.concat(chunks));fs.writeFileSync(`private/${output}.json`,JSON.stringify(meta));console.log(JSON.stringify({frames:meta.frames.length,meshes:meshes.length,bytes:offset}));
