import {DeliveryClient} from './delivery.mjs';

// Adapt the packaged upstream UI without editing its generated JavaScript bundle.
export function installDeliveryBridge(env){
 if(env.maoDeliveryBridge)return;
 env.maoDeliveryBridge=true;
 // Audio continues while the upstream avatar is absent or still loading.
 const audioOnly={_wavFileHandler:null,startRandomMotion:()=>{}};
 let managerGetter=env.getLive2DManager,adapterGetter=env.getLAppAdapter;
 const modelReady=()=>{try{const model=managerGetter?.call(env)?.getModel(0);return model&&(!('_model' in model)||model._model!=null);}catch{return false;}};
 Object.defineProperty(env,'getLive2DManager',{configurable:true,get:()=>function(...args){
  const manager=managerGetter?.apply(env,args);
  if(!manager)return {getModel:()=>audioOnly};
  return new Proxy(manager,{get(target,key){if(key==='getModel')return (...params)=>{const model=target.getModel(...params);return !model||('_model' in model&&model._model==null)?audioOnly:model;};const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;}});
 },set:value=>{managerGetter=value;}});
 Object.defineProperty(env,'getLAppAdapter',{configurable:true,get:()=>function(...args){return modelReady()?adapterGetter?.apply(env,args):null;},set:value=>{adapterGetter=value;}});
 const NativeSocket=env.WebSocket,NativeAudio=env.Audio,pending=[];
 const clear=client=>{for(let index=pending.length-1;index>=0;index--)if(pending[index].client===client)pending.splice(index,1);};
 env.WebSocket=new Proxy(NativeSocket,{construct(target,args){
  const url=new URL(String(args[0]),env.location.href),local=['localhost','127.0.0.1','[::1]'].includes(url.hostname);
  const relevant=['/client-ws','/proxy-ws'].includes(url.pathname)&&local;
  // A synthetic test UI must never follow the upstream default to production.
  if(relevant&&env.location.port==='12394'){
   url.hostname='127.0.0.1';url.port='12394';args=[url.toString(),...args.slice(1)];
  }
  const socket=Reflect.construct(target,args,target);
  if(!relevant)return socket;
  const send=socket.send.bind(socket),client=new DeliveryClient({send:packet=>send(JSON.stringify(packet)),storage:env.localStorage});
  socket.send=function(data){
   if(typeof data==='string'){try{const message=JSON.parse(data);
    if(message.type==='frontend-playback-complete'){
     for(const entry of pending)if(entry.client===client)client.mark(entry.packet,'failed');
     clear(client);
    }
    data=JSON.stringify(client.decorate(message));}catch{}}
   return send(data);
  };
  socket.addEventListener('open',()=>{const proof=client.resume();if(proof)send(JSON.stringify(proof));});
  socket.addEventListener('message',event=>{
   let packet;try{packet=JSON.parse(event.data);}catch{return;}
   client.receive(packet);
   if(packet.runtime_profile&&env.document)env.document.documentElement.dataset.maoRuntimeProfile=packet.runtime_profile;
   if(packet.type==='audio'&&packet.audio&&packet.segment_id){
    pending.push({audio:packet.audio,packet,client});if(pending.length>40)pending.shift();
   }
   if(packet.type==='control'&&packet.text==='conversation-chain-end')clear(client);
  });
  socket.addEventListener('close',()=>clear(client));
  return socket;
 }});
 env.Audio=new Proxy(NativeAudio,{construct(target,args){
  const audio=Reflect.construct(target,args,target),source=String(args[0]??'');
  const index=pending.findIndex(item=>source.endsWith(','+item.audio));
  if(index>=0){const entry=pending.splice(index,1)[0];entry.client.attach(audio,entry.packet);}
  return audio;
 }});
}

if(typeof window!=='undefined')installDeliveryBridge(window);
