import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {ROOM_BOUNDS,configureAvatarCamera,availableAvatarHeight} from '../web_tool/mao-5070/draco/room-view.mjs';
import {placement,petCameraView} from '../web_tool/mao-5070/draco/pet-placement.mjs';

const camera=new T.PerspectiveCamera(32,1,.02,30);
const view=placement({}, {width:1920,height:1080});
const pane={left:440,right:900,top:30,height:640},footer={left:440,right:900,top:535,height:135};
assert.equal(availableAvatarHeight('window',pane,footer),505,'floor would be hidden under the input footer');
assert.equal(availableAvatarHeight('window',pane,{...footer,top:631,height:39}),601,'collapsed footer space was not reclaimed');
assert.equal(availableAvatarHeight('pet',pane,footer),640,'window footer leaked into Pet Mode');
// Check the avatar pane, rather than total app width: the chat sidebar uses
// a substantial part of a small Window Mode window.
for(const [width,height] of [[460,505],[460,601],[280,535],[900,465],[1920,945],[220,765]]){
  configureAvatarCamera(camera,{mode:'window',view,width,height});
  for(const x of [ROOM_BOUNDS.min.x,ROOM_BOUNDS.max.x])for(const y of [ROOM_BOUNDS.min.y,ROOM_BOUNDS.max.y])for(const z of [ROOM_BOUNDS.min.z,ROOM_BOUNDS.max.z]){
    const p=new T.Vector3(x,y,z).project(camera);
    assert.ok(Math.abs(p.x)<.98&&Math.abs(p.y)<.98&&Math.abs(p.z)<1,`room clipped at ${width}x${height}: ${p.toArray()}`);
  }
  const project=zoom=>{configureAvatarCamera(camera,{mode:'window',view:{...view,zoom},width,height});return new T.Vector3(.2,1.2,0).project(camera);};
  const a=project(1.15),b=project(2.3);
  assert.ok(Math.abs(b.x-a.x*2)<1e-8&&Math.abs(b.y-a.y*2)<1e-8,'window wheel zoom must remain available');
}
// Switching back to Pet Mode must reproduce the previous camera exactly,
// including the saved desktop position and full-desktop virtual viewport.
const original=new T.PerspectiveCamera(32,1,.02,30),r=petCameraView(view,{width:1920,height:1080});
original.zoom=1;original.setViewOffset(r.fullWidth,r.fullHeight,r.offsetX,r.offsetY,r.width,r.height);
original.position.set(0,.975,3.45*Math.max(1,.65/(view.width/view.height)));original.lookAt(0,.94,0);original.updateMatrixWorld(true);
configureAvatarCamera(camera,{mode:'pet',view,width:1920,height:1080});
for(const property of ['projectionMatrix','matrixWorld'])for(let i=0;i<16;i++)assert.ok(Math.abs(camera[property].elements[i]-original[property].elements[i])<1e-10,`Pet Mode ${property} changed`);
configureAvatarCamera(camera,{mode:'window',view,width:460,height:640});
assert.equal(camera.view.enabled,false,'pet viewport must not leak into Window Mode');
for(const direction of [new T.Vector3(.6,.6,1),new T.Vector3(-.6,.6,1),new T.Vector3(0,1.1,1)]){
  configureAvatarCamera(camera,{mode:'window',view,width:280,height:505,roomView:{direction}});
  for(const x of [ROOM_BOUNDS.min.x,ROOM_BOUNDS.max.x])for(const y of [ROOM_BOUNDS.min.y,ROOM_BOUNDS.max.y])for(const z of [ROOM_BOUNDS.min.z,ROOM_BOUNDS.max.z]){
    const p=new T.Vector3(x,y,z).project(camera);assert.ok(Math.abs(p.x)<.98&&Math.abs(p.y)<.98&&Math.abs(p.z)<1,'orbit camera clipped the room');
  }
}
for(const focus of [{x:-3.3,z:-4.3},{x:3.3,z:.3}]){
  configureAvatarCamera(camera,{mode:'window',view,width:460,height:505,roomView:{kind:'follow',focus}});
  for(const point of [[focus.x,0,focus.z],[focus.x,1.9,focus.z]]){const p=new T.Vector3(...point).project(camera);assert.ok(Math.abs(p.x)<1&&Math.abs(p.y)<1,'follow camera lost Mao at a room corner');}
}
const cached=new T.PerspectiveCamera(32,1,.02,30),settings={mode:'window',view,width:460,height:505};
assert.equal(configureAvatarCamera(cached,settings),true);assert.equal(configureAvatarCamera(cached,settings),false,'unchanged camera recalculates the projection');
settings.width=800;assert.equal(configureAvatarCamera(cached,settings),true,'resize did not invalidate camera fit');
settings.roomView={kind:'follow',focus:{x:0,z:0}};assert.equal(configureAvatarCamera(cached,settings),true);assert.equal(configureAvatarCamera(cached,settings),false);
settings.roomView.focus.x=.5;assert.equal(configureAvatarCamera(cached,settings),true,'following Mao reuses stale camera position');
console.log('Window room camera: footer reserved, 6 pane sizes, orbit/follow, cached projection invalidation and unchanged Pet Mode projection passed.');
