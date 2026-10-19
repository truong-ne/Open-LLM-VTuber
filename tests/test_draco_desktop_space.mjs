import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {DesktopSpace,FloorFeet,desktopCommand,locomotionFrame} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {BodyActor} from '../web_tool/mao-5070/draco/motion.mjs';
import {createDracoRig} from './helpers/draco_fixture.mjs';
import {createNativeBridge} from '../web_tool/mao-5070/draco/native-bridge.mjs';
import {createMeshFixture} from './helpers/draco_mesh_fixture.mjs';
for(const phrase of ['Mao xoay một vòng đi!','xoay 1 vong','quay 360 độ','Mao quay tròn một vòng'])assert.equal(desktopCommand(phrase),'spin');
for(const phrase of ['Đừng xoay một vòng','không quay một vòng nhé','mình đang quay phim','kể một câu chuyện'])assert.equal(desktopCommand(phrase),null);
assert.equal(desktopCommand('Mao dừng lại'),'stop');
assert.equal(desktopCommand('Đi sang trái'),'left');assert.equal(desktopCommand('đi lại một chút'),'walk');
assert.equal(desktopCommand('Mao bước nhẹ qua bên trái'),'left');assert.equal(desktopCommand('bước sang phải'),'right');
assert.equal(desktopCommand('Không bước sang trái'),null);
for(const command of ['back','forward','walk']){
  const route=new DesktopSpace();route.perform(command);let movingFrames=0,turnFrames=0;
  for(let frame=0;frame<60*19;frame++){
    route.update(1/60);
    if(route.pose.speed>.01){
      const alignment=(Math.sin(route.yaw)*route.pose.vx+Math.cos(route.yaw)*route.pose.vz)/route.pose.speed;
      assert.ok(alignment>.995,`${command}: translating sideways instead of facing the walking direction`);movingFrames++;
    }
    if(route.phase==='orient'){assert.ok(route.pose.speed<1e-9,'body started sliding before orienting');turnFrames++;}
  }
  assert.ok(movingFrames>20);
  assert.ok(Math.abs(route.yaw)<1e-8,'pet did not face its audience after arriving');
}
for(const direction of [-1,1]){
  const sideSpace=new DesktopSpace(),rest={L:new T.Vector3(.055,.12,0),R:new T.Vector3(-.055,.12,0)},sideFeet=new FloorFeet(rest);
  sideSpace.perform(direction<0?'left':'right');let firstSwing,maxLift=0,previous,maxStep=0;
  for(let frame=0;frame<60*4;frame++){
    sideSpace.update(1/60);locomotionFrame(sideSpace,sideFeet,1/60);
    assert.ok(Math.abs(sideSpace.yaw)<1e-9,'sidestep turned away from the viewer');
    assert.ok(sideFeet.legs.L.point.x>sideFeet.legs.R.point.x,'sidestep crossed the legs');
    for(const side of ['L','R']){const leg=sideFeet.legs[side];if(leg.swing&&!firstSwing)firstSwing=side;maxLift=Math.max(maxLift,leg.point.y-rest[side].y);}
    const point=sideFeet.legs.L.point.clone();if(previous)maxStep=Math.max(maxStep,point.distanceTo(previous));previous=point;
  }
  assert.equal(firstSwing,direction<0?'R':'L','trailing foot moved before the opening foot');
  assert.ok(Math.abs(sideSpace.x-direction*.16)<1e-9);assert.ok(maxLift>.02&&maxLift<.026);assert.ok(maxStep<.015,'sidestep foot snaps');
  for(const side of ['L','R'])assert.ok(sideFeet.legs[side].point.distanceTo(rest[side].clone().add(new T.Vector3(sideSpace.x,0,0)))<1e-8,'trailing foot did not close into stance');
}
for(const next of ['spin','stop','right']){
  const s=new DesktopSpace(),f=new FloorFeet({L:new T.Vector3(.055,.12,0),R:new T.Vector3(-.055,.12,0)});s.perform('left');
  for(let i=0;i<45;i++){s.update(1/60);locomotionFrame(s,f,1/60);}s.perform(next);
  for(let i=0;i<180;i++){s.update(1/60);const g=locomotionFrame(s,f,1/60);for(const p of Object.values(g.feet))assert.ok(p.toArray().every(Number.isFinite),'interrupted sidestep produced invalid IK goals');}
}
const fpsRuns=[];
for(const fps of [30,60,120]){
  const space=new DesktopSpace();space.perform('spin');let enteredSpin=false,previousYaw=0,totalRotation=0,maxSpeed=0;
  for(let f=0;f<fps*9;f++){
    space.update(1/fps);let delta=space.yaw-previousYaw;if(delta<-Math.PI)delta+=Math.PI*2;if(delta>Math.PI)delta-=Math.PI*2;totalRotation+=delta;previousYaw=space.yaw;
    maxSpeed=Math.max(maxSpeed,space.pose.speed);
    if(space.phase==='spin'&&!enteredSpin){assert.ok(space.z<=-.419,'spin started before stepping away');enteredSpin=true;}
    assert.ok(space.x>=-.42&&space.x<=.42&&space.z>=-.72&&space.z<=.1);
  }
  assert.equal(space.completedSpins,1);assert.equal(space.phase,'idle');assert.ok(Math.abs(totalRotation-Math.PI*2)<1e-9,'rotation was not exactly one full turn');assert.ok(maxSpeed<.4);
  fpsRuns.push(space.z);
}
assert.ok(Math.max(...fpsRuns)-Math.min(...fpsRuns)<1e-9);
const paused=new DesktopSpace();paused.perform('spin');paused.update(.1);const pose=[paused.x,paused.z,paused.yaw];for(let i=0;i<20;i++)paused.update(.1,{paused:true});assert.deepEqual([paused.x,paused.z,paused.yaw],pose);
const bridge=createNativeBridge();assert.ok(bridge.command('xoay một vòng'));assert.equal(bridge.pendingCommand,'spin');let command;
bridge.renderer={perform:value=>{command=value;return true;}};bridge.command('đi sang trái');assert.equal(command,'left');

