import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {ROOM,createDesktopRoom,pickRoomFloor} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {configureAvatarCamera} from '../web_tool/mao-5070/draco/room-view.mjs';

const room=createDesktopRoom({theme:'lounge'});assert.equal(room.theme,'luxury-lounge');
room.setMode('window');
let meshes=0,instances=0,lights=0;
room.group.traverse(o=>{if(o.isMesh)meshes++;if(o.isInstancedMesh)instances+=o.count;if(o.isLight){lights++;assert.equal(o.castShadow,false);}});
assert.ok(instances>200,'decor was not batched');assert.ok(meshes<70,`too many room draw objects: ${meshes}`);assert.equal(lights,2);
assert.ok(!room.group.getObjectByName('floor-grid'),'old wire grid remains');
assert.equal(room.group.getObjectByName('disco-mirror-ball'),undefined,'removed hanging ball remains');
assert.equal(room.group.getObjectByName('disco-mirror-tiles'),undefined);
assert.equal(room.group.getObjectByName('disco-reflected-flecks'),undefined,'orphaned mirror-ball reflections remain');
assert.equal(room.group.getObjectByName('disco-equalizer'),undefined);
const head=room.group.getObjectByName('disco-moving-head'),firstHead=head.quaternion.clone();
for(let i=0;i<120;i++)room.update(1/60);
assert.ok(head.quaternion.angleTo(firstHead)>.01,'soft lighting never moves');
const stone=room.group.getObjectByName('disco-box-stone').material;
const shader={vertexShader:T.ShaderLib.standard.vertexShader,fragmentShader:T.ShaderLib.standard.fragmentShader};stone.onBeforeCompile(shader);
assert.ok(shader.vertexShader.includes('vMaoStone=(modelMatrix*maoStonePoint).xyz'));
assert.ok(shader.fragmentShader.includes('float vein='));assert.ok(shader.fragmentShader.includes('#include <color_fragment>'));
room.group.updateMatrixWorld(true);
room.group.traverse(o=>{
  assert.ok(o.matrixWorld.elements.every(Number.isFinite),`${o.name}: invalid animated transform`);
  if(o.name==='disco-light-beam')assert.ok(o.material.opacity<.04,'beams wash out the avatar');
});
// The entire navigation rectangle has a 45 cm body/hair/garment clearance.
for(const obstacle of room.obstacles){
  const w=ROOM.walk,pad=.45;
  const intersects=w.maxX+pad>obstacle.minX&&w.minX-pad<obstacle.maxX&&w.maxZ+pad>obstacle.minZ&&w.minZ-pad<obstacle.maxZ;
  assert.equal(intersects,false,`${obstacle.name} blocks the walking area`);
}
const camera=new T.PerspectiveCamera(32,1,.02,30);
configureAvatarCamera(camera,{mode:'window',view:{zoom:1.15},width:876,height:520});
for(const [x,z] of [[0,0],[-2.7,-3.3],[2.7,-3.3]]){
  const ndc=new T.Vector3(x,-.004,z).project(camera),p=pickRoomFloor(camera,new T.Vector2(ndc.x,ndc.y),room);
  assert.ok(p&&Math.hypot(p.x-x,p.z-z)<1e-5,'decor changed floor picking');
}
room.setMode('pet');const rotation=head.quaternion.clone();for(let i=0;i<60;i++)room.update(1/60);
assert.equal(room.group.visible,false);assert.ok(head.quaternion.equals(rotation),'Pet Mode keeps simulating a hidden room');assert.equal(pickRoomFloor(camera,new T.Vector2(),room),null);
// Every shared GPU resource must be released once, including instance buffers.
const resources=new Set(),counts=new Map();
room.group.traverse(o=>{if(o.geometry)resources.add(o.geometry);if(o.material)resources.add(o.material);if(o.isInstancedMesh)resources.add(o);});
for(const resource of resources){counts.set(resource,0);resource.addEventListener('dispose',()=>counts.set(resource,counts.get(resource)+1));}
room.dispose();for(const count of counts.values())assert.equal(count,1,'GPU resource leaked or disposed repeatedly');
console.log(JSON.stringify({luxuryLounge:true,removedMirrorBall:true,meshes,instances,lights,garmentClearance:.45,petHidden:true,disposedOnce:true}));
