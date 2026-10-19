const active=state=>['loading','playing'].includes(state?.phase);
async function bounded(promise,ms){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Audio timeout')),ms);})]);}finally{clearTimeout(timer);}}
export function songCooldown(state,now=Date.now(),offset=0){
  return state?.phase==='finished'?Math.max(0,Math.ceil(((Number(state.cooldown_ends_at)||0)*1000-now-offset)/1000)):0;
}

// One claimed playback owner per run. Polling/reconnect never restarts a song.
export class SingingPlayer{
  constructor({api,createAudio=url=>new Audio(url),createContext=()=>new AudioContext(),canPlay=()=>true,clientId=crypto.randomUUID()}={}){
    Object.assign(this,{api,createAudio,createContext,canPlay,clientId,state:null,audio:null,context:null,analyser:null,run:'',attempted:'',generation:0,disposed:false});
  }
  async report(event,run=this.run,extra={}){return this.api({event,run_id:run,client_id:this.clientId,...extra});}
  update(state){
    if(this.disposed)return;
    if(this.state?.run_id!==state?.run_id||!active(state)){this.generation++;this.cleanup();}
    this.state=state;
  }
  async tryStart(){
    const state=this.state;
    if(this.disposed||state?.phase!=='loading'||!this.canPlay()||this.attempted===state.run_id)return;
    const run=state.run_id,generation=this.generation;
    this.attempted=run;
    try{
      const claim=await this.report('claim',run);
      if(!claim.accepted||this.disposed||generation!==this.generation)return;
      this.run=run;
      if(!/^[a-z0-9-]{1,64}$/.test(state.song?.id||''))throw Error('Invalid song');
      const audio=this.createAudio(`/api/sing/audio/${encodeURIComponent(state.song.id)}`);this.audio=audio;
      audio.crossOrigin='anonymous';audio.preload='auto';
      audio.addEventListener('ended',()=>this.end('ended',run),{once:true});
      audio.addEventListener('error',()=>this.end('error',run),{once:true});
      // One reusable graph per player, one MediaElementSource per audio file.
      // If analysis is unavailable, native audio still plays; the mouth rests.
      try{
        this.context=this.context||this.createContext();
        await bounded(this.context.resume(),2500);
        this.source=this.context.createMediaElementSource(audio);this.analyser=this.context.createAnalyser();this.analyser.fftSize=256;
        this.samples=new Float32Array(this.analyser.fftSize);this.source.connect(this.analyser);this.analyser.connect(this.context.destination);
      }catch{this.analyser=null;this.source?.disconnect();this.source?.connect(this.context.destination);}
      if(this.disposed||generation!==this.generation){this.cleanup();return;}
      await bounded(audio.play(),15000);
      if(this.disposed||generation!==this.generation){this.cleanup();return;}
      const result=await this.report('playing',run);
      if(!result.accepted&&generation===this.generation)this.cleanup();
    }catch{if(this.run===run)await this.end('error',run);else this.attempted='';}
  }
  async end(event,run=this.run){
    if(run!==this.run)return;
    this.cleanup();
    try{await this.report(event,run);}catch{}
  }
  async heartbeat(){
    const audio=this.audio,run=this.run;if(!audio)return;
    try{const result=await this.report('heartbeat',run,{position:audio.currentTime||0});if(!result.accepted&&this.audio===audio)this.cleanup();}catch{if(this.audio===audio)this.cleanup();}
  }
  get pose(){
    const audio=this.audio,playing=!!audio&&!audio.paused&&!audio.ended;
    let volume=0;
    if(playing&&this.analyser){this.analyser.getFloatTimeDomainData(this.samples);for(const value of this.samples)volume+=value*value;volume=Math.min(1,Math.sqrt(volume/this.samples.length)*3);}
    return {playing,time:playing?audio.currentTime:0,bpm:this.state?.song?.bpm||120,volume};
  }
  cleanup(){
    if(this.audio){const audio=this.audio;this.audio=null;audio.pause();audio.removeAttribute('src');audio.load();}
    this.source?.disconnect();this.analyser?.disconnect();this.source=this.analyser=null;
  }
  dispose(){this.disposed=true;this.generation++;if(this.audio)this.end('closed');this.cleanup();this.context?.close();}
}

const STYLE=`
.mao-song-banner{position:absolute;right:4%;top:13%;z-index:5;width:min(270px,30%);color:#edf2df;padding:16px 20px;border:1px solid #b8d0bc77;border-radius:3px 20px 3px 20px;background:linear-gradient(130deg,#173e34eb,#0a211eeb);box-shadow:0 15px 40px #0004;pointer-events:none;font:12px 'Segoe UI',sans-serif}
.mao-song-banner[hidden]{display:none}.mao-song-banner small{display:block;letter-spacing:.23em;color:#abd3b7;font-size:9px}.mao-song-banner h2{font:26px 'Times New Roman',serif;line-height:1.2;margin:10px 0;overflow-wrap:anywhere}.mao-song-banner p{margin:0;line-height:1.6;color:#c2d8c7;white-space:pre-line}.mao-song-banner progress{display:block;width:100%;height:3px;margin-top:14px;accent-color:#b0d7b6}
body[data-mao-sing="loading"] #mao-window-subtitle,body[data-mao-sing="playing"] #mao-window-subtitle{display:none}
@media(max-width:650px){.mao-song-banner{right:12px;top:42px;padding:10px;width:30%}.mao-song-banner h2{font-size:17px}}
`;
function node(tag,text){const value=document.createElement(tag);if(text)value.textContent=text;return value;}
export function mountSingingPlayer(container,{baseUrl='http://127.0.0.1:12393',fetcher=fetch,canPlay=()=>true,getMode=()=> 'window'}={}){
  let disposed=false,timer,offset=0,notification='',noticeUntil=0;
  const api=async event=>{
    const response=await fetcher(`${baseUrl}/api/sing/playback`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(event),signal:AbortSignal.timeout(3000)});
    if(!response.ok)throw Error('Playback unavailable');return response.json();
  };
  const player=new SingingPlayer({api,canPlay,createAudio:path=>new Audio(`${baseUrl}${path}`)});
  const style=node('style');style.textContent=STYLE;const banner=node('aside');banner.className='mao-song-banner';banner.setAttribute('aria-label','Tiết mục của Mao');banner.setAttribute('aria-live','polite');banner.hidden=true;
  const heading=node('small','MAO • LIVE STAGE'),title=node('h2'),detail=node('p'),progress=node('progress');progress.max=1;banner.append(heading,title,detail,progress);container.append(style,banner);
  function paint(){
    const state=player.state,pose=player.pose,cd=songCooldown(state,Date.now(),offset);
    const show=['waiting','loading','playing'].includes(state?.phase)||Date.now()<noticeUntil;
    banner.hidden=!show||getMode()!=='window';document.body.dataset.maoSing=state?.phase||'idle';
    if(banner.hidden)return;
    title.textContent=state?.song&&['waiting','loading','playing'].includes(state.phase)?state.song.title:'Thực đơn âm nhạc';
    const time=seconds=>`${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;
    detail.textContent=state?.phase==='waiting'?'Chờ Mao nói xong nhé!':state?.phase==='loading'?'Mao đang chuẩn bị lên sân khấu…':state?.phase==='playing'?`Tặng ${state.requester||'cả nhà'}\n${time(pose.playing?pose.time:state.position||0)} / ${time(state.song.duration)}`:notification+(cd?`\nBài tiếp theo sau ${cd}s`:'');
    progress.hidden=state?.phase!=='playing';progress.value=pose.time/(state?.song?.duration||1);
  }
  async function poll(){
    if(disposed)return;
    try{
      const response=await fetcher(`${baseUrl}/api/sing/state`,{cache:'no-store',signal:AbortSignal.timeout(3000)});if(!response.ok)throw Error('offline');
      const state=await response.json();if(disposed)return;offset=state.server_now*1000-Date.now();
      if(state.phase==='finished'&&player.state?.phase!=='finished'){notification=state.reason==='ended'?'Hết bài rồi, cảm ơn cả nhà đã nghe Mao hát!':state.reason==='stopped'?'Mao quay về phòng nhé!':'Chưa phát được bài này, Mao quay về phòng nhé!';noticeUntil=Date.now()+6000;}
      player.update(state);await player.tryStart();
    }catch{if(player.audio){player.cleanup();notification='Kết nối bị gián đoạn, Mao tạm dừng tiết mục.';noticeUntil=Date.now()+6000;}player.update(null);}
    finally{if(!disposed){paint();timer=setTimeout(poll,500);}}
  }
  const notice=event=>{
    const result=event.detail;if(!result)return;
    if(result.state){player.update(result.state);offset=result.state.server_now*1000-Date.now();}
    notification=result.status==='songs'?result.songs?.filter(song=>song.available).map(song=>`!sing ${song.title}`).join('\n')||'Chưa có bài hát sẵn. Thêm file nhạc cho Mao trước nhé!':result.message||'';
    noticeUntil=Date.now()+8000;paint();
  };
  window.addEventListener('mao-sing-command-result',notice);
  const heartbeat=setInterval(()=>player.heartbeat(),3000),ticker=setInterval(paint,250);poll();
  return {get state(){return player.state;},get pose(){return player.pose;},get clockOffset(){return offset;},player,
    dispose(){disposed=true;clearTimeout(timer);clearInterval(heartbeat);clearInterval(ticker);window.removeEventListener('mao-sing-command-result',notice);player.dispose();banner.remove();style.remove();delete document.body.dataset.maoSing;}
  };
}
