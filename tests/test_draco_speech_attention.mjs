import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {SpeechAttention} from '../web_tool/mao-5070/draco/speech-attention.mjs';
import {DesktopSpace,FloorFeet,locomotionFrame} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {ROOM} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {PerformanceBodyActor} from '../web_tool/mao-5070/draco/performance-motion.mjs';
import {createNativeMeshFixture} from './helpers/draco_mesh_fixture.mjs';
import {skirtCoverageProbe} from './helpers/draco_skirt_coverage.mjs';

const {asset,root}=createNativeMeshFixture(),actor=new PerformanceBodyActor(asset),feet=new FloorFeet(actor.feet);
const space=new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32}),attention=new SpeechAttention();
const probe=skirtCoverageProbe(actor,{scaled:true,levels:[-.2087,-.1887,-.1587,-.1187,-.0787]});
for(let i=0;i<180;i++)actor.update(1/120);
space.moveTo(1.8,-2.8);
let heldPosition,maxOutside=0,maxFootDrift=0,readyAt;
for(let frame=0;frame<60*17;frame++){
  if(frame===240){heldPosition=[space.x,space.z];attention.focus(space);}
  if(frame>=240){attention.update(space,true);space.setAudienceYaw(.55);}
  root.position.set(0,0,0);root.rotation.y=0;root.updateMatrixWorld(true);
  space.update(1/60);actor.setLocomotion(locomotionFrame(space,feet,1/60));actor.update(1/60);
  root.position.set(space.x,0,space.z);root.rotation.y=space.yaw;root.updateMatrixWorld(true);
  maxFootDrift=Math.max(maxFootDrift,actor.audit.footDrift);
  if(frame>=240){
    assert.deepEqual([space.x,space.z],heldPosition,'speech allowed translation/automatic roaming');
    if(readyAt===undefined&&attention.ready(space,feet))readyAt=(frame-240)/60;
    if(frame%24===0)maxOutside=Math.max(maxOutside,probe().maxOutside);
  }
}
assert.ok(readyAt!==undefined&&readyAt<8,`speech preparation did not settle: ${readyAt}`);
assert.ok(maxOutside<.001,`stop/turn exposed a thigh: ${maxOutside}`);
assert.ok(maxFootDrift<.004,`speech orientation lost foot planting: ${maxFootDrift}`);
assert.ok(Math.abs(space.yaw-.55)<.0001);
assert.equal(attention.stopped(space),false,'temporary speech focus became a user stop command');
// Stay focused across a long gap inside one spoken story.
for(let i=0;i<60*10;i++){attention.update(space,true);space.update(1/60);locomotionFrame(space,feet,1/60);}
assert.deepEqual([space.x,space.z],heldPosition);
attention.command(space,'walk');assert.equal(space.segment,null,'manual walk started during speech');
attention.release();assert.ok(space.segment,'deferred user request did not start after speech');
attention.focus(space);attention.command(space,'walk');attention.command(space,'stop');attention.release();
assert.equal(space.segment,null);assert.equal(space.nextRoam,Infinity,'explicit stop was lost at speech end');
attention.focus(space);attention.release();assert.equal(space.nextRoam,Infinity);

const automatic=new DesktopSpace();attention.focus(automatic);attention.release();
assert.equal(automatic.nextRoam,automatic.time+5,'idle roaming failed to resume after speech');
const spinning=new DesktopSpace();spinning.perform('spin');attention.focus(spinning);
assert.equal(spinning.segment,null,'speech continued a spin away from the camera');
assert.equal(spinning.steps.length,0);
assert.equal(attention.moveTo(spinning,NaN,0),false);
// AI movement attached to playing audio must queue through the speech lock,
// rather than being rejected merely because speechSession is true.
const aiSpace=new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32});
const aiAttention=new SpeechAttention();aiAttention.focus(aiSpace);
assert.equal(aiAttention.bodyCommand(aiSpace,'dj'),true);
assert.equal(aiSpace.segment,null,'AI destination started while talking');
for(let i=0;i<600;i++){aiAttention.update(aiSpace,true);aiSpace.update(1/60);}
assert.deepEqual([aiSpace.x,aiSpace.z],[0,0],'queued AI intent broke the speech lock');
assert.equal(aiAttention.bodyCommand(aiSpace,'lounge-east'),false,'later AI suggestion replaced pending intent');
aiAttention.update(aiSpace,false);assert.ok(aiSpace.segment,'AI destination never started after speech');
for(let i=0;i<60*30;i++){aiSpace.update(1/60,{paused:false,enabled:true});if(aiSpace.phase==='idle')break;}
assert.ok(aiSpace.z< -2,'AI destination failed to move into the actual room');
const stoppedAI=new DesktopSpace();stoppedAI.perform('stop');const stoppedAttention=new SpeechAttention();stoppedAttention.focus(stoppedAI);
assert.equal(stoppedAttention.bodyCommand(stoppedAI,'dj'),false,'AI overrode explicit user stop');
stoppedAttention.release();assert.equal(stoppedAI.nextRoam,Infinity);
const manualAI=new DesktopSpace({bounds:ROOM.walk,roam:'room'});const manualAttention=new SpeechAttention();manualAttention.focus(manualAI);manualAttention.command(manualAI,'lounge-west');
assert.equal(manualAttention.bodyCommand(manualAI,'dj'),false,'AI replaced a manual destination');
manualAttention.release();assert.ok(manualAI.segment);
console.log(JSON.stringify({speechFacesCamera:true,holdsAcrossAudioGaps:true,manualStopPreserved:true,manualWalkDeferred:true,readyAt,maxFootDrift,maxOutside}));
