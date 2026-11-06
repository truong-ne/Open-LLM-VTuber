import {createClassroomMusic} from './classroom-music.mjs?v=2';
import {mountLiveMonitor} from './live-monitor.mjs';
import {countdown, seatRows, avatarUrl, avatarFallback} from './classroom-state.mjs?v=3';

const ASSETS = new URL('./assets/classroom/', import.meta.url);
const MARKUP = `
<div class="classroom-toolbar"><button data-action="panel" aria-expanded="false"><span id="current-mode-name">Phòng của Mao</span> <span id="preview-badge" hidden>Xem thử</span><span>▾</span></button></div>
<aside class="classroom-controls" hidden>
  <header><span>CHẾ ĐỘ LIVESTREAM</span><h2>Vua Tiếng Việt</h2><p>Mao dẫn lớp, cả nhà cùng đoán.</p></header>
  <label>Kênh TikTok<input id="account-input" value="@thanhoathirty6" maxlength="25"></label>
  <label>Nhạc nền <input id="music-volume" type="range" min="0" max="100" value="35" aria-label="Âm lượng nhạc nền"><span id="music-status">35% · Âm lượng cố định</span></label>
  <button data-action="on" class="primary">Mở lớp mới</button>
  <button data-action="off">Tắt lớp · Mao thường</button>
  <details id="recent-results" class="honor-details"><summary>Kết quả 10 câu gần đây</summary><p>Thứ hạng theo đáp án đúng đầu tiên mà máy chủ nhận.</p><ol id="recent-results-list"></ol></details>
  <details class="honor-details"><summary>Bảng vinh danh dài hạn · Top 40</summary><p>Top 1 ngày +10, top 2 ngày +6, top 3 ngày +3. Chốt một lần lúc 00:00 giờ Việt Nam; xếp theo số câu đúng trong ngày, rồi điểm trả lời.</p><ol id="honor-full"></ol></details>
  <button data-action="preview">Xem bố cục lớp</button>
  <p id="control-status" role="status">Điểm được lưu sau mỗi câu. Khán giả chơi bằng bình luận TikTok.</p>
</aside>
<section class="mao-classroom" hidden aria-label="Vua Tiếng Việt trong Mao Desktop">
 <div class="classroom-frame">
  <header class="classroom-masthead"><span class="classroom-stamp">LỚP HỌC CÙNG MAO <i>✦</i> MỖI NGÀY MỘT TỪ HAY</span><h1>Vua Tiếng Việt<span>Tiếng mình, thương mình.</span></h1><div class="classroom-session"><b id="account">@thanhoathirty6</b></div></header>
  <div class="classroom-lesson">
   <section class="classroom-teacher"><span class="teacher-tag">MAO <small>Người bạn dẫn lớp</small></span><div id="teacher-stage" aria-label="Mao 3D nửa người, nói và biểu cảm theo giọng"></div><p id="teacher-speech"></p><img class="teacher-plant" alt="" aria-hidden="true"><img class="teacher-books" alt="" aria-hidden="true"></section>
   <section class="classroom-board"><div class="board-meta"><span id="category">Từ đời thường</span><strong id="timer">60</strong></div><p id="clue" aria-live="polite"></p><div id="letters" class="letters"></div><div id="slots" class="slots"></div><p id="hint-label" class="hint-label"></p><div class="board-meta bottom"><span id="round-players"></span><span id="phase-label"></span></div><div class="chalk-rest" aria-hidden="true"></div></section>
  </div>
  <section class="classroom-result"><span class="result-icon">✦</span><div><div class="result-line"><strong id="answer-title">Mỗi câu đúng, tiến thêm một bàn</strong><span id="correct-count"></span></div><p id="explanation"></p></div></section>
  <section class="classroom-live"><header><h2>Bình luận trực tiếp</h2><span id="comment-count">Chờ bình luận</span></header><p class="comment-method">Thứ tự đúng tính theo lúc máy chủ nhận đáp án đầu tiên.</p><div id="round-podium" class="round-podium"></div><ol id="live-comments" aria-live="polite"></ol></section>
  <aside class="classroom-honor"><div class="honor-heading"><h2>Vinh danh dài hạn</h2><span id="honor-rules">TOP NGÀY: 1 +10 · 2 +6 · 3 +3</span></div><ol id="honor-list"></ol></aside>
  <div class="classroom-pupils"><header><h2>Lớp học · 40 chỗ</h2><span>Top ngày theo số câu đúng · đặt lại lúc 00:00</span></header><section class="desks" id="desks" aria-label="Bốn mươi bàn học của khán giả"></section></div>
  <p class="classroom-offline" hidden>Mất kết nối với Mao · Đang thử lại</p>
 </div>
</section>`;

