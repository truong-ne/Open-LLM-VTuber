// Only the reply being spoken is displayable. Incoming/queued chat never opens it.
export function replyComments(message){
  if(message?.type!=='user-input-transcription'||typeof message.text!=='string')return [];
  if(['youtube-live','tiktok-live'].includes(message.source)){
    if(message.text.length>64000)return [];
    let data;
    try{const index=message.text.lastIndexOf('\n{');if(index<0)return [];data=JSON.parse(message.text.slice(index+1));}catch{return [];}
    if(!Array.isArray(data.comment_groups))return [];
    return data.comment_groups.slice(0,3).filter(row=>typeof row?.comment==='string'&&row.comment.trim()).map((row,index)=>({
      id:index+1,text:row.comment.slice(0,300),nickname:(Array.isArray(row.nicknames)?row.nicknames.filter(name=>typeof name==='string').slice(0,2).join(', '):'')||'Khán giả',platform:message.source==='youtube-live'?'youtube':'tiktok',
    }));
  }
  if(!message.source||message.source==='desktop')return message.text.trim()?[{id:1,text:message.text.slice(0,300),nickname:'papa',platform:'desktop'}]:[];
  return [];
}

export function createReplyPopup({onChange,hideDelay=1200,setTimer=setTimeout,clearTimer=clearTimeout}={}){
  let pending=[],shown=[],visible=false,finished=true,hideTimer,watchdog,lastBatch='';
  const clear=()=>{clearTimer(hideTimer);clearTimer(watchdog);hideTimer=watchdog=undefined;};
  function reset(){clear();pending=[];shown=[];visible=false;finished=true;onChange?.([],false);}
  function input(message){
    const batch=message.batch_id?String(message.source)+'/'+String(message.batch_id):'';
    if(batch&&batch===lastBatch)return;
    reset();lastBatch=batch;pending=replyComments(message);finished=!pending.length;
  }
  function playing(){
    if(finished||!pending.length)return;
    clearTimer(watchdog);watchdog=setTimer(reset,120000);
    if(!visible){shown=pending;visible=true;onChange?.(shown,true);}
  }
  function end(){
    finished=true;pending=[];clear();
    if(visible)hideTimer=setTimer(reset,hideDelay);else reset();
  }
  return {input,playing,end,reset,dispose:reset};
}
