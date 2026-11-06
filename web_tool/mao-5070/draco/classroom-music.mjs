// Local background track, played by the same application as Mao's voice.
export function createClassroomMusic({Audio=globalThis.Audio}={}) {
  const audio=new Audio(new URL('./assets/classroom-background.ogg',import.meta.url).href);
  audio.loop=true;audio.preload='auto';
  let disposed=false,pending=false;
  const status={playing:false,error:'',volume:.35};
  audio.addEventListener('playing',()=>{status.playing=true;status.error='';});
  audio.addEventListener('pause',()=>{status.playing=false;});
  audio.addEventListener('error',()=>{status.error=`Không tải được nhạc (${audio.error?.code||0})`;status.playing=false;});
  function update({enabled=false,level=status.volume}={}){
    if(disposed)return;
    status.volume=Math.max(0,Math.min(1,Number(level)||0));audio.volume=status.volume;
    if(!enabled||!audio.volume){audio.pause();status.playing=false;return;}
    if(audio.paused&&!pending){pending=true;audio.play().then(()=>{status.error='';}).catch(error=>{status.error=error.message;status.playing=false;}).finally(()=>{pending=false;});}
    status.playing=!audio.paused&&!audio.ended&&audio.readyState>=2;
  }
  function dispose(){disposed=true;audio.pause();audio.removeAttribute('src');audio.load();status.playing=false;}
  return {status,update,dispose};
}
