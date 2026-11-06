import {mountGiftPanel} from './gift-panel.mjs';
import {createReplyPopup} from './reply-popup.mjs?v=2';
const STYLE=`
.mao-comment-layer{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:4;container-type:size}
.mao-comments{position:absolute;left:clamp(14px,2.4cqw,42px);bottom:clamp(110px,16cqh,180px);width:clamp(260px,30cqw,360px);max-width:calc(100% - 28px);box-sizing:border-box;font-family:'Segoe UI',sans-serif;isolation:isolate}
.mao-comments__glass{display:flex;flex-direction:column;gap:12px;max-height:65cqh}
.mao-comments__header{display:flex;align-items:center;gap:10px;padding:0 6px;color:#fff9eb;text-shadow:0 2px 14px #132b21aa}
.mao-comments__crest{display:grid;place-items:center;flex:none;width:34px;height:34px;border:1px solid #f9f1da66;border-radius:12px;color:#f6e7be;font-size:22px;background:#486449b3;box-shadow:0 4px 16px #0002}
.mao-comments__title{margin:0;color:#fff9ec;font:600 21px/1.2 'Segoe UI',sans-serif;letter-spacing:-.5px}
.mao-comments__eyebrow{display:flex;align-items:center;gap:6px;margin-top:5px;font-size:10px;color:#f1ead8}.mao-comments__eyebrow::before{content:'';width:5px;height:5px;border-radius:50%;background:#c4e59e;box-shadow:0 0 8px #b8e79077}
.mao-comments__list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:9px;min-height:0;max-height:330px;overflow:hidden}
.mao-comment{position:relative;flex-shrink:0;box-sizing:border-box;padding:17px 18px 18px;border:1px solid #fff8e4a6;border-radius:22px;background:linear-gradient(140deg,#fffdf3f5,#f0f1e5f0);color:#35483c;box-shadow:0 12px 32px #10241930,inset 0 1px #fff;backdrop-filter:blur(16px);animation:mao-comment-in .28s ease-out}
.mao-comment:first-child{border-left:3px solid #9eaf7d}.mao-comment:nth-child(n+2){margin-left:10px;opacity:.94}
.mao-comment__meta{display:flex;align-items:center;gap:9px;margin-bottom:10px;min-width:0}.mao-comment__avatar{display:grid;place-items:center;width:30px;height:30px;flex:none;border-radius:11px;background:linear-gradient(145deg,#dee9cd,#cddcbd);color:#5a7549;font-size:13px;font-weight:700;box-shadow:inset 0 0 0 1px #9fb48633}.mao-comment__name{color:#61754f;font-size:12px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mao-comment__text{margin:0;color:#35483c;font-size:clamp(13px,1.4cqw,16px);line-height:1.65;overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
body[data-mode="pet"] .mao-comment-layer{display:none}
body[data-mao-game="playing"] .mao-comments,body[data-mao-game="waiting"] .mao-comments,body[data-mao-game="finished"] .mao-comments{bottom:12px;width:clamp(260px,35cqw,430px);max-width:52%}
body[data-mao-game="playing"] .mao-comment:not(:first-child),body[data-mao-game="waiting"] .mao-comment:not(:first-child),body[data-mao-game="finished"] .mao-comment:not(:first-child){display:none}
@container(max-width:620px){.mao-comments{left:14px;bottom:110px;width:min(70cqw,330px);max-width:calc(100% - 28px)}.mao-comments__title{font-size:19px}.mao-comments__glass{gap:9px}.mao-comments__crest{width:29px;height:29px;font-size:19px;border-radius:10px}.mao-comment{padding:13px 15px;border-radius:19px}.mao-comment__meta{margin-bottom:7px}.mao-comment__text{font-size:14px;line-height:1.5}.mao-comment:nth-child(n+3){display:none}}
@container(max-width:420px){.mao-comments{left:12px;width:calc(100% - 24px);bottom:102px}.mao-comments__title{font-size:18px}.mao-comment:nth-child(n+2){display:none}}
@media(prefers-reduced-motion:reduce){.mao-comment{animation:none}}
@keyframes mao-comment-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
`;

export function mergeCommentFeed(previous,payload){
  if(!payload||typeof payload.session!=='string'||!Number.isInteger(payload.revision)||payload.revision<0||!Array.isArray(payload.comments))return previous;
  if(payload.session===previous.session&&payload.revision<previous.revision)return previous;
  const map=new Map((previous.session===payload.session?previous.comments:[]).map(item=>[item.id,item]));
  for(const item of payload.comments){
    if(!item||!Number.isInteger(item.id)||item.id<1||item.id>payload.revision||typeof item.text!=='string'||!item.text.trim())continue;
    const nickname=item.platform==='desktop'&&item.nickname==='Bạn trên desktop'?'papa':item.nickname;
    map.set(item.id,{id:item.id,text:item.text.slice(0,300),nickname:String(nickname||'Bạn').slice(0,40),platform:['youtube','tiktok','desktop'].includes(item.platform)?item.platform:'desktop'});
  }
  return {session:payload.session,revision:payload.revision,comments:[...map.values()].sort((a,b)=>b.id-a.id).slice(0,20)};
}

function node(tag,className,text){const value=document.createElement(tag);if(className)value.className=className;if(text!==undefined)value.textContent=text;return value;}
export function mountCommentPanel(container,{getMode=()=> 'window',eventTarget=globalThis.window,fetcher=fetch}={}){
  const style=node('style');style.textContent=STYLE+'\n.mao-comments[hidden]{display:none!important}';
  const layer=node('div','mao-comment-layer'),panel=node('aside','mao-comments');panel.hidden=true;panel.setAttribute('aria-label','Bình luận Mao đang trả lời');
  const glass=node('div','mao-comments__glass'),header=node('header','mao-comments__header'),title=node('div');
  title.append(node('h2','mao-comments__title','Chuyện cùng Mao'),node('span','mao-comments__eyebrow','Mao đang lắng nghe bạn'));
  header.append(node('span','mao-comments__crest','✦'),title);
  const list=node('ol','mao-comments__list');list.setAttribute('aria-live','polite');
  glass.append(header,list);panel.append(glass);layer.append(style,panel);container.append(layer);
  const gifts=mountGiftPanel(layer,{getMode,fetcher});
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
  return {element:panel,reset(){popup.reset();},render(payload){render(payload?.comments||[],payload?.active===true);},setViewport(width,height){layer.style.width=`${width}px`;layer.style.height=`${height}px`;},dispose(){eventTarget?.removeEventListener('mao-reply-event',message);eventTarget?.removeEventListener('mao-reply-playback',playing);popup.dispose();gifts.dispose();layer.remove();}};
}
