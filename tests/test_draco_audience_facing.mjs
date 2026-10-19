import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {DesktopSpace,FloorFeet,locomotionFrame} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {configureAvatarCamera} from '../web_tool/mao-5070/draco/room-view.mjs';
import {ROOM} from '../web_tool/mao-5070/draco/desktop-room.mjs';

const angle=(a,b)=>Math.atan2(Math.sin(a-b),Math.cos(a-b));
const run=(s,seconds,visit=()=>{})=>{for(let i=0;i<seconds*60;i++){s.update(1/60);visit(s);}};
let maxYawRate=0,maxStanceDrift=0,stanceSamples=0;
for(const target of [-.7,.7,Math.PI-.03,-Math.PI+.03]){
  const s=new DesktopSpace(),feet=new FloorFeet({L:new T.Vector3(.055,.12,0),R:new T.Vector3(-.055,.12,0)});
  s.perform('stop');s.setAudienceYaw(target);const prior={};
  run(s,7,()=>{
    locomotionFrame(s,feet,1/60);maxYawRate=Math.max(maxYawRate,Math.abs(s.pose.yawRate));
    for(const side of ['L','R']){
      const leg=feet.legs[side],stance=!leg.swing&&!leg.landing;
      if(stance&&prior[side]?.stance){maxStanceDrift=Math.max(maxStanceDrift,leg.anchor.distanceTo(prior[side].anchor));stanceSamples++;}
      prior[side]={stance,anchor:leg.anchor.clone()};
    }
  });
  assert.ok(Math.abs(angle(s.yaw,target))<1e-4,'idle actor ignores audience bearing');
  assert.deepEqual([s.x,s.z],[0,0],'looking at audience started wandering');
  assert.equal(s.setAudienceYaw(NaN),false);
}
assert.ok(maxYawRate<=1.1+1e-8,'idle turn snaps to viewer');
assert.ok(stanceSamples>100&&maxStanceDrift<1e-9,'audience turn slides the stance feet');

// A camera crossing the +/-pi seam must cause a short turn, not a full reversal.
const seam=new DesktopSpace();seam.perform('stop');seam.yaw=Math.PI-.03;seam.setAudienceYaw(-Math.PI+.03);
let seamTravel=0;run(seam,4,()=>{seamTravel+=Math.abs(seam.pose.yawRate)/60;});
assert.ok(seamTravel<.07);assert.ok(Math.abs(angle(seam.yaw,seam.audienceYaw))<1e-5);
seam.setAudienceYaw(0);const frozen=seam.yaw;for(let i=0;i<60;i++)seam.update(1/60,{paused:true});assert.equal(seam.yaw,frozen);

// Moving the camera during a route must not hijack the walking heading.
const walk=new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32});walk.moveTo(1.2,-1.4);
let movingFrames=0;
run(walk,13,s=>{
  s.setAudienceYaw(-.55);
  if(s.phase==='walk'&&s.pose.speed>.01){
    const alignment=(Math.sin(s.yaw)*s.pose.vx+Math.cos(s.yaw)*s.pose.vz)/s.pose.speed;
    assert.ok(alignment>.995,'audience tracking steers a walking actor sideways');movingFrames++;
  }
});
assert.ok(movingFrames>100);assert.ok(Math.abs(angle(walk.yaw,-.55))<.002,'arrival faces an outdated camera');
walk.moveTo(-1,-2);run(walk,1);walk.perform('stop');walk.setAudienceYaw(.45);run(walk,6);
assert.ok(Math.abs(angle(walk.yaw,.45))<1e-5,'stop prevented audience tracking');

// Explicit choreography is allowed to complete before attention returns.
const spin=new DesktopSpace();spin.perform('stop');spin.setAudienceYaw(.6);run(spin,5);spin.perform('spin');
let totalSpin=0;
run(spin,8,s=>{if(s.phase==='spin'||s.completedSpins===1&&s.phase==='settle')totalSpin+=s.pose.yawRate/60;});
assert.equal(spin.completedSpins,1);assert.ok(Math.abs(totalSpin-Math.PI*2)<1e-6,'tracking shortened the full spin');
spin.setAudienceYaw(-.4);run(spin,5);assert.ok(Math.abs(angle(spin.yaw,-.4))<1e-5);

// Audience means the physical render camera, not the room origin or orbit yaw.
const camera=new T.PerspectiveCamera(32,1,.02,30);
for(const kind of ['room','follow'])for(const x of [-2.4,2.4])for(const azimuth of [-.7,.7]){
  const s=new DesktopSpace({bounds:ROOM.walk,roam:'room'});s.x=x;s.z=-3;s.perform('stop');
  configureAvatarCamera(camera,{mode:'window',view:{zoom:1.15},width:876,height:520,roomView:{kind,direction:new T.Vector3(Math.sin(azimuth),.5,Math.cos(azimuth)).normalize(),focus:new T.Vector3(s.x,0,s.z)}});
  const target=Math.atan2(camera.position.x-s.x,camera.position.z-s.z);s.setAudienceYaw(target);run(s,6);
  const toViewer=new T.Vector3(camera.position.x-s.x,0,camera.position.z-s.z).normalize();
  assert.ok(new T.Vector3(Math.sin(s.yaw),0,Math.cos(s.yaw)).dot(toViewer)>.9999,`${kind}: off-center actor looks past audience`);
}
console.log(JSON.stringify({audienceFacing:true,walkHeadingPreserved:true,fullSpinPreserved:true,maxYawRate,maxStanceDrift,stanceSamples}));
