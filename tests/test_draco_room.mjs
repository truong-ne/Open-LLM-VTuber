import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {ROOM,createDesktopRoom,pickRoomFloor} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {DesktopSpace,FloorFeet,locomotionFrame} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {configureAvatarCamera} from '../web_tool/mao-5070/draco/room-view.mjs';
import {BodyActor} from '../web_tool/mao-5070/draco/motion.mjs';
import {createMeshFixture} from './helpers/draco_mesh_fixture.mjs';

const room=createDesktopRoom();room.setMode('window');room.group.updateMatrixWorld(true);
assert.equal(ROOM.width*ROOM.depth,48);
assert.equal(room.group.children.filter(o=>o.isMesh&&o.name.includes('wall')).length,3);
const camera=new T.PerspectiveCamera(32,1,.02,30);
configureAvatarCamera(camera,{mode:'window',view:{zoom:1.15},width:876,height:520});
for(const [x,z] of [[0,0],[-2.8,-3.4],[2.8,-3.4],[-2.8,.2],[2.8,.2]]){
  const p=new T.Vector3(x,-.004,z).project(camera),picked=pickRoomFloor(camera,new T.Vector2(p.x,p.y),room);
  assert.ok(picked&&Math.hypot(picked.x-x,picked.z-z)<1e-5,'floor click does not reach the selected room position');
}
room.setMode('pet');assert.equal(room.group.visible,false);assert.equal(pickRoomFloor(camera,new T.Vector2(),room),null,'hidden pet floor still captures clicks');
room.setMode('window');assert.ok(room.group.visible);
const run=(space,seconds)=>{for(let i=0;i<seconds*60;i++){space.update(1/60);assert.ok(space.x>=ROOM.walk.minX-1e-8&&space.x<=ROOM.walk.maxX+1e-8&&space.z>=ROOM.walk.minZ-1e-8&&space.z<=ROOM.walk.maxZ+1e-8,'path crossed a wall');}};
const make=()=>new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32});
const navigation=make();assert.equal(navigation.moveTo(NaN,0),false);navigation.moveTo(100,-100);run(navigation,28);
assert.ok(Math.abs(navigation.x-ROOM.walk.maxX)<1e-8&&Math.abs(navigation.z-ROOM.walk.minZ)<1e-8,'room destination still clamped to the old small pet patch');
const beforeX=navigation.x;navigation.perform('spin');run(navigation,9);
assert.equal(navigation.completedSpins,1);assert.ok(Math.abs(navigation.x-beforeX)<=.21,'spinning in a corner dragged Mao back to the center');
navigation.perform('stop');const stopped=[navigation.x,navigation.z];run(navigation,30);assert.deepEqual([navigation.x,navigation.z],stopped);
const auto=make();let minX=0,maxX=0,minZ=0,maxZ=-Infinity,maxSpeed=0;
for(let i=0;i<60*180;i++){auto.update(1/60);minX=Math.min(minX,auto.x);maxX=Math.max(maxX,auto.x);minZ=Math.min(minZ,auto.z);maxZ=Math.max(maxZ,auto.z);maxSpeed=Math.max(maxSpeed,auto.pose.speed);}
assert.ok(maxX-minX>3.5&&maxZ-minZ>2.5,'autonomous routes still occupy only the small pet area');assert.ok(maxSpeed<.61,'room walking is too fast for the foot gait');
// Same source mesh, normalization and stable bone simulation as the desktop,
// now with a multi-meter route and the faster room walking cadence.
const mesh=createMeshFixture(),root=new T.Group(),wrapper=new T.Group();root.add(wrapper);wrapper.add(mesh);mesh.updateMatrixWorld(true);
const box=new T.Box3().setFromObject(mesh),center=box.getCenter(new T.Vector3()),scale=1.8/box.getSize(new T.Vector3()).y;
wrapper.scale.setScalar(scale);wrapper.position.set(-center.x*scale,-box.min.y*scale,-center.z*scale);wrapper.updateMatrixWorld(true);
const footCenter=mesh.getObjectByName('draco_ankleL').getWorldPosition(new T.Vector3()).add(mesh.getObjectByName('draco_ankleR').getWorldPosition(new T.Vector3())).multiplyScalar(.5);wrapper.position.x-=footCenter.x;wrapper.position.z-=footCenter.z;wrapper.updateMatrixWorld(true);
const actor=new BodyActor(mesh),feet=new FloorFeet(actor.feet),walk=make();for(let i=0;i<180;i++)actor.update(1/120);walk.moveTo(2.8,-3.6);
let footError=0,clothPenetration=0,maxKneeStep=0,lastKnee;
for(let i=0;i<60*25;i++){
  if(i===60*18){walk.perform('stop');walk.setAudienceYaw(.7);}
  walk.update(1/60);root.position.set(0,0,0);root.rotation.y=0;root.updateMatrixWorld(true);actor.setLocomotion(locomotionFrame(walk,feet,1/60));actor.update(1/60);
  const knee=actor.joints.kneeL.getWorldQuaternion(new T.Quaternion());if(lastKnee)maxKneeStep=Math.max(maxKneeStep,knee.angleTo(lastKnee));lastKnee=knee;
  root.position.set(walk.x,0,walk.z);root.rotation.y=walk.yaw;root.updateMatrixWorld(true);
  for(const side of ['L','R'])footError=Math.max(footError,actor.joints['ankle'+side].getWorldPosition(new T.Vector3()).distanceTo(feet.legs[side].point));
  clothPenetration=Math.max(clothPenetration,actor.dynamics.audit.maxPenetration);
}
assert.ok(Math.abs(walk.yaw-.7)<1e-5,'mesh actor never returned attention to the camera');
assert.ok(footError<.004,`room route loses foot contact: ${footError}`);assert.ok(clothPenetration<.003,`room route garment penetration: ${clothPenetration}`);assert.ok(maxKneeStep<.2,`room knee snaps: ${maxKneeStep}`);
room.dispose();console.log(JSON.stringify({roomArea:48,petRoomHidden:true,pointPicking:true,wallLimits:true,autoRange:[maxX-minX,maxZ-minZ],footError,clothPenetration,maxKneeStep}));
