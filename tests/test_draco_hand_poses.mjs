import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {BodyActor} from '../web_tool/mao-5070/draco/motion.mjs';
import {createDracoRig} from './helpers/draco_fixture.mjs';

function frame(actor,side){
  const p=n=>actor.asset.getObjectByName(n).getWorldPosition(new T.Vector3());
  const wrist=p(`draco_wrist${side}`),along=p(`draco_finger${side}2_0`).sub(wrist).normalize();
  const forearm=wrist.clone().sub(p(`draco_elbow${side}`)).normalize();
  const normal=actor.palms[side].normal.clone().applyQuaternion(actor.joints['wrist'+side].getWorldQuaternion(new T.Quaternion()).multiply(actor.rest.get(actor.joints['wrist'+side]).worldInverse));
  return {bend:T.MathUtils.radToDeg(Math.acos(T.MathUtils.clamp(forearm.dot(along),-1,1))),normal,along,thumb:p(`draco_finger${side}0_0`).sub(wrist),palm:wrist.clone().lerp(p(`draco_finger${side}2_0`),.6),tip:p(`draco_finger${side}2_2`)};
}
const cases={laugh:['L','R'],chuckle:['L'],think:['R'],shy:['L'],reassure:['R'],emphasize:['R']};
const report={poses:{},transitionMaxHandStep:0,transitionMaxAngularStep:0,maxClothPenetration:0};
for(const [action,sides] of Object.entries(cases)){
  const actor=new BodyActor(createDracoRig());for(let f=0;f<180;f++)actor.update(1/120);
  actor.play(action);for(let f=0;f<288;f++){
    actor.update(1/120);if(actor.dynamics.audit.maxPenetration>report.maxClothPenetration){report.maxClothPenetration=actor.dynamics.audit.maxPenetration;report.contact={action,frame:f,...actor.dynamics.audit.blocked};}
  }
  report.poses[action]={};
  for(const side of sides){
    const hand=frame(actor,side);assert.ok(hand.bend<55,`${action}/${side}: wrist bent ${hand.bend} degrees`);
    assert.ok(action==='emphasize'?hand.normal.z>.8:hand.normal.z<-.85,`${action}/${side}: palm faces the wrong side`);
    report.poses[action][side]={bend:hand.bend,palmZ:hand.normal.z,thumbY:hand.thumb.y};
    if(action==='laugh'&&side==='R'){
      assert.ok(hand.thumb.y>.01,'stomach hand has its thumb below the fingers');
      assert.ok(hand.along.x>.75,'stomach fingers point away from the intended side');
    }
    if(side==='L'&&(action==='laugh'||action==='chuckle'))assert.ok(hand.along.x<-.35,'face hand still looks like a vertical greeting');
    if(action==='shy'||action==='reassure'){
      const chest=actor.joints.chest.getWorldPosition(new T.Vector3()),neck=actor.joints.neck.getWorldPosition(new T.Vector3());
      assert.ok(hand.palm.y>chest.y-.025&&hand.palm.y<chest.y+.055,`${action}: palm is above the chest`);
      assert.ok(hand.tip.y<neck.y-.065,`${action}: fingers cover the neck instead of the chest`);
      assert.ok(hand.palm.z>chest.z+.11&&hand.palm.z<chest.z+.17,`${action}: hand is inside or too far in front of the torso`);
      const chestChange=actor.joints.chest.getWorldQuaternion(new T.Quaternion()).multiply(actor.rest.get(actor.joints.chest).worldInverse);
      const localAlong=hand.along.clone().applyQuaternion(chestChange.invert());
      const wrist=actor.joints['wrist'+side].getWorldPosition(new T.Vector3());
      const inward=T.MathUtils.radToDeg(Math.asin(-localAlong.z));
      assert.ok(inward>16&&inward<30,`${action}: fingers must incline toward the chest, got ${inward} degrees`);
      assert.ok(Math.abs(localAlong.x)>.8&&localAlong.y>.08&&localAlong.y<.4,`${action}: hand must lie diagonally across the chest instead of upright`);
      assert.ok(wrist.z-hand.tip.z>.025,`${action}: fingertips still float forward of the chest`);
      report.poses[action][side].inwardAngle=inward;
      report.poses[action][side].fingertipInset=wrist.z-hand.tip.z;
      report.poses[action][side].palmAboveChest=hand.palm.y-chest.y;
      report.poses[action][side].fingersBelowNeck=neck.y-hand.tip.y;
    }
  }
}
const actor=new BodyActor(createDracoRig());for(let f=0;f<180;f++)actor.update(1/120);
const sequence=['laugh','emphasize','reassure','think','chuckle','shy','idle','laugh'],previous=new Map();
for(let f=0;f<sequence.length*150;f++){
  if(f%150===0)actor.play(sequence[f/150]);actor.update(1/60);
  for(const side of ['L','R']){
    const wrist=actor.joints['wrist'+side],point=wrist.getWorldPosition(new T.Vector3());
    const old=previous.get(side);if(old)report.transitionMaxHandStep=Math.max(report.transitionMaxHandStep,point.distanceTo(old));previous.set(side,point);
    for(const bone of [wrist,actor.forearms[side]]){
      const q=bone.getWorldQuaternion(new T.Quaternion()),before=previous.get(bone);
      if(before)report.transitionMaxAngularStep=Math.max(report.transitionMaxAngularStep,q.angleTo(before));previous.set(bone,q);
    }
  }
}
assert.ok(report.transitionMaxHandStep<.08,'hand position jumps during mood changes');
assert.ok(report.transitionMaxAngularStep<.22,`hand/forearm rotation snaps: ${report.transitionMaxAngularStep}`);
assert.ok(report.maxClothPenetration<.003,`sleeve collision: ${JSON.stringify({depth:report.maxClothPenetration,...report.contact})}`);
fs.writeFileSync('web_tool/mao-5070/draco/hand-pose-test-report.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
