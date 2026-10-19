import test from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {SingingPlayer,songCooldown} from '../web_tool/mao-5070/draco/singing-player.mjs';
import {createDesktopRoom} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {configureAvatarCamera} from '../web_tool/mao-5070/draco/room-view.mjs';
import {PerformanceBodyActor} from '../web_tool/mao-5070/draco/performance-motion.mjs';
import {createDracoRig} from './helpers/draco_fixture.mjs';

class AudioFixture extends EventTarget{
  constructor(url){super();this.url=url;this.paused=true;this.ended=false;this.currentTime=0;this.plays=0;}
  async play(){this.paused=false;this.plays++;}
  pause(){this.paused=true;}
  removeAttribute(){}
  load(){}
}
const state={phase:'loading',run_id:'one',song:{id:'demo',title:'Bài thử',duration:200,bpm:120}};
function fixture({claim=true,canPlay=()=>true}={}){
  const calls=[],audios=[];
  const player=new SingingPlayer({api:async event=>{calls.push(event);return {accepted:event.event==='claim'?claim:true};},clientId:'screen',canPlay,createAudio:url=>{const a=new AudioFixture(url);audios.push(a);return a;},createContext:()=>{throw Error('No analysis in fixture');}});
  return {player,calls,audios};
}

test('song waits for curtain reveal, claims one owner and does not replay on polling',async()=>{
  let ready=false;const {player,calls,audios}=fixture({canPlay:()=>ready});player.update(state);
  await player.tryStart();assert.equal(calls.length,0);
  ready=true;await player.tryStart();assert.deepEqual(calls.map(x=>x.event),['claim','playing']);assert.equal(audios[0].plays,1);
  for(let i=0;i<10;i++){player.update(state);await player.tryStart();}
  assert.equal(audios.length,1);audios[0].currentTime=12;assert.equal(player.pose.time,12);assert.equal(player.pose.playing,true);
  await player.heartbeat();assert.equal(calls.at(-1).position,12);
  audios[0].ended=true;audios[0].dispatchEvent(new Event('ended'));await new Promise(resolve=>setImmediate(resolve));
  assert.equal(player.audio,null);assert.equal(calls.at(-1).event,'ended');player.dispose();
});

test('a second desktop, old results, new runs and failed audio cannot double-play',async()=>{
  const other=fixture({claim:false});other.player.update(state);await other.player.tryStart();assert.equal(other.audios.length,0);other.player.dispose();
  const {player,audios,calls}=fixture();player.update(state);await player.tryStart();
  player.update({...state,phase:'finished'});assert.equal(audios[0].paused,true);assert.equal(player.pose.playing,false);
  await player.tryStart();assert.equal(audios.length,1);
  player.update({...state,run_id:'two'});await player.tryStart();assert.equal(audios.length,2);
  audios[1].dispatchEvent(new Event('error'));await new Promise(resolve=>setImmediate(resolve));
  assert.equal(player.audio,null);assert.equal(calls.at(-1).event,'error');player.dispose();
});

test('disposed or superseded requests never start delayed audio',async()=>{
  let resolve;const player=new SingingPlayer({api:()=>new Promise(done=>resolve=done),clientId:'screen',createAudio:()=>{throw Error('must not create stale audio');}});
  player.update(state);const pending=player.tryStart();player.dispose();resolve({accepted:true});await pending;assert.equal(player.audio,null);
});

test('song cooldown uses server time and concert camera keeps both feet and head visible',()=>{
  assert.equal(songCooldown({phase:'finished',cooldown_ends_at:1030},1000000,5000),25);
  assert.equal(songCooldown({phase:'finished',cooldown_ends_at:1030},1030000),0);
  const room=createDesktopRoom({theme:'concert'});room.setMode('window');assert.equal(room.theme,'mao-concert');assert.ok(room.group.getObjectByName('concert-moon'));assert.ok(!room.group.getObjectByName('mao-studio-tv'));
  for(const [width,height] of [[1280,720],[460,520]]){
    const camera=new T.PerspectiveCamera();configureAvatarCamera(camera,{mode:'window',view:{zoom:1.32},width,height,roomView:{lounge:true,kind:'room'}});
    for(const y of [0,1.85]){const p=new T.Vector3(0,y,-1.65).project(camera);assert.ok(Math.abs(p.x)<1&&Math.abs(p.y)<.95);}
  }
  room.dispose();
});

test('continuous song sway follows the playback clock with stable feet and finite joints',()=>{
  const actor=new PerformanceBodyActor(createDracoRig());for(let i=0;i<180;i++)actor.update(1/120);
  let maxDrift=0,min=Infinity,max=-Infinity;
  for(let frame=0;frame<60*10;frame++){
    actor.songPerformance={playing:true,time:frame/60,bpm:120};if(actor.action!=='hipSway')actor.play('hipSway');actor.started=actor.time-2;actor.update(1/60,.05);
    maxDrift=Math.max(maxDrift,actor.audit.footDrift);min=Math.min(min,actor.joints.waist.position.x);max=Math.max(max,actor.joints.waist.position.x);
    for(const bone of actor.bones)assert.ok(bone.quaternion.toArray().every(Number.isFinite));
  }
  assert.ok(max-min>.02,'no visible sway');assert.ok(maxDrift<.001,'concert feet slide');
});