export function mountDesktopClassroom({fetcher=fetch,ipc=window.electron?.ipcRenderer,baseUrl='http://127.0.0.1:12393'}={}) {
  if (!ipc?.invoke) throw Error('Classroom controls require Mao Desktop.');
  const style=document.createElement('link');style.rel='stylesheet';style.href=new URL('./classroom-desktop.css?v=7',import.meta.url).href;document.head.append(style);
  const seatStyle=document.createElement('link');seatStyle.rel='stylesheet';seatStyle.href=new URL('./classroom-seats.css?v=6',import.meta.url).href;document.head.append(seatStyle);
  const root=document.createElement('div');root.id='mao-classroom-desktop';root.innerHTML=MARKUP;document.body.append(root);
  const $=id=>root.querySelector(`#${id}`), scene=root.querySelector('.mao-classroom'), controls=root.querySelector('.classroom-controls');
  const liveMonitor=mountLiveMonitor(controls,{fetcher,baseUrl});
  const music=createClassroomMusic();
  try{const saved=localStorage.getItem('mao-classroom-music-volume');if(saved!==null)$('music-volume').value=String(Math.max(0,Math.min(100,Number(saved)||0)));}catch{}
  $('music-volume').oninput=()=>{try{localStorage.setItem('mao-classroom-music-volume',$('music-volume').value);}catch{}tick();};
  const text=(id,value)=>{$(id).textContent=String(value??'');};
  const make=(tag,className,value)=>{const el=document.createElement(tag);el.className=className||'';if(value!==undefined)el.textContent=value;return el;};
  for (const [selector,file] of [['.teacher-plant','plant.png'],['.teacher-books','books.png']]) root.querySelector(selector).src=new URL(file,ASSETS).href;
  let current=null,preview=false,disposed=false,offset=0,poll,ticker,seatKey='',honorKey='',commentKey='',presented='',subtitleText='',stylesReady=false;
  const controller={teacherStage:$('teacher-stage'),get active(){return stylesReady&&(preview||!!current?.classroom?.enabled)&&document.body.dataset.mode==='window';},get music(){return music.status;},get state(){return current;},get preview(){return preview;},render,showPreview,dispose};
  let loadedStyles=0;const stylesheetReady=()=>{if(++loadedStyles===2){stylesReady=true;visibility();}};
  for(const link of [style,seatStyle]){link.addEventListener('load',stylesheetReady,{once:true});link.addEventListener('error',()=>text('control-status','Chưa tải được giao diện lớp học. Hãy mở lại Mao Desktop.'),{once:true});}
  const fallbackSeeds=new Map();
  for(let i=0;i<40;i++){
    const desk=make('article','desk empty');desk.dataset.rank=i+1;
    const student=make('div','student');student.setAttribute('aria-hidden','true');
    const avatar=make('img','student-avatar');avatar.alt='';avatar.referrerPolicy='no-referrer';avatar.crossOrigin='anonymous';avatar.decoding='async';
    avatar.onload=()=>{student.dataset.failed='false';};avatar.onerror=()=>{student.dataset.failed='true';if(avatar.src!==avatarFallback())avatar.src=avatarFallback();};
    student.append(make('span','avatar-halo'),make('span','avatar-fallback','?'),avatar);
    const name=make('div','seat-name',`Bàn ${i+1}`),points=make('small','seat-score');desk.append(make('span','seat-rank',String(i+1).padStart(2,'0')),student,make('div','desk-surface'),name,points);$('desks').append(desk);
  }
  function avatarSource(row,state){
    let seed=row.avatar_seed;
    if(!seed){const key=`${state.classroom?.session_id||'preview'}:${row.nickname}`;if(!fallbackSeeds.has(key))fallbackSeeds.set(key,crypto.randomUUID());seed=fallbackSeeds.get(key);}
    return avatarUrl(seed);
  }
  function paintSeats(state){
    const rows=seatRows(state),key=JSON.stringify(rows);if(key===seatKey)return;seatKey=key;
    rows.forEach((row,i)=>{const desk=$('desks').children[i],avatar=desk.querySelector('.student-avatar');desk.classList.toggle('empty',!row);desk.querySelector('.seat-name').textContent=row?row.nickname:`Chờ bạn vào lớp`;desk.querySelector('.seat-name').dataset.length=row?(Array.from(row.nickname||'').length>28?'extra':Array.from(row.nickname||'').length>18?'long':'normal'):'normal';desk.querySelector('.seat-name').title=row?.nickname||'';desk.querySelector('.seat-score').textContent=row?`${row.correct} câu đúng`:'';desk.setAttribute('aria-label',row?`Hạng ${i+1}: ${row.nickname}, ${row.correct} câu đúng`:`Bàn ${i+1} còn trống`);
      if(row){const src=avatarSource(row,state);if(avatar.getAttribute('src')!==src){desk.querySelector('.student').dataset.failed='false';avatar.src=src;}desk.querySelector('.avatar-fallback').textContent=Array.from(row.nickname||'?')[0].toLocaleUpperCase('vi');}
      else{avatar.removeAttribute('src');desk.querySelector('.avatar-fallback').textContent='?';}
    });
  }
  function paintHonor(state){
    const board=state.classroom?.honor||[],key=JSON.stringify(board);if(key===honorKey)return;honorKey=key;
    $('honor-list').replaceChildren();$('honor-full').replaceChildren();
    if(!board.length){$('honor-list').append(make('li','empty','Chốt top ngày lúc 00:00 giờ Việt Nam để ghi tên vào bảng vinh danh!'));return;}
    for(const [i,row] of board.entries()){
      const entry=make('li','honor-full-row');entry.append(make('b','',`${i+1}. ${row.nickname}`),make('span','',`${row.honor_points} điểm · 🥇${row.gold||0} 🥈${row.silver||0} 🥉${row.bronze||0}`));$('honor-full').append(entry);
      if(i>=3)continue;
      const li=make('li','honor-person');li.dataset.rank=i+1;
      const avatar=make('img','honor-avatar');avatar.src=avatarSource(row,state);avatar.alt='';avatar.referrerPolicy='no-referrer';avatar.crossOrigin='anonymous';avatar.onerror=()=>{avatar.onerror=null;avatar.src=avatarFallback();};
      const info=make('div','honor-info');info.append(make('span','name',row.nickname),make('span','honor-points',`${row.honor_points} điểm`));
      li.append(make('span','rank',String(i+1).padStart(2,'0')),avatar,info);$('honor-list').append(li);
    }
  }
  function paintComments(state){
    const c=state.classroom||{},items=c.comments||[],results=c.round_results||[],key=JSON.stringify([state.round_id,state.phase,items,results]);if(key===commentKey)return;commentKey=key;
    $('live-comments').replaceChildren();$('round-podium').replaceChildren();
    text('comment-count',items.length?`${items.length} bình luận gần nhất`:'Chờ bình luận của bạn');
    if(state.phase==='finished'){
      for(const row of results.slice(0,3)){
        const chip=make('span','podium-chip');chip.dataset.rank=row.position;
        chip.title=`#${row.position} ${row.nickname} ${row.player_tag||''} · ${(row.elapsed_ms/1000).toFixed(3)}s`;chip.textContent=`#${row.position} ${row.nickname} · ${(row.elapsed_ms/1000).toFixed(3)}s`;$('round-podium').append(chip);
      }
      if(!results.length)$('round-podium').append(make('span','','Chưa có đáp án đúng ở câu này.'));
    }
    for(const row of items.slice(-4)){
      const li=make('li','live-comment');li.dataset.status=row.status||'received';
      const meta=make('div','comment-meta');meta.append(make('b','comment-name',row.nickname),make('time','',`${(row.elapsed_ms/1000).toFixed(3)}s`));
      if(row.position)meta.append(make('span','comment-verdict',`Đúng #${row.position}`));
      else if(row.status==='correct')meta.append(make('span','comment-verdict','Đúng · đã ghi nhận trước'));
      else if(state.phase==='finished')meta.append(make('span','comment-verdict',row.status==='incorrect'?'Chưa đúng':'Không tính lượt'));
      else meta.append(make('span','comment-verdict',row.status==='not_scored'?'Không tính lượt':'Đã nhận'));
      li.title=`${row.nickname}: ${row.text}`;li.append(meta,make('p','comment-text',row.text));$('live-comments').append(li);
    }
    if(!items.length)$('live-comments').append(make('li','comments-empty','Bình luận đáp án sẽ hiện tại đây. Kết quả được chốt khi hết giờ.'));
  }
  function visibility(){
    text('current-mode-name',controller.active?'Vua Tiếng Việt':'Phòng của Mao');
    scene.hidden=!controller.active;document.body.dataset.maoClassroom=controller.active?'on':'off';
    root.querySelector('[data-action="panel"]').dataset.active=!!current?.classroom?.enabled;
  }
  function render(state){
    current=state;offset=(state.server_now||Date.now()/1000)-Date.now()/1000;
    if(preview){if(previewState){previewState.classroom.honor=state.classroom?.honor||[];paintHonor(previewState);}visibility();return;}
    renderScene(state);visibility();
  }
  function renderScene(state){
    const c=state.classroom||{},result=state.phase==='finished';
    scene.dataset.phase=state.phase;
    text('honor-rules','TOP NGÀY · '+(c.honor_bonuses||[10,6,3]).map((points,i)=>`TOP ${i+1} +${points}`).join(' · '));
    text('account',c.account||'@thanhoathirty6');text('category',state.category||'Từ đời thường');
    text('clue',state.phase==='waiting'?'Câu tiếp theo đang được chuẩn bị. Cả lớp sẵn sàng chưa?':result?`Đáp án: ${state.answer}`:state.hints?.at(-1)||'Mao đang chuẩn bị gợi ý…');
    $('clue').dataset.length=$('clue').textContent.length>100?'long':'short';
    $('letters').replaceChildren();const letters=state.phase==='waiting'?[]:result?Array.from((state.answer||'').toLocaleUpperCase('vi').replaceAll(' ','')):state.letters||[];
    $('letters').dataset.long=letters.length>11;
    letters.forEach((letter,i)=>{const tile=make('span','letter',letter);tile.style.setProperty('--tilt',`${[-2,1,-1,2,0][i%5]}deg`);$('letters').append(tile);});
    $('slots').replaceChildren();if(!result&&state.phase!=='waiting')for(const n of state.slots||[]){const word=make('span','slot-word');for(let i=0;i<n;i++)word.append(make('i','slot'));$('slots').append(word);}
    text('hint-label',result?'Mình cùng nhớ thêm một từ hay.':`Gợi ý ${(state.hint_index||0)+1}/${state.hint_count||3} · Bình luận đáp án để chơi`);
    text('round-players',`${state.participants||0} bạn đang đoán`);
    text('phase-label',result?'Cùng nghe Mao giải thích':state.phase==='waiting'?'Đợi Mao một chút nhé':'Cả lớp cùng nghĩ nào!');
    const correct=c.round_results?.length?c.round_results:(state.leaderboard||[]).filter(p=>p.score===100),winner=correct[0];
    text('answer-title',result?(winner?`Nhanh nhất: ${winner.nickname}`:'Chưa ai đúng, mình cùng học từ mới nhé!'):'Mỗi câu đúng, tiến thêm một bàn');
    text('correct-count',result?`${state.correct_count??correct.length} bạn đúng`:'');
    text('explanation',result?state.explanation||'':'Đoán đúng +1 câu. Điểm tốc độ phân hạng khi bằng nhau. Không cần quà tặng để vào lớp.');
    
    if(!preview)text('teacher-speech',subtitleText);
    paintSeats(state);paintHonor(state);paintComments(state);tick();
  }
  function tick(){
    visibility();
    music.update({enabled:stylesReady&&!preview&&document.body.dataset.mode==='window',level:Number($('music-volume').value)/100});
    text('music-status',music.status.error?'Nhấn vào lớp để bật nhạc':`${$('music-volume').value}% · Âm lượng cố định`);
    const state=preview?previewState:current;if(!state)return;
    const now=Date.now()/1000+(preview?0:offset),seconds=preview?45:countdown(state.ends_at,now);
    text('timer',state.phase==='playing'?seconds:state.phase==='waiting'?'…':'✓');scene.dataset.urgent=state.phase==='playing'&&seconds<=10;
    
    if(state.phase==='finished')text('phase-label',`Nghỉ ${countdown(state.cooldown_ends_at,now)} giây · Chờ Mao nói xong`);
  }
  let previewState;
  function showPreview(enabled=true){
    if(enabled&&current?.classroom?.enabled){text('control-status','Lớp thật đang chạy. Tắt lớp trước khi xem bố cục minh họa.');return;}
    preview=enabled;$('preview-badge').hidden=!preview;
    root.querySelector('[data-action="preview"]').textContent=preview?'Đóng xem bố cục':'Xem bố cục lớp';
    if(preview){const now=Date.now()/1000,names=['Lan Anh','Minh Khang','Bảo Ngọc','Thanh Hóa','Hải Yến','Tuấn Anh','Ngọc Mai','Bạn Mèo','Hoàng Nam','Khánh Linh','Hà My','Gia Huy','Thảo Nhi','Minh Châu','Quốc Bảo'];const rows=names.map((nickname,i)=>({nickname,correct:Math.max(1,28-i*2),points:2300-i*120}));previewState={phase:'playing',round_id:'desktop-preview',server_now:now,ends_at:now+60,category:'Con vật',hint_index:0,hints:['Leo trèo giỏi, thích ăn chuối.'],letters:['N','K','H','C','Ỉ','O'],slots:[3,3],participants:36,classroom:{enabled:true,round_number:42,ends_at:now+26000,account:'@thanhoathirty6',players:152,standings:rows,seats:rows,honor:current?.classroom?.honor||[],comments:names.slice(0,5).map((nickname,i)=>({id:i,nickname,text:['Mao ơi câu này vui quá','Con khỉ','Mình đoán là khỉ nè','Cả nhà cùng cố lên','con mèo'][i],elapsed_ms:2500+i*1300,status:'received'})),round_results:[]}};renderScene(previewState);}else if(current)renderScene(current);
    if(preview)text('teacher-speech','Đang xem thử giao diện. Mở lớp để Mao dẫn câu hỏi.');
    controls.hidden=true;root.querySelector('[data-action="panel"]').setAttribute('aria-expanded','false');visibility();
  }
  async function control(enabled){
    const buttons=[...controls.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
    try{const state=await ipc.invoke('mao-classroom-control',{enabled,account:$('account-input').value.trim()});if(state.error)throw Error(state.error);preview=false;$('preview-badge').hidden=true;render(state);text('control-status',enabled?'Đã mở lớp. Mao sẽ bắt đầu khi lời nói hiện tại kết thúc.':'Đã tắt lớp. Mao trở về trò chuyện thường.');controls.hidden=true;}
    catch(error){text('control-status',`Chưa đổi chế độ: ${error.message}`);}
    finally{buttons.forEach(b=>b.disabled=false);}
  }
  root.querySelector('[data-action="panel"]').onclick=event=>{controls.hidden=!controls.hidden;event.currentTarget.setAttribute('aria-expanded',String(!controls.hidden));};
  root.querySelector('[data-action="on"]').onclick=()=>control(true);root.querySelector('[data-action="off"]').onclick=()=>control(false);root.querySelector('[data-action="preview"]').onclick=()=>showPreview(!preview);
  $('recent-results').ontoggle=async()=>{
    if(!$('recent-results').open)return;
    $('recent-results-list').replaceChildren(make('li','','Đang tải kết quả…'));
    try{const response=await fetcher(`${baseUrl}/api/classroom/results`,{cache:'no-store',signal:AbortSignal.timeout(4000)});if(!response.ok)throw Error();const data=await response.json();$('recent-results-list').replaceChildren();for(const round of data.rounds||[]){const item=make('li','honor-full-row');item.append(make('b','',`Đáp án: ${round.answer}`),make('span','',new Date(round.completed_at*1000).toLocaleString('vi-VN')));for(const winner of (round.winners||[]).slice(0,3))item.append(make('span','',`#${winner.position} ${winner.nickname} · ${(winner.elapsed_ms/1000).toFixed(3)}s`));if(!round.winners?.length)item.append(make('span','','Chưa có người đúng'));$('recent-results-list').append(item);}if(!data.rounds?.length)$('recent-results-list').append(make('li','','Kết quả sẽ được lưu từ câu tiếp theo.'));}catch{$('recent-results-list').replaceChildren(make('li','','Chưa tải được kết quả, hãy mở lại sau.'));}
  };
  const subtitles=new MutationObserver(()=>{if(preview)return;const text=document.querySelector('#mao-window-subtitle .mao-caption p')?.textContent?.trim()||'';if(text===subtitleText)return;subtitleText=text;$('teacher-speech').textContent=text;});
  subtitles.observe(document.body,{childList:true,subtree:true,characterData:true});
  async function refresh(){
    if(disposed)return;
    try{const response=await fetcher(`${baseUrl}/api/vuatiengviet/state`,{cache:'no-store',signal:AbortSignal.timeout(4000)});if(!response.ok)throw Error(String(response.status));const state=await response.json();render(state);root.querySelector('.classroom-offline').hidden=true;
      if(state.classroom?.enabled&&state.phase==='waiting'&&presented!==state.round_id&&controller.active&&window.maoDraco?.state.ready){const response=await fetcher(`${baseUrl}/api/vuatiengviet/presentation`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({round_id:state.round_id}),signal:AbortSignal.timeout(3000)});if(response.ok&&(await response.json()).accepted)presented=state.round_id;}
    }catch{root.querySelector('.classroom-offline').hidden=false;}finally{if(!disposed)poll=setTimeout(refresh,750);}
  }
  function dispose(){liveMonitor.dispose();music.dispose();disposed=true;clearTimeout(poll);clearInterval(ticker);subtitles.disconnect();root.remove();style.remove();seatStyle.remove();delete document.body.dataset.maoClassroom;}
  ticker=setInterval(tick,250);refresh();return controller;
}
