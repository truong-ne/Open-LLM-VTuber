// Optional, receive-only observer of the existing local proxy. It never sends
// chat, tool arguments, approvals or playback acknowledgements to the backend.
export class MaoMirror{
  constructor({bridge,createSocket=url=>new WebSocket(url),createAudio=src=>new Audio(src),onCaption=()=>{},onState=()=>{}}){
    Object.assign(this,{bridge,createSocket,createAudio,onCaption,onState});this.socket=null;this.audio=null;this.queue=[];this.generation=0;this.connected=false;
  }
  connect(url='ws://127.0.0.1:12393/proxy-ws'){
    const target=new URL(url);
    if(!['ws:','wss:'].includes(target.protocol)||!['127.0.0.1','localhost','[::1]'].includes(target.hostname)||target.pathname!=='/proxy-ws'||target.username||target.password||target.search||target.hash)throw Error('Mao mirror must use the local proxy.');
    this.stop();const socket=this.createSocket(target.href);this.socket=socket;
    socket.onopen=()=>{if(this.socket===socket){this.connected=true;this.onState('connected');}};
    socket.onmessage=event=>{
      if(this.socket!==socket||typeof event.data!=='string'||event.data.length>8_000_000)return;
      let payload;try{payload=JSON.parse(event.data);}catch{return;}
      if(['user-input-transcription','control'].includes(payload.type))globalThis.window?.dispatchEvent(new CustomEvent('mao-reply-event',{detail:payload}));
      if(payload.type==='audio'&&typeof payload.audio==='string'&&payload.audio.length<7_000_000){
        // Bound a slow observer's queue; never hold up the actual playback owner.
        if(this.queue.length>=8){this.queue.shift();this.onState('catching-up');}
        this.queue.push(payload);this.play();
      }else if(payload.type==='control'&&payload.text==='interrupt-signal')this.clearAudio();
    };
    socket.onclose=()=>{if(this.socket===socket){this.socket=null;this.connected=false;this.clearAudio();this.onState('disconnected');}};
    socket.onerror=()=>{if(this.socket===socket)this.onState('unavailable');};
  }
  play(){
    if(this.audio||!this.queue.length)return;
    const payload=this.queue.shift(),generation=this.generation,audio=this.createAudio('data:audio/wav;base64,'+payload.audio);
    this.audio=audio;audio.muted=true;this.bridge.speechSession=true;
    this.bridge.attachAudio(audio,{displayText:payload.display_text,expressions:payload.actions?.expressions,motions:payload.actions?.motions,pose:payload.actions?.pose,volumes:Array.isArray(payload.volumes)?payload.volumes:[],sliceLength:payload.slice_length||20});
    this.onCaption(typeof payload.display_text?.text==='string'?payload.display_text.text.slice(0,1000):'');
    const done=()=>{if(this.audio!==audio||this.generation!==generation)return;this.audio=null;this.bridge.speechSession=false;this.play();};
    audio.addEventListener('ended',done,{once:true});audio.addEventListener('error',()=>{this.onState('audio-unavailable');done();},{once:true});
    Promise.resolve(audio.play()).catch(()=>{this.onState('audio-unavailable');done();});
  }
  clearAudio(){this.generation++;this.queue=[];this.audio?.pause();this.audio=null;this.bridge.audio=null;this.bridge.payload=null;this.bridge.speechSession=false;this.onCaption('');}
  stop(){const socket=this.socket;this.socket=null;this.connected=false;socket?.close();this.clearAudio();this.onState('disconnected');}
}
