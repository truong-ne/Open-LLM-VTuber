import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {buildDracoShell} from '../scripts/build_draco_shell.mjs';
import {createNativeBridge} from '../web_tool/mao-5070/draco/native-bridge.mjs';
import {DesktopSpace} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {DeliveryClient} from '../web_tool/mao-5070/delivery.mjs';
const root=path.resolve(import.meta.dirname,'..');
globalThis.window=new EventTarget();
buildDracoShell(root);
const directory=path.join(root,'private/tools/vtuber-desktop-unpacked/out/renderer');
const generated=fs.readFileSync(path.join(directory,'assets/mao-draco-shell.js'),'utf8');
for(const removed of ['function SettingUI(', 'function General(', 'function Footer(', 'const SidebarContent', 'function BgUrlProvider(', 'Live2DCubismCore', 'live2dcubismcore.js'])assert.ok(!generated.includes(removed),removed);
let audioTask;
const taskSource=generated.match(/addAudioTask\(\{[\s\S]*?\n          \}\);/)[0];
const intent={id:'pipeline-test',command:'dj'};
const pose={right:.72,tilt:-4,smile:.4};
vm.runInNewContext(taskSource,{message:{actions:{body:intent,motions:['refuse'],pose}},window:{maoDraco:{renderer:{}}},addAudioTask:value=>{audioTask=value;}});
assert.equal(audioTask.body,intent,'queued audio discarded body intent before playback');
assert.equal(audioTask.motions[0],'refuse','queued audio discarded explicit story gesture');
assert.equal(audioTask.pose,pose,'queued audio discarded composed motor intention');
const bridge=createNativeBridge();
class AudioFixture extends EventTarget {getAttribute(){return 'data:audio/wav;base64,fixture';}}
const audio=new AudioFixture(),payload={displayText:{text:'Chào bạn'},volumes:[.5],sliceLength:20};
bridge.attachAudio(audio,payload);assert.equal(bridge.audio,audio);assert.equal(bridge.payload,payload);
audio.dispatchEvent(new Event('playing'));audio.dispatchEvent(new Event('playing'));assert.equal(bridge.state.audioStarted,1);
audio.dispatchEvent(new Event('ended'));assert.equal(bridge.state.audioEnded,1);assert.equal(bridge.audio,null);assert.equal(bridge.state.audioErrors,0);
let prepared=false;
bridge.renderer={prepareSpeech:async value=>{assert.equal(value,audio);prepared=true;return true;},refresh(){}};
bridge.attachAudio(audio,payload);assert.equal(await bridge.prepareAudio(audio),true);assert.ok(prepared&&bridge.speechSession);
bridge.update({aiState:'thinking-speaking'});assert.equal(bridge.speechSession,true,'gaps between queued sentences released speech focus');
bridge.update({aiState:'idle'});assert.equal(bridge.speechSession,false);
assert.equal(await bridge.prepareAudio(new AudioFixture()),false,'stale audio must not acquire speech focus');
// A normal desktop text input starts its motion locally, even if inference or
// the backend's conversation queue is busy. The original message is unchanged.
const motion=new DesktopSpace(),sent=[];bridge.renderer={perform:value=>motion.perform(value)};
const serviceSource=generated.slice(generated.indexOf('class WebSocketService {'),generated.indexOf('const wsService = WebSocketService.getInstance();'));
vm.runInNewContext(serviceSource+'\nconst service=new WebSocketService();service.ws={readyState:1,send:raw=>sent.push(JSON.parse(raw))};service.sendMessage({type:"text-input",text:"Mao xoay một vòng đi!"});',{
  Subject:class{next(){}},WebSocket:{OPEN:1},window:{maoDraco:bridge},sent,console
});
assert.equal(motion.phase,'step-back');assert.equal(sent[0].text,'Mao xoay một vòng đi!');
console.log('Mao-only desktop: removed UI absent, queued motions and audio bridge passed.');

// Exercise the actual bundled socket handler and queued audio payload. Unit
// tests of DeliveryClient alone cannot detect an injection into React's switch.
const outbound=[],deliveryWindow={maoDraco:bridge};
const client=new DeliveryClient({send:message=>deliveryWindow.maoDeliverySend(message)});
deliveryWindow.maoDelivery=client;
class FakeSocket {
 static OPEN=1;static CONNECTING=0;
 constructor(){this.readyState=1;}
 send(raw){outbound.push(JSON.parse(raw));}
}
class FakeSubject {
 next(message){
  if(message?.type==='audio'){
   assert.ok(client.segments.has(message.segment_id),'socket must register delivery before publishing audio');
   vm.runInNewContext(taskSource,{message,window:deliveryWindow,addAudioTask:value=>{audioTask=value;}});
  }
 }
}
const socketContext={Subject:FakeSubject,WebSocket:FakeSocket,window:deliveryWindow,console};
vm.runInNewContext(serviceSource+'\nglobalThis.service=new WebSocketService();service.connect("ws://mock");service.ws.onopen();',socketContext);
const service=socketContext.service;
const packet={type:'audio',turn_id:process.env.MAO_TEST_TURN||'current-turn',generation_epoch:process.env.MAO_TEST_EPOCH||'current-epoch',segment_id:process.env.MAO_TEST_SEGMENT||'current-segment',audio:'fixture',actions:{}};
service.ws.onmessage({data:JSON.stringify(packet)});
assert.deepEqual({...audioTask.delivery},{turn_id:packet.turn_id,generation_epoch:packet.generation_epoch,segment_id:packet.segment_id});
const fakeAudio=new EventTarget();client.attach(fakeAudio,audioTask);
fakeAudio.dispatchEvent(new Event('playing'));fakeAudio.dispatchEvent(new Event('ended'));
service.ws.onmessage({data:JSON.stringify({...packet,type:'backend-synth-complete'})});
service.sendMessage({type:'frontend-playback-complete'});
const receipts=outbound.filter(message=>message.type==='playback-segment');
assert.deepEqual(receipts.map(message=>message.status),['started','completed']);
assert.ok(receipts.every(message=>message.turn_id===packet.turn_id&&message.generation_epoch===packet.generation_epoch));
assert.equal(outbound.at(-1).turn_id,packet.turn_id);
console.log('Bundled desktop delivery: audio registration, full correlation IDs, real event ACKs and manifest completion passed.');
if(process.argv.includes('--delivery-receipts'))console.log(JSON.stringify(receipts));