// Use the actual rig and foot IK with the complete retreat + turn choreography.
// These are geometry/simulation tests, without controlling a desktop/browser.
const actor=new BodyActor(createDracoRig());for(let i=0;i<120;i++)actor.update(1/120);
const space=new DesktopSpace(),feet=new FloorFeet(actor.feet);space.perform('spin');
let maxFootError=0,maxLift=0,maxJointStep=0,previous,worldStanceFrames=0,maxStanceDrift=0;
const prior=new Map();
for(let frame=0;frame<60*9;frame++){
  space.update(1/60);const gait=locomotionFrame(space,feet,1/60),goals=gait.feet;
  actor.setLocomotion(gait);actor.update(1/60);
  for(const side of ['L','R']){
    const leg=feet.legs[side];maxLift=Math.max(maxLift,goals[side].y-actor.feet[side].y);
    if(!leg.swing&&!leg.landing&&prior.get(side)?.stance&&space.pose.speed>.01){worldStanceFrames++;maxStanceDrift=Math.max(maxStanceDrift,leg.anchor.distanceTo(prior.get(side).point));}
    prior.set(side,{stance:!leg.swing&&!leg.landing,point:leg.anchor.clone()});
  }
  const knee=actor.joints.kneeL.getWorldQuaternion(new T.Quaternion());if(previous)maxJointStep=Math.max(maxJointStep,knee.angleTo(previous));previous=knee;
  maxFootError=Math.max(maxFootError,actor.audit.footDrift);
  for(const bone of actor.bones)assert.ok(bone.quaternion.toArray().every(Number.isFinite),'non-finite rig transform');
  for(const segment of actor.dynamics.segments)assert.ok(segment.current.toArray().every(Number.isFinite),'cloth simulation diverged');
  assert.ok(actor.dynamics.audit.maxStretch<1e-7,'garment bone length changed');
}
assert.ok(maxLift>.025,'walking feet never leave the floor');assert.ok(worldStanceFrames>10&&maxStanceDrift<1e-8,'stance foot slides over the floor');assert.ok(maxFootError<.004,`leg IK cannot reach walking targets: ${maxFootError}`);assert.ok(maxJointStep<.30,`knee snaps while walking: ${maxJointStep}`);
// Exercise the same normalized GLB scene and outer-root placement used by the
// native renderer, including lateral walking and the skirt/thigh collision.
const mesh=createMeshFixture(),displayRoot=new T.Group(),wrapper=new T.Group();displayRoot.add(wrapper);wrapper.add(mesh);mesh.updateMatrixWorld(true);
const bounds=new T.Box3().setFromObject(mesh),center=bounds.getCenter(new T.Vector3()),scale=1.8/bounds.getSize(new T.Vector3()).y;
wrapper.scale.setScalar(scale);wrapper.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale);wrapper.updateMatrixWorld(true);
const footCenter=mesh.getObjectByName('draco_ankleL').getWorldPosition(new T.Vector3()).add(mesh.getObjectByName('draco_ankleR').getWorldPosition(new T.Vector3())).multiplyScalar(.5);
wrapper.position.x-=footCenter.x;wrapper.position.z-=footCenter.z;wrapper.updateMatrixWorld(true);
const actual=new BodyActor(mesh),walk=new DesktopSpace(),actualFeet=new FloorFeet(actual.feet);for(let i=0;i<180;i++)actual.update(1/120);walk.perform('walk');
let maxRenderedFootError=0,maxWalkingClothPenetration=0,maxWalkingKneeStep=0,lastKnee,worstWalkingContact;
for(let frame=0;frame<60*13;frame++){
  walk.update(1/60);displayRoot.position.set(0,0,0);displayRoot.rotation.y=0;displayRoot.updateMatrixWorld(true);
  actual.setLocomotion(locomotionFrame(walk,actualFeet,1/60));actual.update(1/60);
  const knee=actual.joints.kneeL.getWorldQuaternion(new T.Quaternion());if(lastKnee)maxWalkingKneeStep=Math.max(maxWalkingKneeStep,knee.angleTo(lastKnee));lastKnee=knee;
  displayRoot.position.set(walk.x,0,walk.z);displayRoot.rotation.y=walk.yaw;displayRoot.updateMatrixWorld(true);
  for(const side of ['L','R'])maxRenderedFootError=Math.max(maxRenderedFootError,actual.joints['ankle'+side].getWorldPosition(new T.Vector3()).distanceTo(actualFeet.legs[side].point));
  if(actual.dynamics.audit.maxPenetration>maxWalkingClothPenetration){maxWalkingClothPenetration=actual.dynamics.audit.maxPenetration;worstWalkingContact={frame,phase:walk.phase,...actual.dynamics.audit.blocked};}
}
assert.ok(maxRenderedFootError<.004,`display root fights the planted feet: ${maxRenderedFootError}`);
assert.ok(maxWalkingClothPenetration<.003,`skirt enters the thighs while walking: ${JSON.stringify({depth:maxWalkingClothPenetration,...worstWalkingContact})}`);
assert.ok(maxWalkingKneeStep<.16,`lateral walking knee snaps: ${maxWalkingKneeStep}`);
let sideFootError=0,sideClothPenetration=0,sideContact;
for(const direction of [-1,1]){
  displayRoot.position.set(0,0,0);displayRoot.rotation.y=0;displayRoot.updateMatrixWorld(true);actual.setLocomotion(null);for(let i=0;i<180;i++)actual.update(1/120);
  const s=new DesktopSpace(),f=new FloorFeet(actual.feet);s.perform(direction<0?'left':'right');
  for(let i=0;i<60*4;i++){
    s.update(1/60);displayRoot.position.set(0,0,0);displayRoot.rotation.y=0;displayRoot.updateMatrixWorld(true);actual.setLocomotion(locomotionFrame(s,f,1/60));actual.update(1/60);
    displayRoot.position.set(s.x,0,s.z);displayRoot.rotation.y=s.yaw;displayRoot.updateMatrixWorld(true);
    for(const side of ['L','R'])sideFootError=Math.max(sideFootError,actual.joints['ankle'+side].getWorldPosition(new T.Vector3()).distanceTo(f.legs[side].point));
    if(actual.dynamics.audit.maxPenetration>sideClothPenetration){sideClothPenetration=actual.dynamics.audit.maxPenetration;sideContact={direction,frame:i,phase:s.phase,...actual.dynamics.audit.blocked};}
  }
}
assert.ok(sideFootError<.004,`sidestep cannot plant feet: ${sideFootError}`);assert.ok(sideClothPenetration<.003,`sidestep garment collision: ${JSON.stringify({depth:sideClothPenetration,...sideContact})}`);
const repeat=new DesktopSpace(),repeatFeet=new FloorFeet(actor.feet);let maxSoleStep=0;
for(let turn=0;turn<2;turn++){
  repeat.perform('spin');let previousYaw;
  for(let frame=0;frame<60*9;frame++){repeat.update(1/60);repeatFeet.update(repeat,1/60);const yaw=repeatFeet.legs.L.yaw;if(previousYaw!==undefined)maxSoleStep=Math.max(maxSoleStep,Math.abs(yaw-previousYaw));previousYaw=yaw;}
}
assert.equal(repeat.completedSpins,2);assert.ok(maxSoleStep<.15,'repeating a spin reverses a foot through a full turn');
const roam=new DesktopSpace();for(let f=0;f<60*90;f++)roam.update(1/60);assert.ok(roam.distance>.4,'desktop pet never walks autonomously');
roam.perform('stop');const stopped=[roam.x,roam.z];for(let f=0;f<60*90;f++)roam.update(1/60);assert.deepEqual([roam.x,roam.z],stopped,'stop command resumed wandering on its own');
console.log(JSON.stringify({fullTurn:true,retreatBeforeTurn:true,completedSpins:space.completedSpins,maxFootError,maxLift,maxJointStep,maxStanceDrift,maxRenderedFootError,maxWalkingClothPenetration,maxWalkingKneeStep,sideFootError,sideClothPenetration,autoWalkDistance:roam.distance}));
