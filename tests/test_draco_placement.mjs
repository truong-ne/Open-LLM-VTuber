import assert from 'node:assert/strict';
import {placement,wheelZoom,attachPetPlacement,petCameraView,MIN_ZOOM,MAX_ZOOM} from '../web_tool/mao-5070/draco/pet-placement.mjs';
import {PerspectiveCamera,Vector3} from '../web_tool/mao-5070/3d/vendor/three.module.js';
for(const viewport of [{width:1920,height:1080},{width:1280,height:720},{width:320,height:240}]){
  for(const input of [{},{x:-100,y:90000,zoom:100},{x:90000,y:-100,zoom:-1},{x:NaN,y:Infinity,zoom:NaN}]){
    const value=placement(input,viewport);assert.ok(value.x<=viewport.width&&value.y<=viewport.height);assert.ok(value.x+value.width>=0&&value.y+value.height>=0);assert.ok(value.zoom>=MIN_ZOOM&&value.zoom<=MAX_ZOOM);
    if(value.width<=viewport.width)assert.ok(value.x>=0&&value.x+value.width<=viewport.width);
    if(value.height<=viewport.height)assert.ok(value.y>=0&&value.y+value.height<=viewport.height);
  }
}
assert.ok(wheelZoom(1,-100)>1);assert.ok(wheelZoom(1,100)<1);assert.equal(wheelZoom(MAX_ZOOM,-1000),MAX_ZOOM);assert.equal(wheelZoom(MIN_ZOOM,1000),MIN_ZOOM);
assert.equal(placement({zoom:.2}).zoom,.2,'small zoom should no longer stop at .65');
assert.equal(placement({zoom:8}).zoom,8,'close zoom should no longer stop at 3');
// Project through the actual Three.js camera without a browser or desktop UI.
const desktop={width:1920,height:1080};
function project(view,point){
  const camera=new PerspectiveCamera(32,1,.02,30),r=petCameraView(view,desktop);
  camera.setViewOffset(r.fullWidth,r.fullHeight,r.offsetX,r.offsetY,r.width,r.height);
  camera.position.set(0,.975,3.45*Math.max(1,.65/(view.width/view.height)));camera.lookAt(0,.94,0);camera.updateMatrixWorld(true);
  const p=new Vector3(...point).project(camera);
  return {x:(p.x+1)*desktop.width/2,y:(1-p.y)*desktop.height/2};
}
for(const zoom of [.2,.8,1.1]){
  const view=placement({x:400,y:80,zoom},desktop),head=project(view,[0,1.8,0]),feet=project(view,[0,0,0]);
  assert.ok(head.y>=view.y&&feet.y<=view.y+view.height,'complete body must fit its scaled viewport');
  assert.ok(head.y>=0&&feet.y<=desktop.height,'head/feet should remain visible when the pet fits the desktop');
}
const small=placement({x:400,y:80,zoom:.4},desktop),large=placement({x:400,y:80,zoom:.8},desktop);
const projectedHeight=view=>project(view,[0,0,0]).y-project(view,[0,1.8,0]).y;
assert.ok(Math.abs(projectedHeight(large)/projectedHeight(small)-2)<1e-10,'zoom should scale the whole model');
const outside=project(large,[1,1,0]);
assert.ok(outside.x>large.x+large.width&&outside.x<desktop.width,'geometry outside the hit box must still render on the desktop');
// Exercise the installed pointer/wheel handlers with isolated DOM-shaped test
// objects. This does not connect to or control the user's desktop/browser.
class Element extends EventTarget{
  constructor(){super();this.style={};this.classList={add(){},remove(){}};}
  closest(){return null;}
  setPointerCapture(id){this.captured=id;}
  getBoundingClientRect(){return {x:parseFloat(this.style.left)||0,y:parseFloat(this.style.top)||0,width:parseFloat(this.style.width)||400,height:parseFloat(this.style.height)||100};}
}
globalThis.window=new EventTarget();globalThis.innerWidth=1920;globalThis.innerHeight=1080;
globalThis.document={body:{dataset:{mode:'pet'}},getElementById:()=>null};
globalThis.getComputedStyle=()=>({display:'block'});globalThis.ResizeObserver=class{observe(){}};
globalThis.requestAnimationFrame=callback=>{callback();return 1;};globalThis.cancelAnimationFrame=()=>{};
const stage=new Element(),controls=new Element(),caption=new Element(),saved=new Map(),regions=[];
const storage={getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)};
const controller=attachPetPlacement({stage,controls,caption,storage,onChange(){},onRegions:r=>regions.push(r)});
function pointer(type,values){const event=Object.assign(new Event(type,{cancelable:true}),values);stage.dispatchEvent(event);return event;}
const start=controller.getState();pointer('pointerdown',{pointerId:4,button:0,clientX:10,clientY:10});pointer('pointermove',{pointerId:4,clientX:-290,clientY:30});pointer('pointerup',{pointerId:4});
const dragged=controller.getState();assert.equal(dragged.x,start.x-300);assert.equal(dragged.y,start.y+20);assert.equal(stage.captured,4);assert.equal(regions.at(-1).dragging,false);
const wheel=pointer('wheel',{deltaY:-120,deltaMode:0});assert.ok(wheel.defaultPrevented);assert.ok(controller.getState().zoom>dragged.zoom);assert.ok(saved.size);
for(let i=0;i<40;i++)pointer('wheel',{deltaY:-120,deltaMode:0});
assert.equal(controller.getState().zoom,MAX_ZOOM);
for(let i=0;i<60;i++)pointer('wheel',{deltaY:120,deltaMode:0});
assert.equal(controller.getState().zoom,MIN_ZOOM);
const beforeModeChange=controller.getState();
document.body.dataset.mode='window';innerWidth=900;innerHeight=670;window.dispatchEvent(new Event('resize'));
assert.equal(controller.getState().zoom,1.15,'Pet Mode zoom leaked into Window Mode and cropped the floor');
pointer('wheel',{deltaY:-120,deltaMode:0});const windowZoom=controller.getState().zoom;
assert.ok(windowZoom>1.15);assert.ok(saved.has('mao.draco.window-placement.v1'));
document.body.dataset.mode='pet';innerWidth=1920;innerHeight=1080;window.dispatchEvent(new Event('resize'));assert.equal(controller.getState().x,beforeModeChange.x,'window mode lost the desktop position');
assert.equal(controller.getState().zoom,beforeModeChange.zoom,'window zoom overwrote Pet Mode zoom');
document.body.dataset.mode='window';controller.refresh();assert.equal(controller.getState().zoom,windowZoom,'Window Mode lost its own zoom');
document.body.dataset.mode='pet';controller.refresh();
controller.focus();assert.equal(controller.getState().focus,'face');controller.reset();assert.equal(controller.getState().focus,'body');assert.equal(controller.getState().zoom,1.15);
// Wheel zoom keeps the point under the cursor stable unless a screen edge clamps it.
pointer('pointerdown',{pointerId:5,button:0,clientX:10,clientY:10});pointer('pointermove',{pointerId:5,clientX:10-controller.getState().x+500,clientY:10-controller.getState().y+80});pointer('pointerup',{pointerId:5});
const before=controller.getState(),anchor={x:before.x+before.width*.3,y:before.y+before.height*.4};
pointer('wheel',{deltaY:120,deltaMode:0,clientX:anchor.x,clientY:anchor.y});
const after=controller.getState();assert.ok(Math.abs((anchor.x-after.x)/after.width-.3)<1e-10);assert.ok(Math.abs((anchor.y-after.y)/after.height-.4)<1e-10);
console.log('Pet placement: full-body camera projection, no fixed-box clipping, cursor-anchored wheel zoom, drag, persistence and reset passed.');
