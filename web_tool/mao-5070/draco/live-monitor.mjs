const REASONS={queue_overflow:'Hàng chờ đã đầy',game_queue_overflow:'Hàng chờ trò chơi đã đầy',proxy_retry_overflow:'Hàng chờ đã đầy khi thử lại',queue_overflow_on_retry:'Hàng chờ đã đầy khi thử lại',recent_duplicate:'Trùng bình luận vừa trả lời',historical_or_duplicate_event:'Bình luận cũ hoặc sự kiện gửi lại',blocked_word:'Có từ đang được chặn',empty_comment:'Không có nội dung',proxy_send_failed:'Gửi chưa thành công; đang chờ thử lại',retry_after_rejected_busy:'Đưa lại hàng chờ vì Mao đang bận',expired_before_restart:'Đã quá hạn trước khi khởi động lại',recovery_queue_full:'Hàng chờ phục hồi đã đầy','No confirmed desktop playback':'Chưa có xác nhận phát từ desktop','Backend already received this input before reconnect':'Đã gửi trước khi mất kết nối; chưa xác định kết quả phát'};
const LABELS={received:'Đã nhận',accepted:'Đã tiếp nhận lượt',routed_game:'Chuyển tới lớp / bài hát',delivery_unknown:'Chưa xác định phát sau kết nối lại',queued:'Đang chờ',answering:'Đang tạo câu trả lời',audio_generated:'Đã tạo giọng',playing:'Đang phát',delivered:'Đã phát',answered:'Đã kết thúc',playback_unconfirmed:'Chưa xác nhận phát',no_audio:'Không có giọng',playback_failed:'Lỗi phát',skipped:'Bỏ qua',completed:'Đã xử lý'};
export function mountLiveMonitor(container,{fetcher=fetch,baseUrl='http://127.0.0.1:12393'}={}){
  const root=document.createElement('details');root.className='mao-live-monitor';
  const title=document.createElement('summary');title.textContent='Theo dõi LIVE · Hàng chờ và bình luận';
  const status=document.createElement('p'),queue=document.createElement('p'),list=document.createElement('ol'),note=document.createElement('p');
  note.textContent='Chỉ hiển thị cho người vận hành. Không xác nhận được bình luận TikTok chưa chuyển tới bộ đọc.';
  root.append(title,status,queue,list,note);container.append(root);
  let timer,disposed=false;
  function render(data){
    const r=data.reader||{},q=data.queue||{},d=data.desktop||{};
    const names={offline:'LIVE đã kết thúc / đang offline',connected:'Đã kết nối TikTok',stale:'Chưa có trạng thái kết nối mới',reconnecting:'Đang kết nối lại TikTok'};
    status.textContent=`${names[data.connection]||'Đang kiểm tra'} · Nhận mới: ${r.fresh_comments||0} · Lỗi phát: ${d.audioErrors||0} · Ký ức chọn lọc: ${data.memory?.preferences||0}`;
    queue.textContent=`Chờ: ${q.queued_comments||0} · Trong lượt: ${q.inflight_comments||0} · Mao: ${q.conversation_active?'đang nói / đang xử lý':'đang nghe'}${q.waiting_for_reply&&data.server_now-q.last_progress_at>90?' · Cần kiểm tra: lượt trả lời chậm hơn 90 giây':''}${q.next_comments?.length?' · Tiếp theo: '+q.next_comments[0].nickname+': '+q.next_comments[0].text:''}`;
    list.replaceChildren();
    for(const item of data.comments||[]){const li=document.createElement('li'),head=document.createElement('b'),text=document.createElement('p'),detail=document.createElement('small');head.textContent=`${item.nickname} · ${LABELS[item.state]||item.state}`;text.textContent=item.text;detail.textContent=[new Date(item.received_at*1000).toLocaleTimeString('vi-VN'),(REASONS[item.reason]||item.reason),(item.transitions||[]).map(t=>LABELS[t.state]||t.state).join(' → ')].filter(Boolean).join(' · ');li.append(head,text,detail);list.append(li);}
  }
  async function refresh(){
    if(disposed||!root.open||container.hidden)return;
    try{const response=await fetcher(`${baseUrl}/api/live/diagnostics`,{cache:'no-store',signal:AbortSignal.timeout(3500)});if(!response.ok)throw Error();render(await response.json());}catch{status.textContent='Chưa đọc được trạng thái LIVE. Đang thử lại…';}
  }
  root.ontoggle=refresh;timer=setInterval(refresh,1500);
  return {element:root,render,dispose(){disposed=true;clearInterval(timer);root.remove();}};
}
