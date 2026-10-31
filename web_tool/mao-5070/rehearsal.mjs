import {mountNativeAvatar} from './draco/native-avatar.mjs';
import {DeliveryClient} from './delivery.mjs';
const caption=document.getElementById('caption'),status=document.getElementById('state');
const empty=async()=>({ok:true,json:async()=>({phase:'idle',session:'rehearsal',revision:0,comments:[]})});
const bridge={state:{frames:0,socket:'closed'},options:{mode:'window',scale:1,pointerInteractive:false,forceIgnoreMouse:false,scrollToResize:false},singingFetcher:empty,commentFeedFetcher:empty};
window.rehearsal={bridge,errors:[],chunks:0,turns:0,finished:false};
window.maoWordGame={state:{phase:'idle'}};
await mountNativeAvatar(document.getElementById('scene'),bridge);
const protocol=location.protocol==='https:'?'wss:':'ws:';
const socket=new WebSocket(`${protocol}//${location.host}/client-ws`);
const prompts=[
  'Đây là buổi thử trên máy, chưa phát công khai. Mao chào người vận hành trong một câu ngắn nhé.',
  '9+10 đùa đi',
  'nghiêm túc đi',
  'Mao hãy nói một câu ngắn về điều mình muốn học tốt hơn, không khẳng định đã học được khi chưa có bằng chứng.'
];
let index=0,queue=[],playing=false,synthDone=false;
const delivery=new DeliveryClient({storage:localStorage,send:message=>send(message)});
const send=message=>socket.readyState===WebSocket.OPEN&&socket.send(JSON.stringify(delivery.decorate(message)));
function nextTurn(){
  if(index>=prompts.length){window.rehearsal.finished=true;status.textContent='Đã xong bốn lượt thử · chưa phát công khai';return;}
  status.textContent=`Lượt thử ${index+1}/${prompts.length} · Qwen → TTS → RVC → avatar`;
  send({type:'text-input',text:prompts[index++],source:'mao-rehearsal'});
}
async function play(){
  if(playing)return;
  if(!queue.length){if(synthDone){synthDone=false;bridge.speechSession=false;send({type:'frontend-playback-complete'});}return;}
  playing=true;
  const payload=queue.shift();
  try{
    const audio=new Audio(`data:audio/wav;base64,${payload.audio}`);
    delivery.attach(audio,payload);
    bridge.audio=audio;bridge.speechSession=true;
    bridge.payload={displayText:payload.display_text,expressions:payload.actions?.expressions,motions:payload.actions?.motions,pose:payload.actions?.pose,volumes:payload.volumes,sliceLength:payload.slice_length};
    caption.textContent=payload.display_text?.text||'';
    await bridge.renderer.prepareSpeech(audio);
    send({type:'audio-play-start'});
    await audio.play();
    await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=reject;});
    window.rehearsal.chunks++;
  }catch(error){window.rehearsal.errors.push(String(error));status.textContent='Không phát được tiếng thử; kiểm tra trình phát.';}
  finally{playing=false;play();}
}
const wait=Math.max(3000,Math.min(30000,Number(new URLSearchParams(location.search).get('wait'))||3000));
socket.onopen=()=>{bridge.state.socket='open';const resume=delivery.resume();if(resume)send(resume);setTimeout(nextTurn,wait);};
socket.onmessage=event=>{
  const message=JSON.parse(event.data);
  delivery.receive(message);
  if(message.type==='audio'&&message.audio){queue.push(message);play();}
  if(message.type==='backend-synth-complete'){synthDone=true;play();}
  if(message.type==='control'&&message.text==='conversation-chain-end'){window.rehearsal.turns++;setTimeout(nextTurn,2000);}
  if(message.type==='error'){window.rehearsal.errors.push(message.message);status.textContent='Lượt thử gặp lỗi; xem nhật ký.';}
};
socket.onerror=()=>{status.textContent='Chưa kết nối được máy chủ Mao.';};
socket.onclose=()=>{bridge.state.socket='closed';};
window.addEventListener('pagehide',()=>{bridge.audio?.pause();socket.close();});
