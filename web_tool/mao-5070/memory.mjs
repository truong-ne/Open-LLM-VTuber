const KINDS=new Map([['long_term','Dài hạn'],['social','Giao tiếp'],['skill','Kỹ năng']]);
const SOURCES=new Map([['unverified_claim','Chưa kiểm chứng'],['operator','Người quản lý cung cấp'],['evaluation','Từ đánh giá']]);
const PROVENANCE=new Map([
  ['unverified_claim','Nội dung Mao ghi nhận từ hội thoại hoặc nguồn đọc. Đây là thông tin chưa được kiểm chứng, không phải sự thật đã xác nhận.'],
  ['operator','Nội dung do người quản lý cung cấp. Nhãn này ghi lại nguồn nhập, không bảo đảm mọi dữ kiện đều đúng.'],
  ['evaluation','Nội dung được lưu từ kết quả đánh giá hoặc phiên học. Bằng chứng đính kèm cho biết phạm vi của kết quả.'],
]);
function dateLabel(value){
  const text=String(value||'').replace(' ','T').replace(/\+00$/,'Z');
  const date=new Date(text);
  return Number.isFinite(date.getTime())?new Intl.DateTimeFormat('vi-VN',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Ho_Chi_Minh'}).format(date):'Chưa có thông tin';
}
function node(tag,className,text){const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=String(text);return el;}
function subjectLabel(record){return record.public_alias||(record.subject==='shared'?'Kiến thức chung':record.subject)||'Chưa đặt chủ đề';}

export function createMemoryBrowser({getToken}){
  const $=id=>document.getElementById(id);
  const panel=$('panel-memory'),dialog=$('memory-detail');
  let kind='',page=1,pages=1,request=null,detailRequest=null,searchTimer,loaded=false;
  const feedback=(text,error=false)=>{$('memory-feedback').textContent=text;$('memory-feedback').dataset.error=String(error);};

  function card(record){
    const row=node('button','memory-row');row.type='button';
    const top=node('span','memory-row-top');
    top.append(node('span','memory-kind',KINDS.get(record.kind)||record.kind),node('span','memory-row-subject',subjectLabel(record)),node('span','memory-row-id','#'+record.id));
    const bottom=node('span','memory-row-bottom');
    const origin=node('span','memory-origin',SOURCES.get(record.source)||record.source);origin.dataset.source=record.source;
    bottom.append(origin,node('span','memory-row-date',dateLabel(record.created)));
    if(record.expired)bottom.append(node('span','memory-expiry','Đã hết hạn'));
    row.append(top,node('span','memory-row-text',record.content),bottom);
    row.addEventListener('click',()=>detail(record.id));
    return row;
  }
  async function detail(id){
    detailRequest?.abort();const controller=new AbortController();detailRequest=controller;
    $('memory-detail-title').textContent='Ký ức #'+id;$('memory-detail-body').hidden=true;$('memory-detail-status').textContent='Đang đọc chi tiết…';
    if(!dialog.open)dialog.showModal();
    try{
      const token=await getToken();if(controller.signal.aborted)return;
      const response=await fetch('/api/memories/'+encodeURIComponent(id),{headers:{'X-Mao-Token':token},cache:'no-store',signal:controller.signal});
      if(!response.ok)throw Error(response.status===404?'Ký ức không còn tồn tại. papa làm mới danh sách nhé.':'Chưa đọc được chi tiết ký ức. papa thử lại nhé.');
      const record=await response.json();if(controller!==detailRequest||!dialog.open)return;
      $('memory-detail-content').textContent=record.content;
      const meta=$('memory-detail-meta');meta.replaceChildren();
      for(const [label,value] of [
        ['Loại ký ức',KINDS.get(record.kind)||record.kind],['Về ai / chủ đề',subjectLabel(record)],
        ['Ngày lưu',dateLabel(record.created)],['Hết hạn',dateLabel(record.expires)],
        ['Nguồn ghi nhận',SOURCES.get(record.source)||record.source],['Trạng thái',record.expired?'Đã hết hạn · không được truy hồi':'Đang sử dụng'],
        ['Tìm kiếm ngữ nghĩa',record.has_embedding?'Có dữ liệu tìm kiếm ngữ nghĩa':'Chưa có · vẫn tìm được bằng từ khóa'],
      ]){const row=node('div');row.append(node('dt','',label),node('dd','',value));meta.append(row);}
      $('memory-detail-provenance').textContent=PROVENANCE.get(record.source)||'Chưa có mô tả nguồn ghi nhận.';
      let evidence=record.evidence||'Chưa có nguồn hoặc bằng chứng đính kèm.';
      try{if(record.evidence)evidence=JSON.stringify(JSON.parse(record.evidence),null,2);}catch{}
      $('memory-detail-evidence').textContent=evidence;
      $('memory-detail-status').textContent='';$('memory-detail-body').hidden=false;
    }catch(error){if(error.name!=='AbortError'&&controller===detailRequest&&dialog.open)$('memory-detail-status').textContent=error.message;}
  }
  async function refresh(reset=false){
    clearTimeout(searchTimer);if(reset)page=1;
    request?.abort();const controller=new AbortController();request=controller;
    panel.setAttribute('aria-busy','true');feedback('Đang đọc ký ức đã lưu…');
    $('memory-prev').disabled=true;$('memory-next').disabled=true;
    const params=new URLSearchParams({q:$('memory-search').value.trim(),kind,state:$('memory-state').value,page:String(page)});
    try{
      const token=await getToken();if(controller.signal.aborted)return;
      const response=await fetch('/api/memories?'+params,{headers:{'X-Mao-Token':token},cache:'no-store',signal:controller.signal});
      if(!response.ok)throw Error('Chưa đọc được kho ký ức. papa bấm Làm mới ký ức để thử lại.');
      const data=await response.json();if(controller!==request)return;
      if(!Array.isArray(data.items)||!data.summary)throw Error('Dữ liệu ký ức chưa hợp lệ. papa thử làm mới nhé.');
      for(const key of ['total','active','expired'])$('memory-'+key).textContent=Number(data.summary[key]).toLocaleString('vi-VN');
      page=data.page;pages=data.pages;loaded=true;
      $('memory-list').replaceChildren(...data.items.map(card));
      const empty=!data.items.length;$('memory-empty').hidden=!empty;
      $('memory-empty-title').textContent=data.summary.total===0?'Mao chưa lưu ký ức nào':'Không có ký ức phù hợp';
      $('memory-empty-help').textContent=data.summary.total===0?'Ký ức sẽ xuất hiện khi Mao ghi nhớ thông tin hoặc lưu kết quả học tập.':'Thử từ khóa khác, đổi loại ký ức hoặc chọn Tất cả thời hạn.';
      $('memory-pager').hidden=empty||pages<=1;
      $('memory-page-label').textContent='Trang '+page+' / '+pages;
      $('memory-prev').disabled=page<=1;$('memory-next').disabled=page>=pages;
      feedback(data.total?'Tìm thấy '+Number(data.total).toLocaleString('vi-VN')+' ký ức · Chọn một mục để xem đầy đủ.':'Đã đọc dữ liệu mới nhất.');
    }catch(error){
      if(error.name!=='AbortError'&&controller===request){loaded=false;feedback(error.message,true);$('memory-list').replaceChildren();$('memory-empty').hidden=true;$('memory-pager').hidden=true;for(const key of ['total','active','expired'])$('memory-'+key).textContent='—';}
    }finally{if(controller===request){panel.setAttribute('aria-busy','false');request=null;}}
  }
  for(const button of document.querySelectorAll('[data-memory-kind]'))button.addEventListener('click',()=>{
    kind=button.dataset.memoryKind;for(const item of document.querySelectorAll('[data-memory-kind]'))item.setAttribute('aria-pressed',String(item===button));refresh(true);
  });
  $('memory-state').addEventListener('change',()=>refresh(true));
  $('memory-search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>refresh(true),300);});
  $('memory-search').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();refresh(true);}});
  $('memory-prev').addEventListener('click',()=>{if(page>1){page--;refresh();}});
  $('memory-next').addEventListener('click',()=>{if(page<pages){page++;refresh();}});
  $('memory-detail-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{detailRequest?.abort();detailRequest=null;});
  return {open(){if(!loaded)refresh();},refresh(){return refresh();}};
}
