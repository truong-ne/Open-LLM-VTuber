import {drawTvScreen,remainingSeconds,screenPhase,tvArtRevision,SCREEN_WIDTH,SCREEN_HEIGHT} from './tv-screen.mjs?v=4';
import {cooldownSeconds} from './game-status.mjs';
export {remainingSeconds};
const STYLE=`
.vtv-root{position:fixed;z-index:1500;left:50%;top:24px;transform:translateX(-50%);width:min(1000px,calc(100vw - 40px));pointer-events:none;font-family:system-ui;color:#eafbff}
.vtv-tv{display:block;width:100%;aspect-ratio:16/9;border:9px solid #173d32;border-radius:22px;box-shadow:0 0 0 1px #b3c1b7,0 18px 60px #102b2738;background:#f3eedf}
.vtv-accessible{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
body[data-mode="window"] .vtv-root{display:none}
body[data-mode="pet"] .vtv-root[data-phase="idle"]{display:none}
body[data-mode="window"]{background:#07111e}
body[data-mode="window"] #mao-legacy-status{display:none}
body[data-mode="window"] #mao-window-footer{background:linear-gradient(100deg,#102137ed,#0c1625ed)!important;border-top:1px solid #4f8b9a38;border-radius:24px 24px 0 0;box-shadow:0 -14px 50px #0002}
body[data-mode="window"] #mao-window-footer textarea,body[data-mode="window"] #mao-window-footer input{background:#0c1c2d!important;border:1px solid #345166!important;color:#e6f7ff!important;border-radius:16px!important}
body[data-mode="window"] #mao-window-subtitle{width:calc(100% - 64px)!important;max-width:980px;pointer-events:auto}
body[data-mode="window"] #mao-window-subtitle>div{background:#0a1d2de8!important;border:1px solid #36566b88;padding:9px 18px!important;border-radius:13px!important;max-width:100%!important;max-height:min(32vh,240px);overflow:hidden!important;scrollbar-width:none;backdrop-filter:blur(10px)}
body[data-mode="window"] #mao-window-subtitle p{font-size:clamp(13px,1.1vw,19px)!important;line-height:1.45!important;color:#d8edf6!important;overflow-wrap:anywhere;max-height:calc(min(32vh,240px) - 20px);overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:7}
body[data-mode="window"] #mao-window-subtitle ::-webkit-scrollbar{display:none;width:0;height:0}
body[data-mode="window"][data-mao-game="playing"] #mao-window-subtitle,body[data-mode="window"][data-mao-game="finished"] #mao-window-subtitle,body[data-mode="window"][data-mao-game="waiting"] #mao-window-subtitle{display:none}
.mao-studio-top{position:absolute;left:22px;right:22px;top:12px;display:flex;align-items:center;gap:12px;pointer-events:none;font:12px 'Segoe UI',sans-serif;color:#8db2c5;z-index:3}
.mao-studio-mark{font-size:15px;font-weight:750;letter-spacing:.3px;color:#f3faff}.mao-studio-mark span{color:#69e3df;font-weight:400}.mao-studio-live{display:flex;align-items:center;gap:6px;font-size:9px;letter-spacing:1.5px}.mao-studio-live::before{content:'';width:5px;height:5px;background:#69e3df;border-radius:50%}
@media(max-width:600px){.vtv-root{top:12px;width:calc(100vw - 16px)}.vtv-tv{border-width:5px;border-radius:13px}.mao-studio-top{left:12px;right:12px}.mao-studio-live{display:none}}
`;
function node(tag,className,text){const element=document.createElement(tag);if(className)element.className=className;if(text!==undefined)element.textContent = text;return element;}
export function createWordGameOverlay({baseUrl='http://127.0.0.1:12393',fetcher=fetch}={}){
  const style=node('style');style.textContent=STYLE;document.head.append(style);
  const root=node('section','vtv-root');root.id='mao-vua-tieng-viet';root.setAttribute('aria-label','Màn hình TV Mao VTuber');
  const canvas=node('canvas','vtv-tv');canvas.width=SCREEN_WIDTH;canvas.height=SCREEN_HEIGHT;root.append(canvas);
  const accessible=node('p','vtv-accessible');accessible.setAttribute('aria-live','polite');root.append(accessible);document.body.append(root);
  let current=null,offset=0,offline=false,disposed=false,poll,revision=0,lastFrame='';
  function paint(force=false){
    const phase=screenPhase(current,Date.now(),offset),key=`${current?.round_id}/${current?.revision}/${phase}/${remainingSeconds(current||{},Date.now(),offset)}/${cooldownSeconds(current,Date.now(),offset)}/${offline}/${tvArtRevision()}`;
    document.body.dataset.maoGame=phase;root.dataset.phase=phase;
    if(force||key!==lastFrame){drawTvScreen(canvas,current,{offset,offline});lastFrame=key;revision++;}
  }
  function render(state){current=state;paint(true);const phase=screenPhase(state,Date.now(),offset);accessible.textContent=phase==='idle'?'Mao VTuber. Gõ !vuatiengviet để chơi.':phase==='finished'?`Đáp án ${state.answer}. ${state.leaderboard?.[0]?.nickname||'Chưa có người chơi'}.`:`Vua tiếng Việt. Gợi ý ${(state.hint_index||0)+1}: ${state.hints?.at(-1)||'Đang chuẩn bị.'}`;}
  async function refresh(){
    if(disposed)return;
    try{const response=await fetcher(`${baseUrl}/api/vuatiengviet/state`,{cache:'no-store',signal:AbortSignal.timeout(3000)});if(!response.ok)throw Error(String(response.status));
      const state=await response.json();offset=state.server_now*1000-Date.now();const changed=!current||state.round_id!==current.round_id||state.revision!==current.revision||offline;offline=false;if(changed)render(state);else current=state;
    }catch{if(!offline){offline=true;paint(true);}}
    finally{if(!disposed)poll=setTimeout(refresh,current?.phase==='playing'?500:1500);}
  }
  const ticker=setInterval(()=>paint(),200);paint(true);refresh();
  return {get state(){return current;},get clockOffset(){return offset;},get offline(){return offline;},get textureRevision(){return revision;},canvas,element:root,render,destroy(){disposed=true;clearInterval(ticker);clearTimeout(poll);root.remove();style.remove();delete document.body.dataset.maoGame;}};
}
