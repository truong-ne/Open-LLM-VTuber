const $=id=>document.getElementById(id),node=(tag,text)=>{const element=document.createElement(tag);element.textContent=text;return element;};
let token='',state=null,tab='events',sourceId=null,editing=null;
async function api(path,body){if(!token)token=(await(await fetch('/api/playroom/session',{cache:'no-store'})).json()).token;
 const response=await fetch(path,{method:body?'POST':'GET',headers:{'X-Mao-Token':token,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,cache:'no-store'});
 const value=await response.json();if(!response.ok)throw Error(value.error||'Chưa thực hiện được thao tác.');return value;}
function feedback(text,error=false){$('feedback').textContent=text;$('feedback').className=error?'error':'';}
function button(label,run){const item=node('button',label);item.onclick=async()=>{item.disabled=true;try{await run();}catch(error){feedback(error.message,true);}finally{item.disabled=false;}};return item;}
async function action(value){feedback('Đang xử lý…');await api('/api/runtime/action',value);await refresh();}
async function showSource(id){sourceId=id;const value=await api('/api/runtime/source/'+encodeURIComponent(id));$('source-body').textContent=JSON.stringify(value,null,2);$('forget').disabled=value.source.deleted;if(!$('source').open)$('source').showModal();}
function evidence(container,records){for(const id of records||[])container.append(button('Xem nguồn '+String(id).slice(0,8),()=>showSource(id)));}
function draw(){const root=$('content');root.replaceChildren();const rows=state[tab]||[];
 if(!rows.length){root.append(node('p','Chưa có mục nào. Dữ liệu xuất hiện từ các tương tác mới; Mao không nhập lại ký ức cũ.'));return;}
 for(const row of rows){const card=node('article','');
 if(tab==='focus'){card.append(node('h3',row.repair?'Đang làm rõ một hiểu nhầm':'Chủ đề hiện tại'),node('p',row.topic),node('p',row.question?'Đang chờ trả lời: '+row.question:'Đã nhận lượt mới; chưa có câu hỏi đang chờ.'));evidence(card,[row.source_event]);}
 if(tab==='events'){card.append(node('h3',row.deleted?'Nguồn đã quên':row.kind+' · '+row.visibility),node('p',row.preview||'Không lưu nội dung'),node('div',row.actor_id));card.append(button('Xem lượt và trạng thái phát',()=>showSource(row.id)));}
 if(tab==='items'){card.append(node('h3',row.claim_type+' · '+row.status),node('p',row.content));evidence(card,row.evidence);card.append(button('Sửa thông tin',()=>{editing=row;$('edit-text').value=row.content;$('edit').showModal();}));}
 if(tab==='activities'){card.append(node('h3','Câu chuyện hư cấu · '+row.status),node('p',(row.canon||[]).map(item=>item.text).join('\n\n')),node('div','Phiên bản '+row.revision+' · hết hạn '+row.expires));card.append(node('small','Tiếp tục cùng Mao qua hội thoại; dùng /story finish khi muốn kết thúc.'));}
 if(tab==='preferences'){card.append(node('h3',row.dimension+' → '+row.choice),node('p','Trạng thái: '+row.status+' · phạm vi: '+row.actor_id));evidence(card,(row.evidence||[]).flatMap(item=>[item.event,item.feedback].filter(Boolean)));card.append(button('Khóa ranh giới / dừng học nét này',()=>action({operation:'lock_preference',id:row.id})),button('Bỏ nét này',()=>action({operation:'retire_preference',id:row.id})));if(row.status==='eligible')card.append(button('Tạo ứng viên để đánh giá',()=>action({operation:'propose',id:row.id})));}
 if(tab==='policies'){card.append(node('h3','Chính sách #'+row.revision+' · '+row.status),node('p',JSON.stringify(row.settings)),node('pre',JSON.stringify(row.evaluations,null,2)),node('small','Ngân sách thử còn lại: '+row.budget));
 card.append(button('Đánh giá biệt lập',()=>action({operation:'evaluate',revision:row.revision})),button('Thử tối đa 20 lượt',()=>action({operation:'trial',revision:row.revision,budget:20})),button('Áp dụng khi đủ bằng chứng',()=>action({operation:'promote',revision:row.revision})),button('Rút thay đổi',()=>action({operation:'rollback',revision:row.revision})));}
 root.append(card);}}
async function refresh(){try{state=await api('/api/runtime/state');$('metrics').replaceChildren();for(const [label,value] of [['Trải nghiệm',state.counts.episodes],['Ký ức có nguồn',state.counts.memories],['Lượt đã phát',state.health.turns.find(row=>row.status==='completed')?.count||0],['p95 / số mẫu',Math.round(state.health.latency.p95_ms||0)+' ms / '+state.health.latency.samples]]){const card=node('div','');card.className='card';card.append(node('small',label),Object.assign(node('strong',String(value)),{className:'metric'}));$('metrics').append(card);} $('health').textContent=JSON.stringify({flags:state.flags,worker:state.worker,health:state.health},null,2);draw();feedback('Đã đọc dữ liệu mới nhất.');}catch(error){feedback(error.message,true);}}
for(const item of $('tabs').querySelectorAll('button'))item.onclick=()=>{tab=item.dataset.tab;for(const other of $('tabs').children)other.dataset.active=String(other===item);if(state)draw();};
$('refresh').onclick=refresh;$('close-source').onclick=()=>$('source').close();$('close-edit').onclick=()=>$('edit').close();
$('forget').onclick=async()=>{try{await action({operation:'forget_source',id:sourceId});$('source').close();}catch(error){feedback(error.message,true);}};
$('save-edit').onclick=async()=>{try{await action({operation:'edit_item',id:editing.id,revision:editing.revision,content:$('edit-text').value});$('edit').close();}catch(error){feedback(error.message,true);}};
await refresh();
document.title+=' · '+(state?.scope??'chưa kết nối');
const focusTab=node('button','Đang chú ý');focusTab.dataset.tab='focus';focusTab.onclick=()=>{tab='focus';for(const other of $('tabs').children)other.dataset.active=String(other===focusTab);if(state)draw();};$('tabs').append(focusTab);
