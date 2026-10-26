export const MIN_ZOOM=.15,MAX_ZOOM=12;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
export function placement(value={},viewport={width:1280,height:720}){
  const zoom=Number.isFinite(value.zoom)?clamp(value.zoom,MIN_ZOOM,MAX_ZOOM):1.15;
  const width=Math.min(440,Math.max(270,viewport.width*.28),viewport.width)*zoom;
  const height=Math.min(viewport.height,Math.max(300,Math.min(800,viewport.height*.72)))*zoom;
  if(value.dock==='bottom-right')return {x:viewport.width-width*.84-20,y:viewport.height-height*.93-18,width,height,zoom,focus:'body'};
  return {x:clamp(Number.isFinite(value.x)?value.x:viewport.width-width-24,Math.min(0,viewport.width-width),Math.max(0,viewport.width-width)),y:clamp(Number.isFinite(value.y)?value.y:viewport.height-height-40,Math.min(0,viewport.height-height),Math.max(0,viewport.height-height)),width,height,zoom,focus:value.focus==='face'?'face':'body'};
}
export function wheelZoom(zoom,delta){return clamp(zoom*Math.exp(-clamp(delta,-300,300)*.0015),MIN_ZOOM,MAX_ZOOM);}
// The pet's rectangle is a virtual camera viewport. Render its surrounding
// pixels too, up to the physical desktop edges, rather than crop at this box.
export function petCameraView(view,viewport){
  return {fullWidth:view.width,fullHeight:view.height,offsetX:-view.x,offsetY:-view.y,width:viewport.width,height:viewport.height};
}
export function attachPetPlacement({stage,controls,caption,onChange,onRegions,storage=localStorage,canZoom=()=>true,extraRegions=()=>[]}){
  const pet=()=>document.body.dataset.mode==='pet';
  const key=mode=>mode==='pet'?'mao.draco.placement.v1':'mao.draco.window-placement.v1';
  const read=mode=>{try{return JSON.parse(storage.getItem(key(mode))||'{}');}catch{return {};}};
  const profiles={pet:read('pet'),window:read('window')};
  let mode=pet()?'pet':'window',desired={...profiles[mode]},state=placement(desired,{width:innerWidth,height:innerHeight}),drag=null,frame;
  const viewport=()=>({width:innerWidth,height:innerHeight});
  const save=()=>{try{storage.setItem(key(mode),JSON.stringify({x:desired.x,y:desired.y,zoom:state.zoom,focus:state.focus,dock:desired.dock}));}catch{}};
  const regions=()=>{
    const rectangles=[stage,controls,caption,document.getElementById('input-form'),...extraRegions()].filter(e=>e&&getComputedStyle(e).display!=='none').map(e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height};});
    onRegions({mode:pet()?'pet':'window',dragging:!!drag,rectangles});
  };
  function apply(){
    const next=pet()?'pet':'window';
    if(mode!==next){profiles[mode]={...desired};mode=next;desired={...profiles[mode]};drag=null;stage.classList.remove('dragging');}
    state=placement(desired,viewport());
    if(pet())Object.assign(stage.style,{left:`${state.x}px`,top:`${state.y}px`,width:`${state.width}px`,height:`${state.height}px`,right:'auto',bottom:'auto',maxWidth:'none',minWidth:'0'});
    else for(const property of ['left','top','width','height','right','bottom','maxWidth','minWidth'])stage.style[property]='';
    onChange({...state});cancelAnimationFrame(frame);frame=requestAnimationFrame(regions);
  }
  stage.addEventListener('pointerdown',event=>{
    if(!pet()||event.button!==0||event.target.closest('button'))return;
    drag={id:event.pointerId,x:event.clientX,y:event.clientY,startX:state.x,startY:state.y};stage.setPointerCapture(event.pointerId);stage.classList.add('dragging');regions();event.preventDefault();
  });
  stage.addEventListener('pointermove',event=>{if(!drag||event.pointerId!==drag.id)return;delete desired.dock;desired.x=drag.startX+event.clientX-drag.x;desired.y=drag.startY+event.clientY-drag.y;apply();});
  const end=()=>{if(!drag)return;drag=null;desired.x=state.x;desired.y=state.y;stage.classList.remove('dragging');save();regions();};
  stage.addEventListener('pointerup',end);stage.addEventListener('pointercancel',end);stage.addEventListener('lostpointercapture',end);
  const setZoom=(next,anchor={x:state.x+state.width/2,y:state.y+state.height})=>{
    const ratio=next/state.zoom;
    desired.x=anchor.x+(state.x-anchor.x)*ratio;
    desired.y=anchor.y+(state.y-anchor.y)*ratio;
    desired.zoom=next;apply();desired.x=state.x;desired.y=state.y;save();
  };
  stage.addEventListener('wheel',event=>{if(!canZoom())return;event.preventDefault();setZoom(wheelZoom(state.zoom,event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?innerHeight:1)),pet()&&Number.isFinite(event.clientX)&&Number.isFinite(event.clientY)?{x:event.clientX,y:event.clientY}:undefined);},{passive:false});
  const zoom=amount=>setZoom(clamp(state.zoom*amount,MIN_ZOOM,MAX_ZOOM));
  window.addEventListener('resize',apply);const observer=new ResizeObserver(apply);if(caption)observer.observe(caption);
  apply();
  return {refresh:apply,regions,zoom,dockBottomRight(zoom){desired={zoom:clamp(zoom,MIN_ZOOM,MAX_ZOOM),dock:'bottom-right',focus:'body'};apply();save();},focus(){desired.focus=state.focus==='face'?'body':'face';apply();save();},reset(){desired={};apply();save();},getState:()=>({...state}),isDragging:()=>!!drag,dispose(){window.removeEventListener('resize',apply);observer.disconnect();cancelAnimationFrame(frame);}};
}
