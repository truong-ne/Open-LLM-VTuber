import {createMemoryBrowser} from './memory.mjs?v=1';
const $=id=>document.getElementById(id);
const fields=['prompt','proactive','autonomy','topics'];
const tabs=[...document.querySelectorAll('[data-view]')];
let token='',revision=0,baseline='',loaded=false,busy=false,currentStatus='draft';
let currentView='personality';
const heading={title:document.querySelector('h1').textContent,eyebrow:document.querySelector('.page-heading .eyebrow').textContent,help:document.querySelector('.page-heading p').textContent};
const memory=createMemoryBrowser({getToken:async()=>{
  const response=await fetch('/api/playroom/session',{cache:'no-store'});
  if(!response.ok)throw Error('Chưa kết nối được dịch vụ Mao. papa thử làm mới nhé.');
  token=(await response.json()).token;return token;
}});
function documentValues(){return {prompt:$('prompt').value,proactive_prompt:$('proactive').value,autonomy_prompt:$('autonomy').value,topics:$('topics').value.split('\n').map(s=>s.trim()).filter(Boolean)};}
function dirty(){return loaded&&JSON.stringify(documentValues())!==baseline;}
function message(text='',error=false){$('message').textContent=text;$('message').dataset.error=String(error);}
function connection(state,label){$('connection').dataset.state=state;$('connection-label').textContent=label;}
function showView(view,focus=false){
  currentView=view;
  for(const tab of tabs){const selected=tab.dataset.view===view;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;$(tab.getAttribute('aria-controls')).hidden=!selected;if(selected&&focus)tab.focus();}
  const isMemory=view==='memory';
  document.querySelector('.savebar').hidden=isMemory;document.querySelector('.apply-note').hidden=isMemory;
  document.querySelector('h1').textContent=isMemory?'Ký ức của Mao':heading.title;
  document.querySelector('.page-heading .eyebrow').textContent=isMemory?'MEMORY / ARCHIVE':heading.eyebrow;
  document.querySelector('.page-heading p').textContent=isMemory?'Những điều Mao đã lưu lại, để nhớ và hiểu hơn.':heading.help;
  $('reload').title=isMemory?'Làm mới ký ức':'Đọc lại hồ sơ đã lưu';
  $('reload').lastChild.textContent=isMemory?'Làm mới ký ức':'Tải lại hồ sơ';
  if(isMemory)memory.open();
}
function counters(){for(const name of ['prompt','proactive','autonomy']){const count=$(name).value.length;$(name+'-count').textContent=count.toLocaleString('vi-VN')+' / '+$(name).maxLength.toLocaleString('vi-VN');}$('topics-count').textContent=documentValues().topics.length+' / 40 chủ đề';}
function controls(){
  $('draft').disabled=!loaded||busy;$('activate').disabled=!loaded||busy;$('reload').disabled=busy;
  for(const name of fields)$(name).disabled=!loaded||busy;
  $('profile-form').setAttribute('aria-busy',String(busy));const changed=dirty();
  $('save-indicator').dataset.state=busy?'loading':!loaded?'error':changed?'dirty':'saved';
  $('save-label').textContent=busy?'Đang đồng bộ…':!loaded?'Chưa tải được hồ sơ':changed?'Có thay đổi chưa lưu':'Đã đồng bộ hồ sơ';
  $('save-help').textContent=changed?'Lưu để Mao nhận những điều papa vừa chỉnh.':currentStatus==='draft'?'Hồ sơ là bản nháp; Mao chưa nhập vai.':'Nội dung đang khớp với phiên bản đã lưu.';
}
function profileStatus(p){
  currentStatus=p.status;$('status').textContent=p.status==='active'?'Đang áp dụng tính cách':'Bản nháp · chưa nhập vai';$('status').dataset.state=p.status;$('revision').textContent='Phiên bản '+p.revision;
  let date=p.updated_at?new Date(p.updated_at):null;
  if(date&&!Number.isFinite(date.getTime()))date=new Date(String(p.updated_at).replace(' ','T').replace(/\+00$/,'Z'));
  $('updated').textContent=date&&Number.isFinite(date.getTime())?new Intl.DateTimeFormat('vi-VN',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Ho_Chi_Minh'}).format(date):'Vừa lưu';
}
function populate(p){revision=p.revision;$('prompt').value=p.prompt||'';$('proactive').value=p.proactive_prompt||'';$('autonomy').value=p.autonomy_prompt||'';$('topics').value=(p.topics||[]).join('\n');baseline=JSON.stringify(documentValues());loaded=true;profileStatus(p);counters();}
async function load(){
  if(busy)return;
  if(dirty()&&!window.confirm('Tải lại hồ sơ sẽ bỏ các chỉnh sửa chưa lưu. papa muốn tải lại?'))return;
  busy=true;controls();message();connection('loading','Đang kết nối…');
  try{const session=await fetch('/api/playroom/session',{cache:'no-store'});if(!session.ok)throw Error();token=(await session.json()).token;const response=await fetch('/api/persona',{headers:{'X-Mao-Token':token},cache:'no-store'});if(!response.ok)throw Error();populate(await response.json());connection('connected','Hồ sơ đã kết nối');}
  catch{connection('error','Chưa kết nối được');if(!loaded){$('status').textContent='Chưa tải được hồ sơ';$('status').dataset.state='error';}message('Chưa đọc được hồ sơ. papa kiểm tra dịch vụ Mao rồi bấm tải lại nhé.',true);}
  finally{busy=false;controls();}
}
async function save(status){
  if(!loaded||busy)return;
  const values=documentValues();
  if(status==='active'&&!values.prompt.trim()){showView('personality');message('papa viết một chút về tính cách Mao trước khi áp dụng nhé.',true);$('prompt').focus();return;}
  if(values.topics.length>40||values.topics.some(s=>s.length>100)){showView('exploration');message('Nhập tối đa 40 chủ đề, mỗi chủ đề không quá 100 ký tự.',true);$('topics').focus();return;}
  if(status==='draft'&&currentStatus==='active'&&!window.confirm('Lưu thành bản nháp sẽ tạm ngừng persona đang bật. Mao chỉ nhập vai trở lại khi papa chọn Lưu & áp dụng. Tiếp tục?'))return;
  busy=true;controls();message('Đang lưu hồ sơ…');
  try{
    const response=await fetch('/api/persona/save',{method:'POST',headers:{'Content-Type':'application/json','X-Mao-Token':token},body:JSON.stringify({revision,status,...values})});
    if(!response.ok){if(response.status===409)throw Error('Hồ sơ đã thay đổi ở nơi khác hoặc nội dung chưa hợp lệ. Chỉnh sửa của papa vẫn được giữ; hãy kiểm tra rồi tải lại khi sẵn sàng.');if(response.status===403)throw Error('Phiên kết nối đã hết hạn. Chỉnh sửa vẫn được giữ; papa tải lại hồ sơ để kết nối lại nhé.');throw Error('Chưa lưu được hồ sơ. Chỉnh sửa vẫn được giữ để papa thử lại.');}
    populate(await response.json());connection('connected','Hồ sơ đã kết nối');message(status==='active'?'Đã lưu. Mao sẽ dùng hồ sơ mới từ lượt trò chuyện tiếp theo.':'Đã lưu bản nháp. Chọn Lưu & áp dụng khi papa muốn Mao nhập vai trở lại.');
  }catch(error){message(error.message,true);}finally{busy=false;controls();}
}
for(const tab of tabs){tab.addEventListener('click',()=>showView(tab.dataset.view));tab.addEventListener('keydown',event=>{if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();let index=tabs.indexOf(tab);if(event.key==='Home')index=0;else if(event.key==='End')index=tabs.length-1;else index=(index+(['ArrowUp','ArrowLeft'].includes(event.key)?-1:1)+tabs.length)%tabs.length;showView(tabs[index].dataset.view,true);});}
for(const name of fields)$(name).addEventListener('input',()=>{counters();controls();message();});
$('profile-form').addEventListener('submit',event=>{event.preventDefault();if(currentView!=='memory')save('active');});$('draft').addEventListener('click',()=>save('draft'));$('reload').addEventListener('click',()=>currentView==='memory'?memory.refresh():load());
window.addEventListener('beforeunload',event=>{if(dirty()){event.preventDefault();event.returnValue='';}});
load();
if(location.hash==='#memory')showView('memory');
