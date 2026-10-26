import test from 'node:test';
import assert from 'node:assert/strict';
import {CaptureSession,fitStage,LAYOUT,modeOf,obsLayout} from '../web_tool/mao-5070/playroom-state.mjs';

function stream(surface='browser'){
  const listeners={};
  const track={stopped:false,stop(){this.stopped=true;},getSettings:()=>({displaySurface:surface}),addEventListener:(name,fn)=>{listeners[name]=fn;}};
  return {getTracks:()=>[track],getVideoTracks:()=>[track],track,end:()=>listeners.ended?.()};
}
test('OBS source geometry matches the 16:9 content aperture and never starts a broadcast',()=>{
  const layout=obsLayout('http://127.0.0.1:12395/mao-5070/playroom.html?demo=1#hi','browser');
  assert.equal(LAYOUT.capture.width/LAYOUT.capture.height,16/9);
  assert.equal(layout.sources_bottom_to_top[1].initially_visible,false);
  assert.equal(layout.sources_bottom_to_top[1].window_title_must_match,true);
  assert.equal(layout.starts_streaming,false);
  assert.equal(new URL(layout.sources_bottom_to_top[2].url).searchParams.get('demo'),null);
  assert.equal(modeOf('__proto__'),'game');assert.equal(modeOf('computer'),'computer');
  assert.equal(fitStage(1280,720),2/3);
});
test('choosing a source does not reveal it and rejects sharing the entire monitor',async()=>{
  const whole=stream('monitor');let options;
  const capture=new CaptureSession({mediaDevices:{getDisplayMedia:async opts=>(options=opts,whole)}});
  assert.equal(await capture.choose(),false);assert.equal(whole.track.stopped,true);assert.equal(capture.stream,null);
  assert.equal(options.audio,false);assert.equal(options.monitorTypeSurfaces,'exclude');
  const window=stream('window');capture.mediaDevices.getDisplayMedia=async()=>window;
  assert.equal(await capture.choose(),true);assert.equal(capture.shield,true);
  assert.equal(capture.reveal(),true);capture.hide();assert.equal(capture.shield,true);
  window.end();assert.equal(capture.stream,null);assert.equal(capture.shield,true);
});
test('covering while a source picker is pending discards the late stream',async()=>{
  let resolve;const late=stream();
  const capture=new CaptureSession({mediaDevices:{getDisplayMedia:()=>new Promise(r=>{resolve=r;})}});
  const pending=capture.choose();capture.hide();resolve(late);
  assert.equal(await pending,false);assert.equal(late.track.stopped,true);assert.equal(capture.stream,null);
});
test('closing or replacing the scene stops old tracks, and unknown surfaces fail closed',async()=>{
  const first=stream(),next=stream('window'),unknown=stream(undefined);
  const capture=new CaptureSession({mediaDevices:{getDisplayMedia:async()=>first}});
  await capture.choose();capture.mediaDevices.getDisplayMedia=async()=>next;await capture.choose();assert.equal(first.track.stopped,true);
  capture.dispose();assert.equal(next.track.stopped,true);assert.equal(await capture.choose(),false);
  const invalid=new CaptureSession({mediaDevices:{getDisplayMedia:async()=>unknown}});
  unknown.track.getSettings=()=>({});assert.equal(await invalid.choose(),false);assert.equal(unknown.track.stopped,true);
});
