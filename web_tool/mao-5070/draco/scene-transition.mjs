import {createCurtainCloth,CURTAIN_ART} from './curtain-cloth.mjs';
import {CurtainSound} from './curtain-sound.mjs';
// C2 easing: zero speed AND acceleration at either end of the heavy pull.
export const curtainEase=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(x*(x*6-15)+10);};
export const CURTAIN_TIMING={close:900,hold:420,open:1200};
export const SCENE_LABELS={lounge:'Phòng của Mao',studio:'Vua Tiếng Việt',concert:'Mao lên sân khấu'};
export class CurtainTimeline{
  constructor(initial='lounge',{close=CURTAIN_TIMING.close,hold=CURTAIN_TIMING.hold,open=CURTAIN_TIMING.open}={}){
    Object.assign(this,{current:initial,target:initial,phase:'idle',started:0,close,hold,open});
  }
  request(target,now){
    this.target=target;
    if(this.phase==='idle'&&target!==this.current){this.phase='closing';this.started=now;}
  }
  advance(now,ready=true){
    let commit=false,revealed=false;
    const elapsed=now-this.started;
    if(this.phase==='closing'&&elapsed>=this.close){this.current=this.target;this.phase='covered';this.started=now;commit=true;}
    else if(this.phase==='covered'){
      if(this.current!==this.target){this.current=this.target;this.started=now;commit=true;}
      else if(ready&&elapsed>=this.hold){this.phase='opening';this.started=now;}
    }else if(this.phase==='opening'&&elapsed>=this.open){this.phase='idle';revealed=true;}
    const progress=this.phase==='closing'?curtainEase((now-this.started)/this.close):this.phase==='opening'?1-curtainEase((now-this.started)/this.open):this.phase==='covered'?1:0;
    return {scene:this.current,phase:this.phase,progress,commit,revealed};
  }
}
export const CURTAIN_STYLE=`
.mao-curtain{position:absolute;inset:0;overflow:hidden;z-index:100;pointer-events:none;isolation:isolate;--closed:0;--badge:0;contain:layout paint style}
.mao-curtain[hidden]{display:none}.mao-curtain[data-active="true"]{pointer-events:auto}
.mao-curtain__panel{position:absolute;top:-2%;bottom:-2%;width:50.6%;background-color:#08342a;background-image:var(--curtain-art);background-size:200% 100%;will-change:transform;backface-visibility:hidden}
.mao-curtain__left{left:-.3%;background-position:left center;transform:scaleX(var(--closed));transform-origin:left center}
.mao-curtain__right{right:-.3%;background-position:right center;transform:scaleX(var(--closed));transform-origin:right center}
.mao-curtain__cloth{position:absolute;inset:0;width:100%;height:100%;z-index:1;display:none;pointer-events:none}
.mao-curtain[data-gpu="true"] .mao-curtain__cloth{display:block}.mao-curtain[data-gpu="true"] .mao-curtain__panel{visibility:hidden}
.mao-curtain__glow{position:absolute;inset:0;z-index:2;opacity:var(--closed);background:radial-gradient(ellipse at 50% 0,#d8f0dc16,transparent 50%),radial-gradient(ellipse at 50% 50%,transparent 45%,#00130f5c);pointer-events:none}
.mao-curtain__card{position:absolute;inset:0;z-index:3;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:17px;opacity:var(--badge);transform:translateY(calc((1 - var(--badge))*12px));color:#f1efda;text-align:center;padding:28px;text-shadow:0 2px 6px #001c16,0 4px 32px #001a14;font-family:'Times New Roman',serif;background:radial-gradient(ellipse at center,#001d1944,transparent 52%)}
.mao-curtain__seal{display:grid;place-items:center;width:58px;height:66px;border:1px solid #c6d6bc88;border-radius:50% 50% 45% 45%;background:linear-gradient(130deg,#092e26d9,#123f30b0);box-shadow:0 0 0 5px #afc8b415,inset 0 0 20px #b7d7bb12;color:#e7e7ce;font-size:38px;font-style:italic}
.mao-curtain__eyebrow{font:10px 'Segoe UI',sans-serif;letter-spacing:.42em;color:#bdd0bb;padding-left:.42em}.mao-curtain__title{margin:0;font-size:clamp(28px,4.5vw,58px);font-weight:400;max-width:90%;line-height:1.1;letter-spacing:.02em}
.mao-curtain__caption{font:12px 'Segoe UI',sans-serif;color:#c4d5c9;letter-spacing:.04em}.mao-curtain__rule{width:190px;height:1px;background:linear-gradient(90deg,transparent,#c7d6bb,transparent);position:relative}.mao-curtain__rule::after{content:'✦';position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);color:#dde6ca;font-size:18px;text-shadow:0 0 8px #12372c,0 0 12px #12372c}
.mao-curtain[data-reduced="true"]{background:#08251e;opacity:var(--closed)}.mao-curtain[data-reduced="true"] .mao-curtain__panel,.mao-curtain[data-reduced="true"] .mao-curtain__cloth{display:none}
@media(max-width:500px){.mao-curtain__seal{width:44px;height:52px;font-size:30px}.mao-curtain__card{gap:13px}.mao-curtain__caption{font-size:11px}.mao-curtain__eyebrow{font-size:9px}}
`;
function node(tag,name,text){const value=document.createElement(tag);value.className=name;if(text)value.textContent=text;return value;}
export function createSceneTransition(container,{initial='lounge',onCommit=()=>{},onRevealed=()=>{},isReady=()=>true}={}){
  const reduced=globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches||false;
  const timeline=new CurtainTimeline(initial,reduced?{close:120,hold:180,open:180}:{});
  const root=node('div','mao-curtain');root.hidden=true;root.dataset.reduced=String(reduced);root.setAttribute('role','status');root.setAttribute('aria-live','polite');
  const style=node('style','');style.textContent=CURTAIN_STYLE;
  root.style.setProperty('--curtain-art',`url("${CURTAIN_ART}")`);
  const clothCanvas=node('canvas','mao-curtain__cloth');clothCanvas.setAttribute('aria-hidden','true');
  const card=node('div','mao-curtain__card'),title=node('h2','mao-curtain__title');
  card.append(node('div','mao-curtain__seal','M'),node('div','mao-curtain__eyebrow','MAO PRESENTS'),title,node('div','mao-curtain__rule'),node('div','mao-curtain__caption','Sân khấu sẵn sàng, Mao ra ngay…'));
  root.append(style,node('div','mao-curtain__panel mao-curtain__left'),node('div','mao-curtain__panel mao-curtain__right'),clothCanvas,node('div','mao-curtain__glow'),card);container.append(root);
  let cloth,artReady=reduced,lastPhase='idle',soundEnabled=true;
  if(!reduced)try{cloth=createCurtainCloth(clothCanvas,{onReady:()=>{artReady=true;}});}catch{artReady=true;}
  try{soundEnabled=window.localStorage.getItem('mao.curtain.sound')!=='off';}catch{}
  const sound=new CurtainSound({enabled:soundEnabled&&!reduced});
  const warm=()=>sound.warm();window.addEventListener('pointerdown',warm,{capture:true});window.addEventListener('keydown',warm,{capture:true});
  return {timeline,element:root,sound,
    get ready(){return timeline.phase==='idle';},
    get scene(){return timeline.current;},
    request(scene,now=performance.now()){timeline.request(scene,now);},
    update(now=performance.now()){
      const frame=timeline.advance(now,artReady&&isReady(timeline.current));
      if(frame.phase!==lastPhase){
        if(document.visibilityState!=='hidden'){
          if(frame.phase==='closing')sound.play('close',timeline.close);
          else if(frame.phase==='opening')sound.play('open',timeline.open);
        }
        lastPhase=frame.phase;
      }
      if(frame.commit)onCommit(frame.scene);
      // Allow one complete rendered frame behind the closed curtain before it
      // opens, including resized canvases and newly uploaded game textures.
      if(frame.revealed)onRevealed(frame.scene);
      root.hidden=frame.phase==='idle';root.dataset.active=String(!root.hidden);
      root.dataset.phase=frame.phase;root.dataset.soundPlays=String(sound.played);
      root.style.setProperty('--closed',String(frame.progress));
      root.style.setProperty('--badge',String(curtainEase((frame.progress-.86)/.14)));
      if(!root.hidden&&cloth?.ready){cloth.draw(frame.progress,frame.phase,now);root.dataset.gpu='true';}
      const label=SCENE_LABELS[timeline.target]||'Mao chuẩn bị';if(title.textContent!==label)title.textContent=label;
      return frame;
    },
    setViewport(width,height){root.style.width=`${width}px`;root.style.height=`${height}px`;root.style.bottom='auto';cloth?.resize(width,height);},
    setSoundEnabled(value){sound.setEnabled(value&&!reduced);try{window.localStorage.setItem('mao.curtain.sound',value?'on':'off');}catch{}},
    dispose(){window.removeEventListener('pointerdown',warm,{capture:true});window.removeEventListener('keydown',warm,{capture:true});sound.dispose();cloth?.dispose();root.remove();}
  };
}
