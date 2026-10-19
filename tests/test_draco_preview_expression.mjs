import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {createNativeMeshFixture} from './helpers/draco_mesh_fixture.mjs';
import {skirtCoverageProbe} from './helpers/draco_skirt_coverage.mjs';
import {PerformanceBodyActor,PERFORMANCE_ACTIONS,HIP_SWAY_PERIOD} from '../web_tool/mao-5070/draco/performance-motion.mjs';
import {PerformanceFaceRig,FACE_PRESETS} from '../web_tool/mao-5070/draco/performance-face.mjs';
const {asset}=createNativeMeshFixture(),actor=new PerformanceBodyActor(asset);
for(let i=0;i<180;i++)actor.update(1/120);
const face=new PerformanceFaceRig(asset);
const shader={uniforms:{},vertexShader:'#include <morphtarget_vertex>',fragmentShader:'#include <map_fragment>'};
face.face.material.onBeforeCompile(shader);
assert.ok(shader.fragmentShader.includes('previewSmile*.003*pow('),'smile must curve the face opening too');
assert.ok(shader.fragmentShader.includes('maoMouthOpen'),'speech shader must survive preview extension');
assert.equal(shader.uniforms.previewSmile,face.smileUniform);
const step=(seconds,volume=0,playing=false)=>{for(let i=0;i<seconds*120;i++){actor.update(1/120);face.update(volume,playing,1/120);}asset.updateMatrixWorld(true);};
assert.equal(PERFORMANCE_ACTIONS.length,19);assert.equal(Object.keys(FACE_PRESETS).length,5);
assert.equal(face.setExpression('invalid'),false);
for(const name of Object.keys(FACE_PRESETS)){
  face.nextBlink=Infinity;assert.equal(face.setExpression(name),true);step(.8);
  const closed=['squint','flat'].includes(name);
  assert.equal(face.iris.visible,!closed,name);
  if(closed){assert.ok(face.eyeClose>.999);assert.equal(face.inks.filter(i=>i.mesh.visible&&i.style===name).length,2);}
  for(const mesh of face.meshes)assert.ok(mesh.morphTargetInfluences.every(Number.isFinite));
  for(const t of face.targets)assert.ok(t.mesh.geometry.morphAttributes.position.every(a=>a.array.every(Number.isFinite)));
}
assert.equal(face.setExpression('tongue'),false);assert.equal(asset.getObjectByName('preview-tongue-out'),undefined);
face.setExpression('neutral');step(1);assert.ok(face.eyeClose<.001);
face.nextBlink=face.time+.05;let blink=0;for(let i=0;i<60;i++){face.update(0,false,1/120);blink=Math.max(blink,face.eyeClose);}assert.ok(blink>.99);assert.ok(face.eyeClose<.001);
step(.8,.65,true);assert.ok(face.open>.8,'speech must still drive the mouth');step(.8);assert.ok(face.open<.001);

// Facial additions must share real head skinning, not remain fixed on screen.
face.setExpression('squint');step(.8);
const ink=face.inks.find(i=>i.style==='squint').mesh,head=actor.joints.head,p=new T.Vector3();
ink.skeleton.update();ink.getVertexPosition(0,p).applyMatrix4(ink.matrixWorld);
const before=p.clone(),origin=head.getWorldPosition(new T.Vector3()),q=new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),.4);
const local=head.quaternion.clone(),parent=head.parent.getWorldQuaternion(new T.Quaternion());
head.quaternion.premultiply(parent.clone().invert().multiply(q).multiply(parent));asset.updateMatrixWorld(true);ink.skeleton.update();
ink.getVertexPosition(0,p).applyMatrix4(ink.matrixWorld);
assert.ok(p.distanceTo(before.clone().sub(origin).applyQuaternion(q).add(origin))<1e-5,'eye ink detached from the head');
head.quaternion.copy(local);

