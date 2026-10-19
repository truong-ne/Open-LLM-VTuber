import fs from 'node:fs';
import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {BodyActor,ACTIONS,bakeBodyClips} from '../web_tool/mao-5070/draco/motion.mjs';
import {createDracoRig as asset,boneCount} from './helpers/draco_fixture.mjs';
const report={sourceBones:boneCount,bones:0,actions:{},maxFootDrift:0,maxStep:0,maxClothStretch:0,maxClothPenetration:0,clothContacts:0,maxClothAngle:0,clothSegments:0,maxWristAngularStep:0,bowTrunkDegrees:0};
for(const action of ACTIONS){
  const a=new BodyActor(asset());report.bones=a.bones.length;for(let i=0;i<180;i++)a.update(1/120);a.play(action);let last,lastWrist,lastWristR,rightMin=Infinity,rightMax=-Infinity,handMin=Infinity,handMax=-Infinity,headMin=Infinity,headMax=-Infinity,rootMin=Infinity,rootMax=-Infinity;
  const find=a.asset.getObjectByName.bind(a.asset);let searches=0;a.asset.getObjectByName=(...args)=>{searches++;return find(...args);};
  for(let frame=0;frame<60*9;frame++){
    a.update(1/60,action==='talk'&&frame<360?.15:0);
    if(action==='bow'){
      const delta=a.joints.chest.getWorldQuaternion(new T.Quaternion()).multiply(a.rest.get(a.joints.chest).worldInverse);
      const up=new T.Vector3(0,1,0).applyQuaternion(delta);
      report.bowTrunkDegrees=Math.max(report.bowTrunkDegrees,T.MathUtils.radToDeg(Math.atan2(up.z,up.y)));
    }
    for(const b of a.bones){assert.ok(b.quaternion.toArray().every(Number.isFinite));assert.ok(Math.abs(b.quaternion.length()-1)<1e-6);}
    const hand=a.joints.wristL.getWorldPosition(new T.Vector3());if(last)report.maxStep=Math.max(report.maxStep,hand.distanceTo(last));last=hand;
    const wristQ=a.joints.wristL.getWorldQuaternion(new T.Quaternion());if(lastWrist)report.maxWristAngularStep=Math.max(report.maxWristAngularStep,wristQ.angleTo(lastWrist));lastWrist=wristQ;
    const rightQ=a.joints.wristR.getWorldQuaternion(new T.Quaternion());if(lastWristR)report.maxWristAngularStep=Math.max(report.maxWristAngularStep,rightQ.angleTo(lastWristR));lastWristR=rightQ;
    const rightY=a.joints.wristR.getWorldPosition(new T.Vector3()).y;rightMin=Math.min(rightMin,rightY);rightMax=Math.max(rightMax,rightY);
    handMin=Math.min(handMin,hand.y);handMax=Math.max(handMax,hand.y);headMin=Math.min(headMin,a.joints.head.quaternion.x);headMax=Math.max(headMax,a.joints.head.quaternion.x);rootMin=Math.min(rootMin,a.joints.waist.position.x);rootMax=Math.max(rootMax,a.joints.waist.position.x);
    report.maxFootDrift=Math.max(report.maxFootDrift,a.audit.footDrift);
    report.clothSegments=a.dynamics.segments.length;
    report.maxClothStretch=Math.max(report.maxClothStretch,a.dynamics.audit.maxStretch);
    report.maxClothAngle=Math.max(report.maxClothAngle,a.dynamics.audit.maxAngle);
    report.clothContacts+=a.dynamics.audit.contacts;
    if(a.dynamics.audit.maxPenetration>report.maxClothPenetration){report.maxClothPenetration=a.dynamics.audit.maxPenetration;report.blocked={action,frame,...a.dynamics.audit.blocked};}
    for(const segment of a.dynamics.segments){
      assert.ok(segment.current.toArray().every(Number.isFinite),'garment simulation diverged');
      assert.ok(segment.current.distanceTo(segment.b.getWorldPosition(new T.Vector3()))-segment.length<1e-6,'garment stretches');
    }
  }
  assert.equal(searches,0,'animation should reuse cached bone references');
  assert.equal(a.action,'idle');report.actions[action]={handHeightRange:handMax-handMin,rightHandHeightRange:rightMax-rightMin,headRotationRange:headMax-headMin,rootTravel:rootMax-rootMin};
}
assert.ok(report.bowTrunkDegrees>29&&report.bowTrunkDegrees<31,`bow should reach 30 degrees, got ${report.bowTrunkDegrees}`);
assert.ok(report.clothSegments>180,'incomplete garment chains');
assert.ok(report.maxClothPenetration<.003,`garment embedded: ${JSON.stringify({depth:report.maxClothPenetration,...report.blocked})}`);
assert.ok(report.maxClothStretch<1e-7,'garment bone lengths are not constrained');
// The normal choreography should avoid contacts. Force one controlled contact
// to test separation, instead of changing the pose merely to hit a collider.
const fixture=new BodyActor(asset()),dynamics=fixture.dynamics;
const cloth=dynamics.segments.find(s=>s.type==='coat');dynamics.segments=[cloth];
const head=fixture.rest.get(cloth.b).worldPosition;
const disturbed=cloth.current.clone().sub(head).applyAxisAngle(new T.Vector3(0,0,1),.15).add(head);
cloth.current.copy(disturbed);cloth.previous.copy(disturbed);cloth.initialized=true;cloth.ignore.clear();
dynamics.buildColliders=()=>{dynamics.colliders=[{a:disturbed.clone(),b:disturbed.clone(),r:.001,types:['coat']}];};
dynamics.step(1/120);
assert.ok(dynamics.audit.contacts>0,'forced capsule contact was missed');
assert.ok(dynamics.audit.maxPenetration<.0005,'forced capsule contact remains embedded');
report.collisionFixture={...dynamics.audit};
assert.ok(report.maxClothAngle<=.650001,'garment exceeds angular limits');
assert.ok(report.maxFootDrift<.0001,'feet slide away from their anchors');
assert.ok(report.actions.greet.handHeightRange>.35,'greeting never raises the hand');
for(const name of ['chuckle','laugh','surprise','shy','shrug','celebrate'])assert.ok(report.actions[name].handHeightRange>.15,`${name} has no visible gesture`);
for(const name of ['think','emphasize'])assert.ok(report.actions[name].rightHandHeightRange>.20,`${name} has no right-hand gesture`);
assert.ok(report.actions.sad.headRotationRange>.04,'sad head pose absent');
assert.ok(report.actions.nod.headRotationRange>.04,'nod does not move head');
assert.ok(report.actions.shift.rootTravel>.025,'weight shift too small');
assert.ok(report.maxWristAngularStep<.22,'wrist rotation snaps between frames');
assert.ok(report.maxStep<.08,'hand teleports between animation frames');
// Deterministic fixed-step simulation at different display frame rates.
const snapshots=[];for(const fps of [30,60,120]){const a=new BodyActor(asset());a.play('greet');for(let f=0;f<fps*3;f++)a.update(1/fps);snapshots.push(a.joints.wristL.getWorldPosition(new T.Vector3()));}
assert.ok(snapshots[0].distanceTo(snapshots[1])<1e-8&&snapshots[0].distanceTo(snapshots[2])<1e-8);
const transition=new BodyActor(asset());for(let f=0;f<180;f++)transition.update(1/120);let priorHand=null,maxTransitionStep=0;
for(let f=0;f<60*3*ACTIONS.length;f++){if(f%180===0)transition.play(ACTIONS[(f/180)%ACTIONS.length]);transition.update(1/60);const point=transition.joints.wristL.getWorldPosition(new T.Vector3());if(priorHand)maxTransitionStep=Math.max(maxTransitionStep,point.distanceTo(priorHand));priorHand=point;assert.ok(transition.audit.footDrift<.0001);}
assert.ok(maxTransitionStep<.08,'gesture interruption causes a hand jump');report.maxTransitionStep=maxTransitionStep;
// Export clips must contain actual usable tracks with unique joint bindings.
const model=asset(),clips=bakeBodyClips(model);assert.equal(clips.length,ACTIONS.length);for(const clip of clips){assert.ok(clip.validate());for(const track of clip.tracks){const width=track.getValueSize();for(let k=0;k<width;k++)assert.ok(Math.abs(track.values[k]-track.values[track.values.length-width+k])<1e-6,'exported clip has a discontinuous loop seam');}assert.ok(clip.tracks.length>10);assert.ok(new Set(clip.tracks.map(t=>t.name)).size===clip.tracks.length);}
const mixer=new T.AnimationMixer(model);mixer.clipAction(clips.find(c=>c.name==='greet')).play();mixer.setTime(2);model.updateMatrixWorld(true);
const exportedHand=model.getObjectByName('draco_wristL').getWorldPosition(new T.Vector3());assert.ok(exportedHand.y>1.3,'exported clip cannot raise hand');
const idleMixer=new T.AnimationMixer(model);mixer.stopAllAction();idleMixer.clipAction(clips.find(c=>c.name==='idle')).play();idleMixer.setTime(2);model.updateMatrixWorld(true);assert.ok(model.getObjectByName('draco_wristR').getWorldPosition(new T.Vector3()).y<.9,'constant lowered arm pose was lost during export');
report.export={clips:clips.map(c=>({name:c.name,tracks:c.tracks.length})),replayGreetingHandHeight:exportedHand.y};
fs.writeFileSync('web_tool/mao-5070/draco/motion-test-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
