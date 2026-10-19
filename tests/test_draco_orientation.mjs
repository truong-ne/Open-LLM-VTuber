import assert from 'node:assert/strict';
import {headingDegrees,cardinal,compassAngles,roomDestination,BODY_COMMANDS} from '../web_tool/mao-5070/draco/room-orientation.mjs';
import {DesktopSpace,desktopCommand} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {ROOM} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {createNativeBridge} from '../web_tool/mao-5070/draco/native-bridge.mjs';

for(const [yaw,degrees,label] of [[0,180,'S'],[Math.PI,0,'N'],[Math.PI/2,90,'E'],[-Math.PI/2,270,'W'],[Math.PI*3,0,'N']]){
  assert.ok(Math.abs(headingDegrees(yaw)-degrees)<1e-8);assert.equal(cardinal(yaw),label);
}
// Compass agrees with actual ground projection for every camera bearing.
for(const camera of [-.7,0,.7])for(const yaw of [-Math.PI,-1,0,1,Math.PI]){
  const a=compassAngles(yaw,camera),angle=a.arrow*Math.PI/180;
  assert.ok(Math.abs(Math.sin(angle)-Math.sin(yaw-camera))<1e-8);
  assert.ok(Math.abs(-Math.cos(angle)-Math.cos(yaw-camera))<1e-8);
}
for(const [text,command] of [['đi về phía bắc','north'],['bước sang hướng nam','south'],['Mao đi về phía đông','east'],['đi hướng tây','west'],['đi tới bàn DJ','dj'],['đi đến giữa phòng','center'],['đi tới ghế bên trái','lounge-west'],['đi tới ghế phía đông','lounge-east']])assert.equal(desktopCommand(text),command);
for(const text of ['đừng đi hướng bắc','không đi tới bàn DJ','Bắc là hướng nào?'])assert.equal(desktopCommand(text),null);
for(const command of BODY_COMMANDS.filter(c=>c!=='spin')){
  const s=new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32});const target=roomDestination(command,s.x,s.z);assert.ok(s.perform(command));
  for(let i=0;i<60*22&&s.segment;i++)s.update(1/60);
  assert.equal(s.segment,null,`${command}: route never finished`);
  const x=Math.max(ROOM.walk.minX,Math.min(ROOM.walk.maxX,target.x)),z=Math.max(ROOM.walk.minZ,Math.min(ROOM.walk.maxZ,target.z));
  assert.ok(Math.hypot(s.x-x,s.z-z)<1e-7,`${command}: wrong world destination`);
}
const pet=new DesktopSpace();assert.equal(pet.perform('dj'),false);

const originalNow=Date.now;let now=100000;Date.now=()=>now;
try{
  const bridge=createNativeBridge(),performed=[];bridge.renderer={performBody:c=>{performed.push(c);return true;},perform:c=>{performed.push(c);return true;}};
  class Audio extends EventTarget{getAttribute(){return 'fixture';}}
  const first=new Audio();bridge.attachAudio(first,{body:{id:'intent-1',command:'dj'}});
  assert.equal(performed.length,0,'movement starts while audio is still queued');first.dispatchEvent(new Event('playing'));assert.deepEqual(performed,['dj']);
  assert.equal(bridge.performBody({id:'intent-1',command:'dj'}),false,'replayed audio repeats movement');
  assert.equal(bridge.performBody({id:'bad',command:'execute'}),false);
  bridge.command('đi về phía bắc');assert.equal(bridge.performBody({id:'intent-2',command:'north'}),false,'reply duplicates manual movement');
  now+=9000;bridge.options.mode='pet';assert.equal(bridge.performBody({id:'intent-3',command:'dj'}),false);
  bridge.options.mode='window';bridge.renderer.performBody=()=>false;assert.equal(bridge.performBody({id:'intent-4',command:'spin'}),false,'busy renderer not respected');
}finally{Date.now=originalNow;}
console.log('Internal heading, cardinal navigation, landmark destinations and once-only audio-synchronized body intents passed.');
