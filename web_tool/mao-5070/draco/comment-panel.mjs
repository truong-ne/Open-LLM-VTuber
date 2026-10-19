import {cooldownSeconds} from './game-status.mjs';
import {songCooldown} from './singing-player.mjs';
const STYLE=`
.mao-comment-layer{position:absolute;inset:0 auto auto 0;width:100%;height:100%;pointer-events:none;z-index:4;container-type:size}
.mao-comments{position:absolute;left:clamp(18px,3.2cqw,76px);top:25%;width:clamp(210px,25cqw,360px);max-width:calc(50% - 105px);color:#e6efe6;font-family:'Segoe UI',sans-serif;isolation:isolate;filter:drop-shadow(0 15px 30px #0005)}
.mao-comments::before{content:'';position:absolute;inset:-7px;border:1px solid #a8d5c438;clip-path:polygon(0 19px,19px 0,calc(100% - 19px) 0,100% 19px,100% calc(100% - 19px),calc(100% - 19px) 100%,19px 100%,0 calc(100% - 19px));background:linear-gradient(125deg,#bed8ce18,transparent 30%,#8bdbc110);z-index:-1}
.mao-comments__glass{position:relative;overflow:hidden;display:flex;flex-direction:column;max-height:min(510px,calc(75cqh - 24px));border:1px solid #9cd5c36b;border-radius:3px 23px 3px 23px;background:linear-gradient(130deg,#173c34ed,#0b201eea 58%,#15352ff0);box-shadow:inset 0 1px #e5f4e82b,inset 0 0 28px #6ccab30d;backdrop-filter:blur(16px)}
.mao-comments__glass::before{content:'';position:absolute;inset:0;pointer-events:none;background:linear-gradient(#98d3c206 1px,transparent 1px),linear-gradient(90deg,#98d3c206 1px,transparent 1px);background-size:24px 24px;mask-image:linear-gradient(#000,transparent 80%)}
.mao-comments__header{position:relative;display:flex;flex-shrink:0;align-items:center;gap:10px;padding:16px 17px 13px;border-bottom:1px solid #c9ddc928}
.mao-comments__crest{display:grid;place-items:center;width:31px;height:36px;flex:none;clip-path:polygon(50% 0,100% 19%,100% 74%,50% 100%,0 74%,0 19%);background:linear-gradient(145deg,#e3ebdc,#9fc8b8);color:#153e32;font:700 21px Georgia,serif}
.mao-comments__title{margin:0;font:600 19px Georgia,'Times New Roman',serif;letter-spacing:.1em;color:#eef0d9}
.mao-comments__eyebrow{display:block;margin-top:4px;font:9px ui-monospace,Consolas,monospace;letter-spacing:.16em;text-transform:uppercase;color:#98c5b3}
.mao-comments__signal{margin-left:auto;width:21px;height:13px;display:flex;gap:3px;align-items:end}.mao-comments__signal i{width:3px;background:#8ce5c6;box-shadow:0 0 8px #80dfc76b}.mao-comments__signal i:nth-child(1){height:4px}.mao-comments__signal i:nth-child(2){height:8px}.mao-comments__signal i:nth-child(3){height:12px}
.mao-comments[data-online="false"] .mao-comments__signal i{background:#889c92;box-shadow:none}
.mao-comments__list{position:relative;list-style:none;padding:11px;margin:0;display:flex;flex-direction:column;gap:8px;min-height:0;max-height:340px;overflow:hidden}
.mao-comment{position:relative;flex-shrink:0;padding:11px 12px;border:1px solid #c1dfcd22;border-left:2px solid #96cdb35e;border-radius:2px 12px 2px 12px;background:linear-gradient(110deg,#c4eadc0b,#9fceb605);animation:mao-comment-in .25s ease-out}
.mao-comment:first-child{border-left-color:#aff0cf;background:linear-gradient(110deg,#a4e5bf1e,#76cba90a)}
.mao-comment__meta{display:flex;align-items:center;gap:7px;margin-bottom:6px;min-width:0;font-size:11px}
.mao-comment__avatar{display:grid;place-items:center;width:22px;height:22px;flex:none;border:1px solid #c6dfc83b;border-radius:8px 8px 8px 2px;background:#7aaf9b22;color:#dce5c8;font-size:10px;font-weight:700}
.mao-comment__name{color:#cce3cc;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mao-comment__platform{margin-left:auto;color:#9cb5a8;font:8px ui-monospace,Consolas,monospace;letter-spacing:.08em}
.mao-comment__text{margin:0;color:#f0f0e0;font-size:clamp(12px,1.25cqw,16px);line-height:1.45;overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}
.mao-comment[data-command="true"]{border-color:#a7dbc561;background:linear-gradient(110deg,#5cbf941e,#b6d8b90e)}
.mao-comment[data-command="true"] .mao-comment__text{color:#bff1cc;font-family:ui-monospace,Consolas,monospace;font-weight:650;letter-spacing:-.02em}
.mao-comment__command{display:block;margin-bottom:6px;color:#94c9b1;font:8px ui-monospace,Consolas,monospace;letter-spacing:.14em;text-transform:uppercase}
.mao-comments__empty{margin:0;padding:20px 18px;color:#b3c8bb;font-size:12px;line-height:1.7}
.mao-comments__footer{position:relative;display:flex;flex-shrink:0;align-items:center;justify-content:space-between;gap:8px;padding:10px 15px 12px;border-top:1px solid #b6d7bd24;font-size:10px;color:#a5bdb0}
.mao-comments__command{border:1px solid #bedfc647;border-radius:4px;background:#90cda00d;padding:5px 7px;color:#d0edce;font:10px ui-monospace,Consolas,monospace}
.mao-comments__status{letter-spacing:.06em;text-transform:uppercase;font-size:8px}
body[data-mode="pet"] .mao-comment-layer{display:none}
body[data-mao-game="playing"] .mao-comments,body[data-mao-game="waiting"] .mao-comments,body[data-mao-game="finished"] .mao-comments{top:auto;bottom:12px;width:clamp(260px,35cqw,430px);max-width:52%}
body[data-mao-game="playing"] .mao-comments__header,body[data-mao-game="waiting"] .mao-comments__header,body[data-mao-game="finished"] .mao-comments__header{padding:8px 12px;gap:8px}
body[data-mao-game="playing"] .mao-comments__crest,body[data-mao-game="waiting"] .mao-comments__crest,body[data-mao-game="finished"] .mao-comments__crest{width:18px;height:22px;font-size:13px}
body[data-mao-game="playing"] .mao-comments__title,body[data-mao-game="waiting"] .mao-comments__title,body[data-mao-game="finished"] .mao-comments__title{font-size:12px}
body[data-mao-game="playing"] .mao-comments__eyebrow,body[data-mao-game="waiting"] .mao-comments__eyebrow,body[data-mao-game="finished"] .mao-comments__eyebrow,body[data-mao-game="playing"] .mao-comments__footer,body[data-mao-game="waiting"] .mao-comments__footer,body[data-mao-game="finished"] .mao-comments__footer{display:none}
body[data-mao-game="playing"] .mao-comments__list,body[data-mao-game="waiting"] .mao-comments__list,body[data-mao-game="finished"] .mao-comments__list{padding:6px}
body[data-mao-game="playing"] .mao-comment:not(:first-child),body[data-mao-game="waiting"] .mao-comment:not(:first-child),body[data-mao-game="finished"] .mao-comment:not(:first-child){display:none}
body[data-mao-game="playing"] .mao-comment,body[data-mao-game="waiting"] .mao-comment,body[data-mao-game="finished"] .mao-comment{padding:7px 10px}
body[data-mao-game="playing"] .mao-comment__meta,body[data-mao-game="waiting"] .mao-comment__meta,body[data-mao-game="finished"] .mao-comment__meta{margin-bottom:3px}
@container(max-width:620px){.mao-comments{left:12px;width:190px;max-width:calc(50% - 65px)}.mao-comments__header{padding:10px}.mao-comments__title{font-size:13px}.mao-comments__eyebrow{font-size:7px}.mao-comments__crest{width:23px;height:28px}.mao-comments__list{padding:6px}.mao-comment{padding:8px}.mao-comment:nth-child(n+3){display:none}.mao-comments__footer{padding:8px;flex-wrap:wrap}.mao-comment__platform{display:none}}
@container(max-width:420px){.mao-comments{display:none}}
@media(prefers-reduced-motion:reduce){.mao-comment{animation:none}}
@keyframes mao-comment-in{from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:none}}
`;

