import test from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {drawTvScreen,screenPhase} from '../web_tool/mao-5070/draco/tv-screen.mjs';
import {createDesktopRoom} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {configureAvatarCamera} from '../web_tool/mao-5070/draco/room-view.mjs';
import {sceneForGame} from '../web_tool/mao-5070/draco/game-scene.mjs';
import {TV_SPEC} from '../web_tool/mao-5070/draco/tv-studio.mjs';

const state={phase:'playing',round_id:'tv-test',revision:2,ends_at:1060,server_now:1000,category:'Văn hóa Việt',slots:[2,3],letters:['D','Á','I','À','O'],hint_index:1,hints:['Trang phục quen thuộc.','Nữ sinh hay mặc bộ màu trắng.'],participants:2,leaderboard:[]};
function graphic(){
  const labels=[];const context=new Proxy({font:'',fillText(s){labels.push(String(s));},measureText(s){return {width:String(s).length*22};},createLinearGradient(){return {addColorStop(){}};}},{get(target,key){return key in target?target[key]:()=>{};}});
  return {labels,canvas:{width:1920,height:1080,getContext(){return context;}}};
}
test('TV shows numbered clues and blanks, then results, then standby without a stale answer',()=>{
  const playing=graphic();drawTvScreen(playing.canvas,state,{now:1020000});assert.ok(playing.labels.includes('GỢI Ý 2'));assert.ok(playing.labels.includes('40'));assert.ok(!playing.labels.includes('ÁO DÀI'));assert.equal(playing.labels.filter(s=>s==='_').length,5);
  const finished={...state,phase:'finished',answer:'áo dài',show_until:1075,leaderboard:[{nickname:'<img onerror=bad>',score:100,seconds:4.1}]};
  const result=graphic();drawTvScreen(result.canvas,finished,{now:1060000});assert.ok(result.labels.includes('ÁO DÀI'));assert.ok(result.labels.includes('<img onerror=bad>'));assert.ok(result.labels.includes('100'));
  const expired=graphic();drawTvScreen(expired.canvas,finished,{now:1076000});assert.equal(screenPhase(finished,1076000),'idle');assert.ok(expired.labels.includes('Mao nhé?'));assert.ok(!expired.labels.includes('ÁO DÀI'));
});
test('studio uses one TV texture, updates only on a new graphic, and releases it',()=>{
  const room=createDesktopRoom({theme:'studio'});assert.equal(room.theme,'mao-tv-studio');room.setMode('window');const texture=room.group.getObjectByName('mao-studio-tv').material.map;
  const previous=globalThis.window;globalThis.window={maoWordGame:{canvas:{width:1920,height:1080},textureRevision:1}};
  try{room.update(0);const version=texture.version;room.update(.016);assert.equal(texture.version,version);globalThis.window.maoWordGame.textureRevision++;room.update(.016);assert.equal(texture.version,version+1);room.setMode('pet');const hidden=texture.version;globalThis.window.maoWordGame.textureRevision++;room.update(.016);assert.equal(texture.version,hidden);let disposed=0;texture.addEventListener('dispose',()=>disposed++);room.dispose();assert.equal(disposed,1);}finally{globalThis.window=previous;}
});
test('result and standby show the cooldown without keeping Mao in the game scene',()=>{
  const finished={...state,phase:'finished',answer:'áo dài',show_until:1075,cooldown_ends_at:1090,leaderboard:[]};
  const result=graphic();drawTvScreen(result.canvas,finished,{now:1060000});
  assert.ok(result.labels.some(s=>s.startsWith('Vòng mới sau 30 giây')));
  const standby=graphic();drawTvScreen(standby.canvas,finished,{now:1076000});
  assert.ok(standby.labels.includes('Vòng mới sau 14 giây'));
  assert.equal(sceneForGame(finished,1076000),'lounge');
  const ready=graphic();drawTvScreen(ready.canvas,finished,{now:1090000});
  assert.ok(ready.labels.includes('!vuatiengviet'));
  assert.ok(!ready.labels.some(s=>s.startsWith('Vòng mới sau')));
});
test('broadcast camera fits the TV and presenter at multiple sizes and caches projection',()=>{
  for(const [width,height] of [[876,520],[2120,1122],[460,520],[1280,720]]){
    const camera=new T.PerspectiveCamera(32,1,.02,30),options={mode:'window',view:{zoom:1.15},width,height,roomView:{studio:true}};
    assert.equal(configureAvatarCamera(camera,options),true);
    for(const [x,y,z] of [[TV_SPEC.x-TV_SPEC.width/2,TV_SPEC.y-TV_SPEC.height/2,TV_SPEC.z],[TV_SPEC.x+TV_SPEC.width/2,TV_SPEC.y+TV_SPEC.height/2,TV_SPEC.z],[1.2,0,-2.5],[2.1,1.85,-2.5]]){const p=new T.Vector3(x,y,z).project(camera);assert.ok(Math.abs(p.x)<1&&Math.abs(p.y)<1,JSON.stringify({width,height,p}));}
    assert.equal(configureAvatarCamera(camera,options),false);
    assert.equal(configureAvatarCamera(camera,{...options,roomView:{kind:'follow',focus:{x:2.8,z:-1.4}}}),true);assert.equal(camera.fov,32);
  }
});
test('default disco switches to TV only during a round and returns after results expire',()=>{
  const room=createDesktopRoom();assert.equal(room.theme,'luxury-lounge');room.dispose();
  assert.equal(sceneForGame(null,1000000),'lounge');assert.equal(sceneForGame({phase:'idle'},1000000),'lounge');
  for(const phase of ['waiting','playing'])assert.equal(sceneForGame({...state,phase},1000000),'studio');
  const finished={...state,phase:'finished',show_until:1075};
  assert.equal(sceneForGame(finished,1074000),'studio');assert.equal(sceneForGame(finished,1075000),'lounge');
  assert.equal(sceneForGame(finished,1070000,5000),'lounge');
  assert.ok(TV_SPEC.width<3.5&&TV_SPEC.height<2,'TV overwhelms the 1.8m presenter');
});
