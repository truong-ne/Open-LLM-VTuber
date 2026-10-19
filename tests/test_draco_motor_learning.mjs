import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {MotorPolicy,validateMotor} from '../web_tool/mao-5070/draco/motor-policy.mjs';
import {AdaptiveBodyActor} from '../web_tool/mao-5070/draco/motor-body.mjs';
import {AdaptiveFaceRig} from '../web_tool/mao-5070/draco/motor-face.mjs';
import {createNativeMeshFixture} from './helpers/draco_mesh_fixture.mjs';
import {skirtCoverageProbe} from './helpers/draco_skirt_coverage.mjs';
import {DesktopSpace,FloorFeet,locomotionFrame} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {SpeechAttention} from '../web_tool/mao-5070/draco/speech-attention.mjs';
const saved=new Map(),storage={getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},policy=new MotorPolicy(storage);
for(const invalid of [{tilt:NaN},{left:Infinity},{tilt:true},{bone:3},{duration:4},[]])assert.equal(validateMotor(invalid),null);
assert.equal(validateMotor({tilt:999}).tilt,12);
assert.equal(policy.feedback('Có khán giả bảo Mao tay thấp hơn'),false);
assert.equal(policy.feedback('Câu chuyện có đoạn: Mao cử động nhẹ hơn'),false);
assert.equal(policy.feedback('Mao tay thấp hơn'),true);
assert.equal(policy.feedback('Mao cử động nhẹ hơn'),true);
assert.equal(policy.feedback('Mao cử động nhanh hơn'),true);
const reloaded=new MotorPolicy(storage);
assert.equal(reloaded.profile.height,-.015);assert.equal(reloaded.profile.gain,.88);assert.equal(reloaded.revision,3);
assert.equal(reloaded.feedback('/co-the hoan-tac'),true);assert.equal(reloaded.profile.tempo,1);
assert.equal(new MotorPolicy(storage).profile.tempo,1,'undo must persist across app restarts');
for(let i=0;i<100;i++)policy.feedback('Mao tay thấp hơn');
assert.equal(policy.profile.height,-.06);assert.equal(policy.history.length,32);
const unavailable=new MotorPolicy({getItem(){throw Error('denied');},setItem(){throw Error('denied');}});
unavailable.feedback('Mao cử động nhẹ hơn');assert.equal(unavailable.saved,false);

const {asset,root}=createNativeMeshFixture(),actor=new AdaptiveBodyActor(asset,reloaded),face=new AdaptiveFaceRig(asset);
for(let i=0;i<180;i++)actor.update(1/120);
const probe=skirtCoverageProbe(actor,{scaled:true,levels:[-.2087,-.1787,-.1387,-.0987,-.0587]});
let maxFoot=0,maxOutside=0,maxAngularStep=0,previous=actor.joints.head.quaternion.clone();const samples=[];
const simulate=(pose,seconds)=>{
  assert.equal(actor.setMotor(pose),true);
  for(let i=0;i<seconds*60;i++){
    actor.update(1/60);face.setMotor(reloaded.apply(actor.motorRaw),actor.motorAmount);face.update(.22,true,1/60);
    maxFoot=Math.max(maxFoot,actor.audit.footDrift);maxAngularStep=Math.max(maxAngularStep,previous.angleTo(actor.joints.head.quaternion));previous.copy(actor.joints.head.quaternion);
    if(i%30===0)maxOutside=Math.max(maxOutside,probe().maxOutside);
    for(const bone of actor.bones)assert.ok([...bone.position.toArray(),...bone.quaternion.toArray()].every(Number.isFinite));
  }
  samples.push({head:actor.joints.head.quaternion.clone(),wrist:actor.joints.wristR.getWorldPosition(new T.Vector3()).clone(),smile:face.smileUniform.value,brow:face.targets[0].mesh.morphTargetInfluences[face.targets[0].brow]});
};
// Opposite continuous intentions must produce distinct actual mesh poses,
// without switching to any named action clip.
simulate({tilt:9,nod:3,lean:2,right:.75,left:.15,height:.04,smile:.65,brow:.2,duration:5},2);
simulate({tilt:-8,nod:-4,lean:-3,right:.25,left:.8,height:-.07,smile:.2,brow:.8,eyes:.7,duration:5},2);
assert.ok(samples[0].head.angleTo(samples[1].head)>.15,'intent did not change head pose');
assert.ok(samples[0].wrist.distanceTo(samples[1].wrist)>.03,'intent did not change hand IK');
assert.ok(samples[0].smile-samples[1].smile>.3);assert.ok(samples[1].brow-samples[0].brow>.4);
const before=reloaded.apply({right:.7,height:0,tilt:8});reloaded.feedback('Mao tay thấp hơn');reloaded.feedback('Mao cử động nhẹ hơn');
const after=reloaded.apply({right:.7,height:0,tilt:8});assert.ok(after.height<before.height&&after.right<before.right&&after.tilt<before.tilt);
simulate({tilt:999,nod:-999,lean:999,left:1,right:1,height:999,smile:1,brow:1,eyes:1,duration:2},5);
assert.equal(actor.motorActive,false,'pose TTL never ended');assert.equal(actor.motorRaw,null);
assert.ok(maxAngularStep<.07,`head snaps: ${maxAngularStep}`);assert.ok(maxFoot<.001,`foot slip: ${maxFoot}`);assert.ok(maxOutside<.001,`skirt penetration: ${maxOutside}`);
// The adaptive motor must also respect the existing locomotion and speech lock.
const space=new DesktopSpace(),feet=new FloorFeet(actor.feet),attention=new SpeechAttention();space.perform('walk');
for(let i=0;i<120;i++){space.update(1/60);actor.setLocomotion(locomotionFrame(space,feet,1/60));actor.update(1/60);}
attention.focus(space);actor.setMotor({tilt:7,right:.6,lean:4,duration:7});
for(let i=0;i<360;i++){attention.update(space,true);space.update(1/60);actor.setLocomotion(locomotionFrame(space,feet,1/60));actor.update(1/60);}
const x=space.x,z=space.z;
for(let i=0;i<300;i++){attention.update(space,true);space.update(1/60);actor.setLocomotion(locomotionFrame(space,feet,1/60));actor.update(1/60);}
assert.ok(Math.hypot(space.x-x,space.z-z)<1e-8,'motor bypassed speech position lock');
assert.ok(Math.abs(space.yaw-space.audienceYaw)<.025,'motor turned body away from camera');
console.log(JSON.stringify({persistentFeedback:true,composedActualRig:true,poseExpiry:true,maxFoot,maxOutside,maxAngularStep,speechLocked:true}));
