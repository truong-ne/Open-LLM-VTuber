import test from 'node:test';
import assert from 'node:assert/strict';
import {CurtainSound} from '../web_tool/mao-5070/draco/curtain-sound.mjs';

function fixture(){
  const sources=[],gains=[];
  const context={state:'running',currentTime:10,destination:{},async resume(){},async close(){this.closed=true;},async decodeAudioData(){return {duration:1.2};},
    createBufferSource(){const source={playbackRate:{value:1},started:false,stops:[],connect(){},disconnect(){},start(){this.started=true;},stop(time){this.stops.push(time);}};sources.push(source);return source;},
    createGain(){const values=[],gain={values,gain:{setValueAtTime(value,time){values.push({value,time});},linearRampToValueAtTime(value,time){values.push({value,time});}},connect(){},disconnect(){}};gains.push(gain);return gain;}};
  const now={value:0},busy={value:false};
  const sound=new CurtainSound({fetcher:async()=>({ok:true,arrayBuffer:async()=>new ArrayBuffer(8)}),createContext:()=>context,now:()=>now.value,speechBusy:()=>busy.value});
  return {sound,context,sources,gains,now,busy};
}

test('each pull is fitted to its visual movement and fades without interrupting speech',async()=>{
  const {sound,sources,gains,busy}=fixture();
  assert.equal(await sound.play('close',900),true);assert.equal(sources[0].started,true);assert.equal(sources[0].playbackRate.value,1.2/.9);
  const normal=Math.max(...gains[0].values.map(x=>x.value));assert.ok(normal>0&&normal<=.5);
  busy.value=true;assert.equal(await sound.play('open',1200),true);
  assert.equal(sources.length,2);assert.ok(sources[0].stops.includes(undefined),'old pull was not stopped');
  assert.equal(Math.max(...gains[1].values.map(x=>x.value)),normal*.2);
  assert.equal(sound.played,2);sound.dispose();
});

test('muted, blocked and late sounds are skipped instead of bursting after unlock',async()=>{
  const f=fixture();f.sound.setEnabled(false);assert.equal(await f.sound.play('close',900),false);assert.equal(f.sources.length,0);
  f.sound.setEnabled(true);f.context.state='suspended';assert.equal(await f.sound.play('close',900),false);assert.equal(f.sources.length,0);
  f.context.state='running';f.sound.buffers={};f.context.decodeAudioData=async()=>{f.now.value=1000;return {duration:1};};
  assert.equal(await f.sound.play('open',1200),false);assert.equal(f.sources.length,0);f.sound.dispose();
});

test('disposing during a decode cannot start an abandoned pull',async()=>{
  const f=fixture();let resolve;
  f.context.decodeAudioData=()=>new Promise(done=>resolve=done);
  const pending=f.sound.play('close',900);await f.sound.preload;await Promise.resolve();
  f.sound.dispose();resolve({duration:1});assert.equal(await pending,false);assert.equal(f.sources.length,0);
});
