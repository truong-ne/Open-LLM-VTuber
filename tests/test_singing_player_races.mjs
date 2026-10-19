import test from 'node:test';
import assert from 'node:assert/strict';
import {SingingPlayer} from '../web_tool/mao-5070/draco/singing-player.mjs';

test('a late rejected heartbeat cannot stop the next song',async()=>{
  let resolveHeartbeat;
  const player=new SingingPlayer({clientId:'screen',api:async event=>event.event==='heartbeat'?new Promise(resolve=>resolveHeartbeat=resolve):{accepted:true},createContext:()=>{throw Error('analysis disabled');},createAudio:()=>({paused:true,ended:false,currentTime:0,addEventListener(){},async play(){this.paused=false;},pause(){this.paused=true;},load(){},removeAttribute(){}})});
  const state={phase:'loading',run_id:'one',song:{id:'one',bpm:120}};player.update(state);await player.tryStart();
  const first=player.audio,pending=player.heartbeat();
  player.update({...state,run_id:'two',song:{id:'two',bpm:120}});await player.tryStart();
  const second=player.audio;assert.notEqual(first,second);resolveHeartbeat({accepted:false});await pending;
  assert.equal(player.audio,second);assert.equal(second.paused,false);player.dispose();
});
