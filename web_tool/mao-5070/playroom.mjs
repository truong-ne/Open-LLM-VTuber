import {CaptureSession,MODES,fitStage,modeOf,obsLayout} from './playroom-state.mjs';
import {createNativeBridge} from './draco/native-bridge.mjs';
import {MaoMirror} from './playroom-mirror.mjs';
import {mergeCommentFeed} from './draco/comment-panel.mjs';

const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);
const layer=['background','overlay'].includes(params.get('layer'))?params.get('layer'):'';
const clean=params.get('clean')==='1'||!!layer;
if(layer)document.body.dataset.layer=layer;
document.body.dataset.clean=String(clean);
document.body.dataset.shield=String(params.get('shield')==='1');
let mode=modeOf(params.get('mode')),mirror=null,chatTimer=null,chatController=null,chatState={session:'',revision:0,comments:[]};
const obsMode=params.get('obs')==='1';let obsToken='',obsCovered=true,hiddenByOperator=false,frameTimer,frameObjectURL,gameTimer;
let autonomyTimer,autonomyToken='',autonomyPaused=false;
function resize(){document.documentElement.style.setProperty('--scale',String(fitStage(innerWidth,innerHeight)));}
resize();window.addEventListener('resize',resize);

function setMode(value){
  mode=modeOf(value);const next=MODES[mode];document.body.dataset.activity=mode;
  $('chapter').textContent=next.label.toLocaleUpperCase('vi');$('screen-title').textContent=next.title.toLocaleUpperCase('vi');$('eyebrow').textContent=next.eyebrow;
  $('subtitle').textContent='Chưa có hoạt động.';
  for(const button of document.querySelectorAll('[data-mode]'))button.setAttribute('aria-pressed',String(button.dataset.mode===mode));
}
const session=new CaptureSession({mediaDevices:navigator.mediaDevices,onChange:state=>{
  const video=$('capture');if(video.srcObject!==state.stream){video.srcObject=state.stream;if(state.stream)video.play().catch(()=>{});}
  $('privacy-shield').hidden=!!state.stream&&!state.shield;
  $('reveal').disabled=!state.stream||!state.shield;$('disconnect').disabled=!state.stream;$('choose').disabled=obsMode||state.pending;
  $('source-status').textContent=layer==='overlay'?'CỬA SỔ OBS':state.pending?'ĐANG CHỌN CỬA SỔ':state.stream?(state.shield?'ĐANG CHE NỘI DUNG':'CỬA SỔ ĐÃ CHỌN'):'CHƯA CHỌN NGUỒN';
  $('shield-title').textContent=state.stream?'Nguồn đang được che.':'Đang chuẩn bị nguồn.';
  $('shield-note').textContent=state.stream?'Nội dung đang được che. Bấm “Hiện nội dung” khi sẵn sàng.':'Cửa sổ bạn chọn sẽ xuất hiện ở đây.';
  $('operator-note').textContent=state.error||(state.pending?'Chọn đúng một tab hoặc cửa sổ trong hộp thoại của trình duyệt.':state.stream?'Chỉ hiển thị cửa sổ đã chọn. Không thu mic hoặc âm thanh toàn máy.':'Chỉ xem trước trên máy. Chưa thu cửa sổ, chưa phát công khai.');
}});
for(const button of document.querySelectorAll('[data-mode]'))button.onclick=()=>setMode(button.dataset.mode);
$('choose').onclick=()=>session.choose();
$('reveal').onclick=()=>obsMode?showObs():session.reveal();
function cover(){
  session.hide();mirror?.stop();chatController?.abort();
  if(obsMode){hiddenByOperator=true;obsCovered=true;$('reveal').disabled=true;clearTimeout(frameTimer);if(frameObjectURL)URL.revokeObjectURL(frameObjectURL);document.getElementById('obs-frame')?.removeAttribute('src');obsAction('hide').then(()=>{$('reveal').disabled=false;}).catch(()=>{$('operator-note').textContent='Chưa xác nhận được OBS đã che nguồn. Hãy ẩn nguồn Mao Game Window trong OBS.';});}
  document.querySelector('.chat-empty').textContent='Đang tạm che nội dung.';
  $('subtitle').textContent='Đang tạm dừng hiển thị.';
  $('operator-note').textContent='Đã che nội dung và ngắt đồng bộ Mao. Ctrl + Shift + H cũng thực hiện thao tác này.';
}
$('hide').onclick=cover;
$('disconnect').onclick=()=>obsMode?cover():session.stop();
$('export').onclick=()=>{
  const blob=new Blob([JSON.stringify(obsLayout(location.href,mode,{syncMao:mirror?.connected===true}),null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download='mao-playroom-obs-layout.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
window.addEventListener('keydown',event=>{if(event.ctrlKey&&event.shiftKey&&event.code==='KeyH'){event.preventDefault();cover();}});
setMode(mode);session.emit();

let avatar;
async function obsAction(action){
  if(!obsToken)throw Error('Chưa có phiên điều khiển OBS');
  const response=await fetch('/api/playroom/'+action,{method:'POST',headers:{'X-Mao-Token':obsToken}});
  if(!response.ok)throw Error('OBS chưa sẵn sàng');return response.json();
}
async function showObs(){
  try{await obsAction('show');hiddenByOperator=false;obsCovered=false;$('privacy-shield').hidden=true;$('source-status').textContent='CỬA SỔ CHROME THẬT';$('reveal').disabled=true;$('disconnect').disabled=false;clearTimeout(frameTimer);pollObsFrame();}
  catch{$('operator-note').textContent='Chưa hiện được nguồn OBS. Hãy kiểm tra cửa sổ game và OBS.';}
}
async function pollObsFrame(){
  if(obsCovered)return;
  try{
    const response=await fetch('/api/playroom/frame',{headers:{'X-Mao-Token':obsToken},cache:'no-store'});
    if(!response.ok)throw Error('No game frame');const blob=await response.blob();if(obsCovered)return;
    const old=frameObjectURL;frameObjectURL=URL.createObjectURL(blob);$('obs-frame').src=frameObjectURL;$('privacy-shield').hidden=true;if(old)URL.revokeObjectURL(old);
  }catch{obsCovered=true;$('reveal').disabled=false;$('privacy-shield').hidden=false;$('shield-title').textContent='Nguồn game đã tạm dừng.';$('shield-note').textContent='Mở lại đúng cửa sổ game và bấm “Hiện nội dung”.';}
  finally{if(!obsCovered)frameTimer=setTimeout(pollObsFrame,500);}
}
if(obsMode&&!layer){
  $('choose').disabled=true;$('choose').textContent='Nguồn: Chrome · 2048';$('capture').hidden=true;
  const image=document.createElement('img');image.id='obs-frame';image.alt='Ảnh cập nhật từ cửa sổ game Chrome thật';Object.assign(image.style,{position:'absolute',inset:'0',width:'100%',height:'100%',objectFit:'contain',background:'#050b08'});$('content-aperture').prepend(image);
  try{
    const response=await fetch('/api/playroom/session',{cache:'no-store'});const info=await response.json();obsToken=info.token;
    if(info.configured){obsCovered=!info.visible||hiddenByOperator;$('reveal').disabled=!obsCovered;$('disconnect').disabled=false;if(!obsCovered){$('privacy-shield').hidden=true;$('source-status').textContent='CỬA SỔ CHROME THẬT';pollObsFrame();}else if(hiddenByOperator)await obsAction('hide');}
    $('preview-badge').textContent='XEM TRƯỚC · ẢNH CẬP NHẬT';$('operator-note').textContent='Ảnh từ cửa sổ game thật được cập nhật định kỳ. Cảnh OBS lấy video cửa sổ trực tiếp.';
  }catch{$('operator-note').textContent='Chưa cấu hình nguồn game OBS. Hãy chạy hướng dẫn Playroom.';}
}
async function pollGame(){
  try{
    const response=await fetch('./state/game2048.json',{cache:'no-store'});if(!response.ok)return;
    const state=await response.json();
    if(state.game==='2048'&&Number.isFinite(state.updated_at)&&Date.now()/1000-state.updated_at<15&&typeof state.caption==='string'&&!hiddenByOperator){
      $('subtitle').textContent=state.caption.slice(0,500);$('eyebrow').textContent=state.phase==='playing'?'MAO ĐANG CHƠI · 2048':'NHẬT KÝ CHƠI GAME';
    }
  }catch{}finally{gameTimer=setTimeout(pollGame,700);}
}
if(params.get('game')==='2048'&&layer!=='background')pollGame();
async function pollAutonomy(){
  const labels={searching_for_new_sources:'Đang tìm nguồn chưa đọc',waiting_for_zero_viewers:'Chờ khi không có người xem',planning:'Đang chọn chủ đề',reading:'Đang đọc nguồn',reflecting:'Đang xử lý dữ liệu',saving:'Đang lưu kết quả',resting:'Đã hoàn thành',paused:'Đã tạm dừng',yielded:'Nhường lượt cho hội thoại',waiting_for_conversation:'Đang có hội thoại',waiting_for_idle:'Chờ lúc rảnh',budget_or_cooldown:'Đang nghỉ theo hạn mức',storage_or_service_unavailable:'Dịch vụ chưa kết nối',backoff:'Lượt trước chưa thành công',offline:'Dịch vụ chưa chạy',stopped:'Đã dừng',time_budget:'Hết thời gian lượt',waiting_for_persona:'Chờ persona mới'};
  try{
    if(!autonomyToken){const response=await fetch('/api/playroom/session',{cache:'no-store'});if(!response.ok)throw Error();autonomyToken=(await response.json()).token;}
    const response=await fetch('/api/autonomy/status',{cache:'no-store'});if(!response.ok)throw Error();const state=await response.json();autonomyPaused=state.paused===true;
    $('autonomy-status').textContent=(autonomyPaused?labels.paused:labels[state.phase]||'Mao đang chuẩn bị')+(state.title?' · '+String(state.title).slice(0,100):'');
    $('autonomy-pause').disabled=false;$('autonomy-pause').textContent=autonomyPaused?'Tiếp tục tự tìm hiểu':'Tạm dừng tự tìm hiểu';
    const source=state.last_result?.source;let allowed=false;try{const url=new URL(source);allowed=(url.origin==='https://en.wikipedia.org'&&url.pathname.startsWith('/wiki/')||url.origin==='https://arxiv.org'&&url.pathname.startsWith('/abs/')||url.origin==='https://support.google.com'&&url.pathname.startsWith('/youtube/answer/')||url.origin==='https://streamlabs.com'&&url.pathname.startsWith('/content-hub/post/')||url.origin==='https://restream.io'&&url.pathname.startsWith('/blog/')||url.origin==='https://hololive.hololivepro.com'&&url.pathname.startsWith('/en/talents')||url.origin==='https://blog.twitch.tv'&&url.pathname.startsWith('/en/')||url.origin==='https://greatergood.berkeley.edu'&&(url.pathname.startsWith('/topic/')||url.pathname.startsWith('/article/item/')))&&!url.username&&!url.password;}catch{}
    $('autonomy-source').hidden=!allowed;$('autonomy-log').hidden=!allowed;
    if(allowed){$('autonomy-source').href=source;$('autonomy-summary').textContent=String(state.last_result.quote||'').slice(0,250);$('autonomy-thought').textContent=state.last_result.reflection?String(state.last_result.reflection).slice(0,350):'Chỉ lưu trích đoạn, chưa có diễn giải.';$('autonomy-thought').title='Ý nghĩ riêng của Mao, chưa phải thông tin đã kiểm chứng. Nguồn đọc được giữ bên dưới.';}
  }catch{$('autonomy-status').textContent='Chưa kết nối được bộ tự tìm hiểu';$('autonomy-pause').disabled=true;}
  finally{autonomyTimer=setTimeout(pollAutonomy,2000);}
}
if(!layer&&!clean){
  $('autonomy-pause').onclick=async()=>{try{$('autonomy-pause').disabled=true;const response=await fetch('/api/autonomy/'+(autonomyPaused?'resume':'pause'),{method:'POST',headers:{'X-Mao-Token':autonomyToken}});if(!response.ok)throw Error();clearTimeout(autonomyTimer);pollAutonomy();}catch{$('autonomy-status').textContent='Chưa xác nhận được thay đổi. Hãy thử lại.';$('autonomy-pause').disabled=false;}};
  pollAutonomy();
}
async function pollChat(){
  if(!mirror?.connected)return;
  try{
    chatController=new AbortController();
    const timer=setTimeout(()=>chatController.abort(),2500);
    let response;try{response=await fetch('http://127.0.0.1:12393/api/comments?after='+chatState.revision+'&session='+encodeURIComponent(chatState.session),{signal:chatController.signal,cache:'no-store'});}finally{clearTimeout(timer);}
    if(!response.ok)throw Error('offline');
    const payload=await response.json();if(!mirror.connected)return;
    chatState=mergeCommentFeed(chatState,payload);
    const area=document.querySelector('.chat-empty');area.replaceChildren();
    for(const item of chatState.comments.slice(0,2)){
      const row=document.createElement('div'),name=document.createElement('strong'),text=document.createElement('span');row.className='public-comment';name.textContent=item.nickname;text.textContent=item.text.slice(0,150);row.append(name,text);area.append(row);
    }
    if(!chatState.comments.length)area.textContent='Chưa có bình luận mới.';
  }catch{}finally{if(mirror?.connected)chatTimer=setTimeout(pollChat,2000);}
}
function mirrorState(state){
  const connected=mirror?.connected===true;
  $('mirror').setAttribute('aria-pressed',String(connected));$('mirror').textContent=connected?'Ngắt đồng bộ Mao':'Đồng bộ Mao';
  if(state==='connected'){$('operator-note').textContent='Đồng bộ phụ đề, khẩu hình và chat. Âm thanh phụ được tắt để tránh tiếng lặp.';clearTimeout(chatTimer);pollChat();}
  if(state==='disconnected'||state==='unavailable'){clearTimeout(chatTimer);chatController?.abort();$('operator-note').textContent='Chưa kết nối được Mao đang chạy. Bản dàn cảnh vẫn dùng được.';}
  if(state==='audio-unavailable')$('operator-note').textContent='Trình duyệt chưa phát được luồng đồng bộ. Hãy kiểm tra nguồn âm thanh Mao.';
}
if(layer!=='background'){
  const bridge=createNativeBridge();
  Object.assign(bridge.options,{mode:'window',presentation:'portrait',maxFps:30,pointerInteractive:false,scrollToResize:false,forceIgnoreMouse:true});
  const offline=async()=>({ok:true,json:async()=>({phase:'idle',server_now:Date.now()/1000})});
  bridge.singingFetcher=offline;bridge.state.socket='offline';
  try{
    const {mountNativeAvatar}=await import('./draco/native-avatar.mjs');
    avatar=await mountNativeAvatar($('avatar'),bridge);
    bridge.renderer.performAction('think');
    $('avatar').dataset.ready='true';
    mirror=new MaoMirror({bridge,onCaption:text=>{$('subtitle').textContent=text||'Chưa có hoạt động.';},onState:mirrorState});
    $('mirror').disabled=false;
    $('mirror').onclick=()=>mirror.socket?mirror.stop():mirror.connect();
    if(params.get('mao')==='1')mirror.connect();
  }catch{
    $('avatar').textContent='Chưa tải được Mao. Hãy mở trang qua máy chủ xem trước.';
    $('avatar').dataset.ready='error';
  }
}
window.addEventListener('pagehide',()=>{session.dispose();mirror?.stop();clearTimeout(chatTimer);clearTimeout(frameTimer);clearTimeout(gameTimer);clearTimeout(autonomyTimer);if(frameObjectURL)URL.revokeObjectURL(frameObjectURL);chatController?.abort();avatar?.dispose();window.removeEventListener('resize',resize);},{once:true});
