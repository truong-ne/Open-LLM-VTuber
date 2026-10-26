const $=id=>document.getElementById(id);let token='',revision=0;
function ready(value){$('draft').disabled=!value;$('activate').disabled=!value;}
async function load(){
  ready(false);$('message').textContent='';
  try{
    const session=await fetch('/api/playroom/session',{cache:'no-store'});if(!session.ok)throw Error();token=(await session.json()).token;
    const response=await fetch('/api/persona',{headers:{'X-Mao-Token':token},cache:'no-store'});if(!response.ok)throw Error();const p=await response.json();revision=p.revision;
    $('prompt').value=p.prompt;$('proactive').value=p.proactive_prompt;$('autonomy').value=p.autonomy_prompt;$('topics').value=p.topics.join('\n');
    $('status').textContent=(p.status==='active'?'Đang bật':'Bản nháp · chưa nhập vai')+' · phiên bản '+revision;ready(true);
  }catch{$('status').textContent='Chưa kết nối được PostgreSQL';$('message').textContent='Kiểm tra DB và máy chủ của Mao, rồi bấm tải lại.';}
}
async function save(status){
  ready(false);$('message').textContent='Đang lưu vào PostgreSQL…';
  try{
    const document={revision,status,prompt:$('prompt').value,proactive_prompt:$('proactive').value,autonomy_prompt:$('autonomy').value,topics:$('topics').value.split('\n').map(s=>s.trim()).filter(Boolean)};
    if(status==='active'&&!document.prompt.trim())throw Error('Hãy viết persona trước khi bật.');
    const response=await fetch('/api/persona/save',{method:'POST',headers:{'Content-Type':'application/json','X-Mao-Token':token},body:JSON.stringify(document)});
    if(!response.ok)throw Error('Chưa lưu được. Persona có thể đã đổi ở nơi khác; hãy tải lại để kiểm tra.');
    const p=await response.json();revision=p.revision;$('status').textContent=(p.status==='active'?'Đang bật':'Bản nháp · chưa nhập vai')+' · phiên bản '+revision;$('message').textContent='Đã lưu trong PostgreSQL.';
  }catch(error){$('message').textContent=error.message;}finally{ready(true);}
}
$('profile-form').onsubmit=event=>{event.preventDefault();save('active');};$('draft').onclick=()=>save('draft');$('reload').onclick=load;load();
