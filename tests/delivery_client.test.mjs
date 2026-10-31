import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DeliveryClient} from '../web_tool/mao-5070/delivery.mjs';
import {installDeliveryBridge} from '../web_tool/mao-5070/delivery-bridge.mjs';

test('audio events carry the exact turn, epoch and segment and are terminal',()=>{
 const sent=[],client=new DeliveryClient({send:message=>sent.push(message)}),audio=new EventTarget();
 const packet={type:'audio',turn_id:'turn',generation_epoch:'epoch',segment_id:'segment'};
 client.receive(packet);client.attach(audio,{delivery:packet});
 audio.dispatchEvent(new Event('playing'));audio.dispatchEvent(new Event('ended'));audio.dispatchEvent(new Event('error'));
 assert.deepEqual(sent.map(item=>item.status),['started','completed']);assert.equal(sent[1].generation_epoch,'epoch');
 client.receive({type:'control',text:'conversation-chain-end'});assert.equal(client.segments.size,0);
});
test('an old audio callback cannot acknowledge a replacement turn',()=>{
 const sent=[],client=new DeliveryClient({send:message=>sent.push(message)});
 client.receive({type:'audio',turn_id:'new',generation_epoch:'new',segment_id:'id'});
 client.mark({turn_id:'old',generation_epoch:'old',segment_id:'id'},'completed');assert.equal(sent.length,0);
});
test('resume proof survives a new socket and aggregate ACK uses the current manifest',()=>{
 const map=new Map(),storage={getItem:key=>map.get(key),setItem:(key,value)=>map.set(key,value)};
 const client=new DeliveryClient({storage,uuid:()=> 'source'});
 client.receive({type:'actor-session',token:'stable'});client.receive({type:'actor-session',token:'new-transport'});
 assert.equal(client.resume().token,'stable');client.receive({type:'actor-session',token:'verified',force:true});assert.equal(client.resume().token,'verified');
 client.receive({type:'backend-synth-complete',turn_id:'turn',generation_epoch:'epoch'});
 assert.equal(client.decorate({type:'frontend-playback-complete'}).turn_id,'turn');assert.equal(client.decorate({type:'text-input'}).event_id,'source');
});

test('the upstream UI bridge observes real audio events and keeps test sockets isolated',()=>{
 class Socket extends EventTarget{constructor(url){super();this.url=url;this.sent=[];}send(data){this.sent.push(JSON.parse(data));}}
 class Audio extends EventTarget{constructor(source){super();this.src=source;}}
 const env={WebSocket:Socket,Audio,location:{href:'http://127.0.0.1:12394/',port:'12394'},localStorage:{getItem:()=>null,setItem:()=>{}}};
 installDeliveryBridge(env);const socket=new env.WebSocket('ws://localhost:12393/client-ws');
 assert.equal(new URL(socket.url).port,'12394');
 const unavailable={_model:null,startRandomMotion:()=>{throw Error('not ready');}};
 env.getLive2DManager=()=>({getModel:()=>unavailable});env.getLive2DManager().getModel(0).startRandomMotion();
 const packet={type:'audio',audio:'fixture',turn_id:'turn',generation_epoch:'epoch',segment_id:'segment'};
 socket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify(packet)}));
 const audio=new env.Audio('data:audio/wav;base64,fixture');audio.dispatchEvent(new Event('playing'));audio.dispatchEvent(new Event('ended'));
 assert.deepEqual(socket.sent.map(message=>message.status),['started','completed']);
 socket.send(JSON.stringify({type:'text-input',text:'fixture'}));assert.ok(socket.sent.at(-1).event_id);
 const before=env.WebSocket;installDeliveryBridge(env);assert.equal(env.WebSocket,before);
});

test('a rejected play promise is a failed delivery rather than completed speech',async()=>{
 const sent=[],client=new DeliveryClient({send:message=>sent.push(message)}),audio=new EventTarget();
 audio.play=()=>Promise.reject(Error('play denied'));
 const packet={type:'audio',turn_id:'turn',generation_epoch:'epoch',segment_id:'segment'};
 client.receive(packet);client.attach(audio,packet);await assert.rejects(audio.play());assert.equal(sent[0].status,'failed');
});

test('a duplicate packet cannot reset a segment already acknowledged by the player',()=>{
 const sent=[],client=new DeliveryClient({send:message=>sent.push(message)});
 const packet={type:'audio',turn_id:'turn',generation_epoch:'epoch',segment_id:'segment'};
 client.receive(packet);client.mark(packet,'completed');client.receive(packet);client.mark(packet,'started');
 assert.deepEqual(sent.map(message=>message.status),['completed']);
});