const probe=skirtCoverageProbe(actor,{scaled:true,levels:[-.2087,-.1987,-.1787,-.1587,-.1387,-.1187,-.0987,-.0787,-.0587]});
const report={};
for(const action of ['hipSway','refuse']){
  assert.equal(actor.play(action),true);
  let outside=0,drift=0,handStep=0;const last=new Map(),hips=[],heads=[];
  for(let frame=0;frame<60*8;frame++){
    actor.update(1/60);face.update(0,false,1/60);asset.updateMatrixWorld(true);
    drift=Math.max(drift,actor.audit.footDrift);
    for(const side of ['L','R']){const point=actor.joints['wrist'+side].getWorldPosition(new T.Vector3());if(last.has(side))handStep=Math.max(handStep,point.distanceTo(last.get(side)));last.set(side,point);}
    if(frame>90&&frame<270){hips.push(actor.joints.waist.getWorldPosition(new T.Vector3()).x);heads.push(actor.joints.head.quaternion.clone());}
    if(action==='refuse'&&frame===180)for(const side of ['L','R']){
      const wrist=actor.joints['wrist'+side],change=wrist.getWorldQuaternion(new T.Quaternion()).multiply(actor.rest.get(wrist).worldInverse);
      assert.ok(actor.palms[side].along.clone().applyQuaternion(change).y>.65,'refusal fingers must point upward');
      assert.ok(actor.palms[side].normal.clone().applyQuaternion(change).z>.65,'refusal palms must face viewers');
    }
    if(frame%12===0)outside=Math.max(outside,probe().maxOutside);
  }
  const hipRange=Math.max(...hips)-Math.min(...hips),headRange=Math.max(...heads.map(q=>q.angleTo(heads[0])));
  assert.ok(outside<.001,`${action}: thigh poke ${outside}`);
  assert.ok(drift<.004,`${action}: feet slip ${drift}`);
  assert.ok(handStep<.04,`${action}: hand jumps ${handStep}`);
  if(action==='hipSway'){
    assert.ok(hipRange>.05&&hipRange<.08,`reference-sized hip sway range ${hipRange}`);
    const peaks=[];for(let i=1;i<hips.length-1;i++)if(hips[i]>hips[i-1]&&hips[i]>=hips[i+1])peaks.push(i/60);
    assert.ok(peaks.length>=2,'hip sway must repeat at the faster reference cadence');
    for(let i=1;i<peaks.length;i++)assert.ok(Math.abs(peaks[i]-peaks[i-1]-HIP_SWAY_PERIOD)<.055,'hip sway cadence differs from target');
    report.hipPeriod=HIP_SWAY_PERIOD;
  }
  if(action==='refuse')assert.ok(headRange>.18,`refusal head shake ${headRange}`);
  assert.equal(actor.action,'idle','action should settle back to idle');
  report[action]={outside,drift,handStep,hipRange,headRange};
}
// Balance reacts to a turn/translation, stays subtle, then settles rather
// than starting a perpetual oscillation after the input stops.
actor.setLocomotion({acceleration:{x:1,z:-1},yawAcceleration:1});
let maxBalance=0,maxBalanceStep=0,previousBalance=0;
for(let frame=0;frame<180;frame++){
  actor.update(1/120);const follow=actor.upperBodyFollow;
  maxBalance=Math.max(maxBalance,...Object.values(follow).map(Math.abs));
  maxBalanceStep=Math.max(maxBalanceStep,Math.abs(follow.roll-previousBalance));previousBalance=follow.roll;
}
assert.ok(actor.upperBodyFollow.roll>.005&&actor.upperBodyFollow.pitch>.005&&actor.upperBodyFollow.yaw<-.002,'upper body must respond to acceleration');
assert.ok(maxBalance<.013&&maxBalanceStep<.001,'balance must remain subtle and continuous');
actor.setLocomotion({acceleration:{x:0,z:0},yawAcceleration:0});
for(let frame=0;frame<240;frame++)actor.update(1/120);
assert.ok(Object.values(actor.upperBodyFollow).every(v=>Math.abs(v)<.00002),'upper body must settle after stopping');
for(const profile of [...actor.previewHair,...actor.previewCoat]){
  assert.ok(Math.abs(profile.segment.drag-profile.drag)<.001,'cloth settings must settle back after motion');
  assert.ok(Math.abs(profile.segment.stiffness-profile.stiffness)<.001);
}
console.log(JSON.stringify({facialPresets:Object.keys(FACE_PRESETS).length,headSkinning:true,blink:true,speech:true,balance:{maxBalance,maxBalanceStep,settles:true},...report}));
