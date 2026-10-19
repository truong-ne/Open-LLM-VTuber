const URLS={close:new URL('./assets/curtain-close-v2.ogg',import.meta.url).href,open:new URL('./assets/curtain-open-v2.ogg',import.meta.url).href};

export class CurtainSound{
  constructor({fetcher=fetch,createContext=()=>new AudioContext(),now=()=>performance.now(),speechBusy=()=>!!globalThis.window?.maoDraco?.audio&&!window.maoDraco.audio.paused,enabled=true,volume=.32}={}){
    Object.assign(this,{fetcher,createContext,now,speechBusy,enabled,volume,context:null,buffers:{},disposed:false,token:0,played:0});
    this.data={};this.active=null;this.pending=null;
    this.preload=Promise.all(Object.entries(URLS).map(async([key,url])=>{try{const response=await fetcher(url,{signal:AbortSignal.timeout(4000)});if(response.ok)this.data[key]=await response.arrayBuffer();}catch{}}));
  }
  warm(){
    if(this.disposed||!this.enabled)return;
    try{this.context=this.context||this.createContext();this.context.resume().catch(()=>{});}catch{}
  }
  async play(kind,duration){
    const token=++this.token,requested=this.now();this.stop();
    if(this.disposed||!this.enabled||!URLS[kind])return false;
    this.warm();const context=this.context;if(!context)return false;
    await this.preload;
    try{
      if(!this.buffers[kind]&&this.data[kind])this.buffers[kind]=await context.decodeAudioData(this.data[kind].slice(0));
      // Never release an old pull sound late when the user finally unlocks
      // audio or a slow asset finishes downloading. The curtain keeps moving.
      if(this.disposed||token!==this.token||context.state!=='running'||this.now()-requested>180||!this.buffers[kind])return false;
      const source=context.createBufferSource(),gain=context.createGain();source.buffer=this.buffers[kind];
      const seconds=duration/1000,clock=context.currentTime;
      source.playbackRate.value=source.buffer.duration/seconds;
      const level=Math.max(0,Math.min(.5,this.volume))*(this.speechBusy()?.2:1);
      gain.gain.setValueAtTime(0,clock);gain.gain.linearRampToValueAtTime(level,clock+.035);gain.gain.setValueAtTime(level,clock+Math.max(.04,seconds-.07));gain.gain.linearRampToValueAtTime(0,clock+seconds);
      source.connect(gain);gain.connect(context.destination);source.onended=()=>{source.disconnect();gain.disconnect();if(this.active===source)this.active=null;};
      this.active=source;source.start();source.stop(clock+seconds+.015);this.played++;return true;
    }catch{return false;}
  }
  stop(){try{this.active?.stop();}catch{}this.active=null;}
  setEnabled(value){this.enabled=!!value;if(!this.enabled){this.token++;this.stop();}}
  dispose(){this.disposed=true;this.token++;this.stop();this.context?.close().catch(()=>{});}
}
