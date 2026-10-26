import test from 'node:test';
import assert from 'node:assert/strict';
import {MaoMirror} from '../web_tool/mao-5070/playroom-mirror.mjs';

function fixture(){
  const audios=[],captions=[],states=[];
  const socket={close(){this.closed=true;},send(){throw Error('Observer must never send');}};
  const bridge={attachAudio(audio,payload){this.audio=audio;this.payload=payload;}};
  const mirror=new MaoMirror({bridge,createSocket:()=>socket,createAudio:src=>{
    const listeners={},audio={src,play:()=>Promise.resolve(),pause(){this.paused=true;},addEventListener(name,fn){(listeners[name]??=[]).push(fn);},end(){for(const fn of listeners.ended||[])fn();}};audios.push(audio);return audio;
  },onCaption:text=>captions.push(text),onState:state=>states.push(state)});
  mirror.connect();socket.onopen();
  const packet=text=>({data:JSON.stringify({type:'audio',audio:'UklGRg==',display_text:{text},volumes:[.5],slice_length:20})});
  return {mirror,socket,bridge,audios,captions,states,packet};
}
test('observer mirrors actual captions and mouth audio silently, without backend sends',()=>{
  const {mirror,socket,bridge,audios,captions,packet}=fixture();
  socket.onmessage(packet('<img onerror=bad>'));socket.onmessage(packet('second'));
  assert.equal(audios.length,1);assert.equal(audios[0].muted,true);
  assert.equal(captions.at(-1),'<img onerror=bad>');assert.equal(bridge.payload.volumes[0],.5);
  audios[0].end();assert.equal(audios.length,2);assert.equal(captions.at(-1),'second');
  mirror.stop();assert.equal(audios[1].paused,true);assert.equal(bridge.audio,null);assert.equal(captions.at(-1),'');
});
test('a slow observer has a bounded queue, and a disconnected socket cannot resume it',()=>{
  const {mirror,socket,audios,packet}=fixture();
  for(let i=0;i<20;i++)socket.onmessage(packet(String(i)));
  assert.equal(mirror.queue.length,8);
  mirror.stop();socket.onmessage(packet('late'));audios[0].end();
  assert.equal(audios.length,1);assert.equal(mirror.queue.length,0);assert.equal(socket.closed,true);
});
test('remote proxy endpoints are refused and invalid packets are ignored',()=>{
  const {mirror,socket,packet,audios}=fixture();
  assert.throws(()=>mirror.connect('ws://example.com/proxy-ws'),/local proxy/);
  assert.throws(()=>mirror.connect('ws://localhost:12393/proxy-ws?key=secret'),/local proxy/);
  socket.onmessage({data:'invalid json'});socket.onmessage({data:JSON.stringify({type:'tool_call',operation:'computer'})});
  assert.equal(audios.length,0);socket.onmessage(packet('real'));assert.equal(audios.length,1);
  socket.onmessage({data:JSON.stringify({type:'control',text:'interrupt-signal'})});assert.equal(audios[0].paused,true);
});
