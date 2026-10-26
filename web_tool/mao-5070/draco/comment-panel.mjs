import {createReplyPopup} from './reply-popup.mjs?v=1';
const STYLE=`
.mao-comment-layer{position:absolute;inset:0 auto auto 0;width:100%;height:100%;pointer-events:none;z-index:4;container-type:size}
.mao-comments{position:absolute;left:clamp(22px,3.4cqw,76px);top:24%;width:clamp(220px,28cqw,340px);max-width:calc(50% - 110px);font-family:'Segoe UI',sans-serif;color:#f7f3e9;isolation:isolate}
.mao-comments__glass{display:flex;flex-direction:column;max-height:calc(76cqh - 20px)}
.mao-comments__header{display:flex;align-items:center;gap:11px;padding:0 5px 16px;text-shadow:0 2px 12px #0008}
.mao-comments__crest{display:grid;place-items:center;flex:none;width:36px;height:36px;border:1px solid #ead7ad70;border-radius:50%;color:#f3dfb6;font:23px Georgia,serif;background:#221d175c;box-shadow:0 3px 14px #0002}
.mao-comments__title{margin:0;color:#fff8e9;font:italic 30px/1.05 Georgia,'Times New Roman',serif;letter-spacing:-1.3px}
.mao-comments__eyebrow{display:block;margin-top:6px;font-size:10px;letter-spacing:.02em;color:#e5d5b8}
.mao-comments__signal{margin-left:auto;align-self:center;display:flex;align-items:center;gap:5px;color:#d8e9d7;font-size:9px}
.mao-comments__signal::before{content:'';width:5px;height:5px;border-radius:50%;background:#b4d8bb;box-shadow:0 0 8px #b4d8bb66}
.mao-comments[data-online="false"] .mao-comments__signal{opacity:.45}
.mao-comments[data-online="false"] .mao-comments__signal::before{background:#d1bc96;box-shadow:none}
.mao-comments__list{position:relative;list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:10px;min-height:0;max-height:340px;overflow:hidden}
.mao-comment{position:relative;flex-shrink:0;padding:14px 15px 15px;border:1px solid #fff5e84a;border-radius:18px 18px 18px 5px;background:linear-gradient(135deg,#fffaf0f5,#f3ecdded);color:#353b34;box-shadow:0 7px 22px #0002;animation:mao-comment-in .32s ease-out}
.mao-comment:first-child{background:linear-gradient(130deg,#fbfff6f7,#e7efdfef);border-color:#eef6dd8c}
.mao-comment:nth-child(2){margin-left:10px}
.mao-comment:nth-child(3){margin-left:18px}
.mao-comment__meta{display:flex;align-items:center;gap:8px;margin-bottom:8px;min-width:0}
.mao-comment__avatar{display:grid;place-items:center;width:25px;height:25px;flex:none;border-radius:50%;background:#d8e1cc;color:#45614d;font:600 11px 'Segoe UI',sans-serif}
.mao-comment__name{color:#48604b;font-size:12px;font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mao-comment__text{margin:0;color:#333c34;font-size:clamp(12px,1.4cqw,16px);line-height:1.6;overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.mao-comment[data-command="true"]{background:linear-gradient(130deg,#fff9ebf7,#efe1c6f0)}
.mao-comment__command{display:block;margin-bottom:6px;color:#8a6a3f;font-size:9px;font-weight:600}
.mao-comments__empty{margin:0;padding:19px 18px 20px;border:1px solid #f1e0bd3d;border-radius:18px 18px 18px 5px;background:#211e198f;backdrop-filter:blur(14px);color:#f0e4d1;font-size:13px;line-height:1.8;white-space:pre-line;box-shadow:0 8px 25px #0002}
.mao-comments__footer{display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:12px 3px 0;color:#e8dbc2;text-shadow:0 1px 5px #0009}
.mao-comments__command{padding:5px 9px;border:1px solid #edddb729;border-radius:99px;background:#211e1959;font-size:9px;white-space:nowrap}
.mao-comments__status{width:100%;margin:2px 5px 0;color:#d8cbb5;font-size:9px;line-height:1.5}
.mao-comments__status:empty{display:none}
body[data-mode="pet"] .mao-comment-layer{display:none}
body[data-mao-game="playing"] .mao-comments,body[data-mao-game="waiting"] .mao-comments,body[data-mao-game="finished"] .mao-comments{top:auto;bottom:12px;width:clamp(260px,35cqw,430px);max-width:52%}
body[data-mao-game="playing"] .mao-comments__header,body[data-mao-game="waiting"] .mao-comments__header,body[data-mao-game="finished"] .mao-comments__header{padding-bottom:8px;gap:8px}
body[data-mao-game="playing"] .mao-comments__crest,body[data-mao-game="waiting"] .mao-comments__crest,body[data-mao-game="finished"] .mao-comments__crest{width:24px;height:24px;font-size:16px}
body[data-mao-game="playing"] .mao-comments__title,body[data-mao-game="waiting"] .mao-comments__title,body[data-mao-game="finished"] .mao-comments__title{font-size:22px}
body[data-mao-game="playing"] .mao-comments__eyebrow,body[data-mao-game="waiting"] .mao-comments__eyebrow,body[data-mao-game="finished"] .mao-comments__eyebrow,body[data-mao-game="playing"] .mao-comments__footer,body[data-mao-game="waiting"] .mao-comments__footer,body[data-mao-game="finished"] .mao-comments__footer{display:none}
body[data-mao-game="playing"] .mao-comment:not(:first-child),body[data-mao-game="waiting"] .mao-comment:not(:first-child),body[data-mao-game="finished"] .mao-comment:not(:first-child){display:none}
body[data-mao-game="playing"] .mao-comment,body[data-mao-game="waiting"] .mao-comment,body[data-mao-game="finished"] .mao-comment{padding:10px 12px}
@container(max-width:620px){.mao-comments{left:14px;width:190px;max-width:calc(50% - 65px)}.mao-comments__header{gap:8px;padding-bottom:10px}.mao-comments__title{font-size:24px}.mao-comments__eyebrow{font-size:9px}.mao-comments__crest{width:28px;height:28px;font-size:18px}.mao-comments__signal{display:none}.mao-comment{padding:10px 12px}.mao-comment:nth-child(n+3){display:none}.mao-comments__footer{gap:5px;padding-top:9px}.mao-comments__command{font-size:8px;padding:4px 7px}}
@container(max-width:420px){.mao-comments{display:none}}
@media(prefers-reduced-motion:reduce){.mao-comment{animation:none}}
@keyframes mao-comment-in{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:none}}
`;