export function mergeCommentFeed(previous,payload){
  if(!payload||typeof payload.session!=='string'||!Number.isInteger(payload.revision)||payload.revision<0||!Array.isArray(payload.comments))return previous;
  if(payload.session===previous.session&&payload.revision<previous.revision)return previous;
  const map=new Map((previous.session===payload.session?previous.comments:[]).map(item=>[item.id,item]));
  for(const item of payload.comments){
    if(!item||!Number.isInteger(item.id)||item.id<1||item.id>payload.revision||typeof item.text!=='string'||!item.text.trim())continue;
    map.set(item.id,{id:item.id,text:item.text.slice(0,300),nickname:String(item.nickname||'Bạn').slice(0,40),platform:['youtube','tiktok','desktop'].includes(item.platform)?item.platform:'desktop'});
  }
  return {session:payload.session,revision:payload.revision,comments:[...map.values()].sort((a,b)=>b.id-a.id).slice(0,20)};
}

function node(tag,className,text){const value=document.createElement(tag);if(className)value.className=className;if(text!==undefined)value.textContent=text;return value;}
export function mountCommentPanel(container,{baseUrl='http://127.0.0.1:12393',fetcher=fetch,getMode=()=> 'window'}={}){
  const style=node('style');style.textContent=STYLE;
  const layer=node('div','mao-comment-layer'),panel=node('aside','mao-comments');panel.setAttribute('aria-label','Bình luận gửi Mao');panel.dataset.online='false';
  const glass=node('div','mao-comments__glass'),header=node('header','mao-comments__header'),title=node('div');
  title.append(node('h2','mao-comments__title','MAO LINK'),node('span','mao-comments__eyebrow','Kết nối cùng Mao'));
  const signal=node('span','mao-comments__signal');signal.setAttribute('aria-hidden','true');for(let i=0;i<3;i++)signal.append(node('i'));
  header.append(node('span','mao-comments__crest','M'),title,signal);
  const list=node('ol','mao-comments__list');list.setAttribute('aria-live','polite');list.setAttribute('aria-relevant','additions');
  const empty=node('p','mao-comments__empty','Chưa có bình luận mới.\nGửi một lời nhắn, Mao sẽ thấy ở đây.');
  const footer=node('footer','mao-comments__footer'),status=node('span','mao-comments__status','Đang kết nối');
  footer.append(node('span','mao-comments__command','!vuatiengviet · !songs'),status);
  glass.append(header,empty,list,footer);panel.append(glass);layer.append(style,panel);container.append(layer);
  let state={session:'',revision:0,comments:[]},disposed=false,timer,controller,online=false;
  function updateStatus(){
    const game=globalThis.window?.maoWordGame,seconds=cooldownSeconds(game?.state,Date.now(),game?.clockOffset||0);
    const singer=globalThis.window?.maoSinging,singCD=songCooldown(singer?.state,Date.now(),singer?.clockOffset||0);
    const label=['waiting','loading','playing'].includes(singer?.state?.phase)?'Tiết mục của Mao':seconds>0?`Vòng mới sau ${seconds}s`:singCD>0?`Bài mới sau ${singCD}s`:online?'Đã kết nối':'Đang kết nối';
    if(status.textContent!==label)status.textContent=label;
    panel.dataset.cooldown=String(seconds>0);
  }
  const card=item=>{
    const row=node('li','mao-comment');row.dataset.id=String(item.id);row.dataset.command=String(/^!(?:vuatiengviet|sing|songs|baihat)(?:\s|$)/i.test(item.text.trim()));
    const meta=node('div','mao-comment__meta');meta.append(node('span','mao-comment__avatar',[...item.nickname][0]?.toUpperCase()||'?'),node('span','mao-comment__name',item.nickname),node('span','mao-comment__platform',item.platform==='desktop'?'DESKTOP':item.platform.toUpperCase()));row.append(meta);
    if(row.dataset.command==='true')row.append(node('span','mao-comment__command',/^!vuatiengviet\s*$/i.test(item.text.trim())?'Lời mời chơi từ khán giả':'Lời mời hát từ khán giả'));
    row.append(node('p','mao-comment__text',item.text));return row;
  };
  function render(payload){
    const next=mergeCommentFeed(state,payload),changed=next.session!==state.session||next.revision!==state.revision;state=next;
    if(changed){
      const existing=new Map([...list.children].map(row=>[Number(row.dataset.id),row]));
      if(next.session!==list.dataset.session)existing.clear();
      list.replaceChildren(...state.comments.slice(0,4).map(item=>existing.get(item.id)||card(item)));list.dataset.session=next.session;
    }
    empty.hidden=state.comments.length>0;list.hidden=!state.comments.length;
  }
  async function poll(){
    if(disposed)return;
    let connected=false;
    try{
      if(document.visibilityState==='hidden'||getMode()!=='window')return;
      controller=new AbortController();const abort=setTimeout(()=>controller.abort(),2500);
      try{const response=await fetcher(`${baseUrl}/api/comments?after=${state.revision}&session=${encodeURIComponent(state.session)}`,{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error('offline');const payload=await response.json();if(disposed)return;render(payload);connected=true;}finally{clearTimeout(abort);}
    }catch{}finally{
      if(!disposed){online=connected;panel.dataset.online=String(online);updateStatus();timer=setTimeout(poll,online?700:2500);}
    }
  }
  poll();
  const statusTicker=setInterval(updateStatus,250);
  return {element:panel,render,setViewport(width,height){layer.style.width=`${width}px`;layer.style.height=`${height}px`;},dispose(){disposed=true;clearTimeout(timer);clearInterval(statusTicker);controller?.abort();layer.remove();}};
}