export function mergeCommentFeed(previous,payload){
  if(!payload||typeof payload.session!=='string'||!Number.isInteger(payload.revision)||payload.revision<0||!Array.isArray(payload.comments))return previous;
  if(payload.session===previous.session&&payload.revision<previous.revision)return previous;
  const map=new Map((previous.session===payload.session?previous.comments:[]).map(item=>[item.id,item]));
  for(const item of payload.comments){
    if(!item||!Number.isInteger(item.id)||item.id<1||item.id>payload.revision||typeof item.text!=='string'||!item.text.trim())continue;
    const nickname=item.platform==='desktop'&&item.nickname==='Bạn trên desktop'?'anh Bi':item.nickname;
    map.set(item.id,{id:item.id,text:item.text.slice(0,300),nickname:String(nickname||'Bạn').slice(0,40),platform:['youtube','tiktok','desktop'].includes(item.platform)?item.platform:'desktop'});
  }
  return {session:payload.session,revision:payload.revision,comments:[...map.values()].sort((a,b)=>b.id-a.id).slice(0,20)};
}

function node(tag,className,text){const value=document.createElement(tag);if(className)value.className=className;if(text!==undefined)value.textContent=text;return value;}
export function mountCommentPanel(container,{getMode=()=> 'window',eventTarget=globalThis.window}={}){
  const style=node('style');style.textContent=STYLE+'\n.mao-comments[hidden]{display:none!important}';
  const layer=node('div','mao-comment-layer'),panel=node('aside','mao-comments');panel.hidden=true;panel.setAttribute('aria-label','Bình luận Mao đang trả lời');
  const glass=node('div','mao-comments__glass'),header=node('header','mao-comments__header'),title=node('div');
  title.append(node('h2','mao-comments__title','MaoLink'),node('span','mao-comments__eyebrow','Đang trả lời bình luận'));
  header.append(node('span','mao-comments__crest','✦'),title);
  const list=node('ol','mao-comments__list');list.setAttribute('aria-live','polite');
  glass.append(header,list);panel.append(glass);layer.append(style,panel);container.append(layer);
  const card=item=>{
    const row=node('li','mao-comment');
    const meta=node('div','mao-comment__meta');meta.append(node('span','mao-comment__avatar',[...item.nickname][0]?.toUpperCase()||'?'),node('span','mao-comment__name',item.nickname));
    row.append(meta,node('p','mao-comment__text',item.text));return row;
  };
  const render=(comments,visible)=>{
    panel.hidden=!visible||getMode()!=='window';
    if(panel.hidden){list.replaceChildren();return;}
    list.replaceChildren(...comments.slice(0,3).map(card));
  };
  const popup=createReplyPopup({onChange:render});
  const message=event=>{
    const data=event.detail;
    if(data?.type==='user-input-transcription')popup.input(data);
    if(data?.type==='reply-disconnected'||data?.type==='interrupt-signal'||data?.type==='control'&&['conversation-chain-end','interrupt-signal'].includes(data.text)){
      if(data.type==='control'&&data.text==='conversation-chain-end')popup.end();else popup.reset();
    }
  };
  const playing=()=>popup.playing();
  eventTarget?.addEventListener('mao-reply-event',message);
  eventTarget?.addEventListener('mao-reply-playback',playing);
  return {element:panel,render(payload){render(payload?.comments||[],payload?.active===true);},setViewport(width,height){layer.style.width=`${width}px`;layer.style.height=`${height}px`;},dispose(){eventTarget?.removeEventListener('mao-reply-event',message);eventTarget?.removeEventListener('mao-reply-playback',playing);popup.dispose();layer.remove();}};
}
