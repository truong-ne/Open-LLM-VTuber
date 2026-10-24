// Hand editor for a Mao choreography, side by side with its reference clip.
// Open through scripts/start_dance_editor.ps1 (or scripts/serve_dance_editor.mjs).
import * as T from '../3d/vendor/three.module.js';
import {GLTFLoader} from '../3d/vendor/loaders/GLTFLoader.js';
import {DanceBodyActor,validateDance} from './dance-body.mjs?v=2';
import {anglesToVector,changedFrames,danceModuleText,editArm,editValue,neighbourhood,readArm,vectorToAngles} from './dance-edit.mjs';

const $=id=>document.getElementById(id);
const status=text=>{$('status').textContent=text;};
const message=(text,error=false)=>{const m=$('message');m.textContent=text;m.classList.toggle('error',error);};
// Browser storage only holds a per-viewer draft; it may be missing or blocked.
const store={get:k=>{try{return localStorage.getItem(k);}catch{return null;}},set:(k,v)=>{try{localStorage.setItem(k,v);}catch{}},remove:k=>{try{localStorage.removeItem(k);}catch{}}};
const decimal=(v,d=2)=>Number(v).toFixed(d).replace('.',',');

// --- choreography --------------------------------------------------------------
const params=new URLSearchParams(location.search);
const danceId=/^[a-z0-9-]{1,64}$/.test(params.get('dance')||'')?params.get('dance'):'white-top-dance';
const source=(await import(`./dances/${danceId}.mjs?t=${Date.now()}`)).default;
const columns=source.columns;
let original=source.frames.map(row=>row.slice());
let rows=original.map(row=>row.slice());
let def=validateDance({...source,frames:rows});
const fps=def.fps,count=rows.length,cycle=count/fps;
const history=[];
const draftKey=`mao-dance-draft:${danceId}`;
try{
  const draft=JSON.parse(store.get(draftKey)||'null');
  if(draft&&draft.columns?.join()===columns.join()&&draft.rows?.length===count&&confirm('Có bản nháp đang chỉnh dở cho vũ đạo này. Mở lại bản nháp?')){
    rows=draft.rows;def=validateDance({...source,frames:rows});
  }
}catch{store.remove(draftKey);}
$('dance-name').textContent=source.label||danceId;
const reference=source.reference||{offset:0};
const offsetKey=`mao-dance-offset:${danceId}`;
$('offset').value=String(Number(store.get(offsetKey)??reference.offset??0).toFixed(4));
const offset=()=>Number($('offset').value)||0;
$('offset').onchange=()=>{store.set(offsetKey,$('offset').value);seekVideo();};

// --- 3D view -------------------------------------------------------------------
const canvas=$('scene');
const renderer=new T.WebGLRenderer({canvas,antialias:true,alpha:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;
renderer.setClearColor(0xe9e4f0,1);
const scene=new T.Scene(),camera=new T.PerspectiveCamera(30,3/4,.02,30);
scene.add(new T.HemisphereLight(0xfff9ff,0x807587,2));
const sun=new T.DirectionalLight(0xfff6ed,2);sun.position.set(-2,3,4);scene.add(sun);
const rim=new T.DirectionalLight(0xd3bef8,1.1);rim.position.set(2,2,-3);scene.add(rim);
const floorDisc=new T.Mesh(new T.CircleGeometry(.7,64),new T.MeshStandardMaterial({color:0xd8d0e2,roughness:.9}));floorDisc.rotation.x=-Math.PI/2;scene.add(floorDisc);
const gltf=await new GLTFLoader().loadAsync('character.glb',e=>{if(e.total)status(`Đang tải model ${Math.round(e.loaded/e.total*100)}%`);});
const asset=gltf.scene,wrapper=new T.Group();wrapper.add(asset);scene.add(wrapper);asset.updateMatrixWorld(true);
const bounds=new T.Box3().setFromObject(asset),size=bounds.getSize(new T.Vector3()),centre=bounds.getCenter(new T.Vector3());
const scale=1.8/size.y;wrapper.scale.setScalar(scale);wrapper.position.set(-centre.x*scale,-bounds.min.y*scale,-centre.z*scale);wrapper.updateMatrixWorld(true);
asset.traverse(m=>{if(m.isMesh)m.frustumCulled=false;});
const actor=new DanceBodyActor(asset);for(let i=0;i<180;i++)actor.update(1/120);

// The robe (with its wide sleeves) hides the arm; it can be shown faded or hidden.
const robe=[];asset.traverse(m=>{if(m.isMesh&&m.material?.name==='V8_Robe_Seams_Fabric_Lining')robe.push({mesh:m,material:m.material,ghost:null});});
function setRobe(mode){
  for(const part of robe){
    part.mesh.visible=mode!=='hidden';
    if(mode==='ghost'){part.ghost??=Object.assign(part.material.clone(),{transparent:true,opacity:.18,depthWrite:false});part.mesh.material=part.ghost;}
    else part.mesh.material=part.material;
  }
}
$('robe').onchange=()=>setRobe($('robe').value);setRobe($('robe').value);

// Bone lines drawn over the body: dancer's right in red, left in blue.
const BONES=[['clavicleR','upperR','R'],['upperR','elbowR','R','Ru'],['elbowR','wristR','R','Rf'],['clavicleL','upperL','L'],['upperL','elbowL','L','Lu'],['elbowL','wristL','L','Lf'],
  ['pelvis','spine','C'],['spine','chest','C'],['chest','neck','C'],['neck','head','C'],['pelvis','thighR','C'],['thighR','kneeR','R'],['kneeR','ankleR','R'],['pelvis','thighL','C'],['thighL','kneeL','L'],['kneeL','ankleL','L']];
// Drawn in 2D over the render, so the lines are thick and never hidden by the body.
const COLOURS={R:'#e2463f',L:'#2f6fe0',C:'#9c93a8',selected:'#f0a020'};
const overlay=$('bones2d'),overlayContext=overlay.getContext('2d'),scratch=new T.Vector3();
function project(name){
  actor.joints[name].getWorldPosition(scratch).project(camera);
  return [(scratch.x+1)/2*overlay.width,(1-scratch.y)/2*overlay.height];
}
function updateBones(){
  const w=overlay.clientWidth,h=overlay.clientHeight,dpr=Math.min(devicePixelRatio,2);
  if(overlay.width!==Math.round(w*dpr)||overlay.height!==Math.round(h*dpr)){overlay.width=Math.round(w*dpr);overlay.height=Math.round(h*dpr);}
  overlayContext.clearRect(0,0,overlay.width,overlay.height);
  if(!$('bones').checked)return;
  const selected=$('part').value,points=new Map();
  overlayContext.lineCap='round';
  // Body first, the selected segment last so it sits on top.
  for(const [a,b,side,part] of [...BONES].sort((x,y)=>(x[3]===selected)-(y[3]===selected))){
    const p=project(a),q=project(b);points.set(a,p);points.set(b,q);
    const chosen=part===selected;
    overlayContext.strokeStyle=chosen?COLOURS.selected:COLOURS[side];
    overlayContext.lineWidth=(chosen?6:side==='C'?2.5:4)*dpr;
    overlayContext.globalAlpha=side==='C'?.7:.95;
    overlayContext.beginPath();overlayContext.moveTo(...p);overlayContext.lineTo(...q);overlayContext.stroke();
  }
  overlayContext.globalAlpha=1;overlayContext.fillStyle='#ffffff';overlayContext.strokeStyle='#2f2638';overlayContext.lineWidth=1.5*dpr;
  for(const [x,y] of points.values()){overlayContext.beginPath();overlayContext.arc(x,y,3.5*dpr,0,Math.PI*2);overlayContext.fill();overlayContext.stroke();}
}
const VIEWS={front:{eye:[0,1.05,4.1],target:[0,.95,0]},upper:{eye:[0,1.35,2.3],target:[0,1.25,0]},side:{eye:[2.7,1.2,2.7],target:[0,1,0]}};
function setView(){const v=VIEWS[$('camera').value];camera.position.set(...v.eye);camera.lookAt(...v.target);}
$('camera').onchange=setView;setView();
function fitRenderer(){
  const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
  const dpr=renderer.getPixelRatio();
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
}

// --- reference clip ------------------------------------------------------------
const video=$('video'),ref=$('ref'),refContext=ref.getContext('2d');
const videoReady=()=>video.readyState>=2&&video.videoWidth>0;
function useVideo(url){video.src=url;video.load();}
video.addEventListener('loadeddata',()=>{$('ref-empty').hidden=true;seekVideo();});
$('open-video').onclick=()=>$('video-file').click();
$('video-file').onchange=()=>{const file=$('video-file').files[0];if(file)useVideo(URL.createObjectURL(file));};
// The editor's server can hand over the clip given on its command line.
fetch('/reference-video',{method:'HEAD'}).then(r=>{if(r.ok)useVideo('/reference-video');}).catch(()=>{});
function seekVideo(){if(videoReady()&&video.paused)video.currentTime=Math.max(0,Math.min(video.duration||0,offset()+time));}
function drawReference(){
  const w=ref.clientWidth,h=ref.clientHeight,dpr=Math.min(devicePixelRatio,2);
  if(ref.width!==Math.round(w*dpr)||ref.height!==Math.round(h*dpr)){ref.width=Math.round(w*dpr);ref.height=Math.round(h*dpr);}
  refContext.fillStyle='#1d1a22';refContext.fillRect(0,0,ref.width,ref.height);
  if(!videoReady())return;
  const [sx,sy,sw,sh]=$('zoom').checked&&reference.crop?reference.crop:[0,0,video.videoWidth,video.videoHeight];
  const s=Math.min(ref.width/sw,ref.height/sh),dw=sw*s,dh=sh*s;
  refContext.imageSmoothingQuality='high';
  refContext.drawImage(video,sx,sy,sw,sh,(ref.width-dw)/2,(ref.height-dh)/2,dw,dh);
}

// --- time ----------------------------------------------------------------------
let time=0,playing=false;
const frameAt=t=>((Math.round(t*fps)%count)+count)%count;
const speed=()=>Number($('speed').value)||1;
$('time').max=String(cycle);$('time').step=String(1/fps);
// Hold the pose at one time, letting the hand lag and cloth settle.
function showPose(t){for(let i=0;i<36;i++){actor.setDance(def,t);actor.update(1/120);}}
// Move through the dance at the solver's 120 Hz so arms, hair and cloth stay continuous.
function advance(from,to,dt){
  let delta=to-from;if(delta<-cycle/2)delta+=cycle;
  const steps=Math.max(1,Math.round(dt*120));
  for(let i=1;i<=steps;i++){actor.setDance(def,((from+delta*i/steps)%cycle+cycle)%cycle);actor.update(dt/steps);}
}
function updateClock(){
  const frame=frameAt(time);
  $('clock').textContent=`${decimal(time)} s · khung ${frame}`;
  $('time').value=String(time);
  drawMarks();refreshControls();
}
function seek(t){
  pause();time=((t%cycle)+cycle)%cycle;seekVideo();showPose(time);updateClock();
}
function play(){
  playing=true;$('play').textContent='Dừng';
  if(videoReady()){video.currentTime=offset()+time;video.playbackRate=speed();video.play().catch(()=>{});}
}
function pause(){
  if(!playing)return;
  playing=false;$('play').textContent='Phát';
  if(videoReady())video.pause();
  time=frameAt(time)/fps;seekVideo();showPose(time);updateClock();
}
$('play').onclick=()=>playing?pause():play();
$('prev').onclick=()=>seek((frameAt(time)-1)/fps);
$('next').onclick=()=>seek((frameAt(time)+1)/fps);
$('time').oninput=()=>seek(Number($('time').value));
$('speed').onchange=()=>{if(videoReady())video.playbackRate=speed();};
document.addEventListener('keydown',event=>{
  const typing=['INPUT','SELECT','TEXTAREA'].includes(document.activeElement?.tagName);
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();undo();return;}
  if(typing)return;
  if(event.key==='ArrowLeft'){event.preventDefault();$('prev').click();}
  else if(event.key==='ArrowRight'){event.preventDefault();$('next').click();}
  else if(event.key===' '&&document.activeElement?.tagName!=='BUTTON'){event.preventDefault();$('play').click();}
});

// --- timeline marks ------------------------------------------------------------
const marks=$('marks'),marksContext=marks.getContext('2d');
function drawMarks(){
  const w=marks.clientWidth,h=marks.clientHeight,dpr=Math.min(devicePixelRatio,2);
  if(marks.width!==Math.round(w*dpr)){marks.width=Math.round(w*dpr);marks.height=Math.round(h*dpr);}
  const style=getComputedStyle(document.documentElement);
  marksContext.clearRect(0,0,marks.width,marks.height);
  marksContext.fillStyle=style.getPropertyValue('--line');marksContext.fillRect(0,marks.height/2-1,marks.width,2);
  marksContext.fillStyle=style.getPropertyValue('--mark');
  for(const frame of changedFrames(original,rows))marksContext.fillRect(frame/count*marks.width-1,2,2,marks.height-4);
  marksContext.fillStyle=style.getPropertyValue('--accent');
  marksContext.fillRect(time/cycle*marks.width-1.5,0,3,marks.height);
}

// --- editing -------------------------------------------------------------------
const PARTS=[
  {id:'Ru',label:'Cánh tay trên phải',arm:'R'},{id:'Rf',label:'Cẳng tay phải',arm:'R'},
  {id:'Lu',label:'Cánh tay trên trái',arm:'L'},{id:'Lf',label:'Cẳng tay trái',arm:'L'},
  {id:'roll',label:'Nghiêng thân',min:-30,max:30,step:.5,unit:'°'},{id:'yaw',label:'Xoay thân',min:-45,max:45,step:.5,unit:'°'},
  {id:'turn',label:'Xoay cả người (sang trái người nhảy)',min:-60,max:60,step:.5,unit:'°'},{id:'pitch',label:'Cúi người ra trước',min:-30,max:30,step:.5,unit:'°'},
  {id:'hip',label:'Dịch hông (sang trái người nhảy)',min:-.3,max:.3,step:.005},{id:'drop',label:'Hạ hông (gập gối)',min:-.1,max:.3,step:.005},
  {id:'Rx',label:'Chân phải: cách trục giữa',min:-.5,max:.5,step:.005},{id:'Ry',label:'Chân phải: nhấc lên',min:-.1,max:.5,step:.005},{id:'Rz',label:'Chân phải: ra trước',min:-.5,max:.5,step:.005},
  {id:'Lx',label:'Chân trái: cách trục giữa',min:-.5,max:.5,step:.005},{id:'Ly',label:'Chân trái: nhấc lên',min:-.1,max:.5,step:.005},{id:'Lz',label:'Chân trái: ra trước',min:-.5,max:.5,step:.005}
].filter(p=>p.arm?columns.includes(p.id+'X'):columns.includes(p.id));
for(const part of PARTS)$('part').append(Object.assign(document.createElement('option'),{value:part.id,textContent:part.label}));
const radius=()=>Number($('radius').value);
const showRadius=()=>{$('radius-out').textContent=`± ${radius()} khung (${decimal(radius()/fps)} s)`;};
$('radius').oninput=showRadius;showRadius();

let gestureBase=null;
const begin=()=>{gestureBase??=rows.map(r=>r.slice());};
function finish(){
  if(!gestureBase)return;
  if(changedFrames(gestureBase,rows).length){history.push(gestureBase);if(history.length>200)history.shift();saveDraft();message(`Đã chỉnh khung ${frameAt(time)}.`);}
  gestureBase=null;
}
function rebuild(){
  def=validateDance({...source,frames:rows});
  showPose(time);drawMarks();
}
function saveDraft(){store.set(draftKey,JSON.stringify({columns,rows}));}
function slider(label,{min,max,step,value,format},onInput){
  const field=document.createElement('div');field.className='field';
  const id=`control-${Math.random().toString(36).slice(2)}`;
  field.innerHTML=`<label for="${id}">${label} <output></output></label><input type="range" id="${id}">`;
  const input=field.querySelector('input'),output=field.querySelector('output');
  Object.assign(input,{min,max,step,value});output.textContent=format(value);
  input.addEventListener('pointerdown',begin);input.addEventListener('keydown',begin);
  input.addEventListener('input',()=>{begin();output.textContent=format(Number(input.value));onInput(Number(input.value));});
  input.addEventListener('change',finish);
  return {field,set:v=>{input.value=String(v);output.textContent=format(v);}};
}
let controls=[];
function buildControls(){
  const part=PARTS.find(p=>p.id===$('part').value);$('controls').replaceChildren();controls=[];
  if(part.arm){
    const angles=()=>vectorToAngles(part.arm,readArm(rows,columns,part.id,frameAt(time)));
    let direction,forward;
    const apply=()=>{rows=editArm(gestureBase,columns,part.id,frameAt(time),anglesToVector(part.arm,direction.value(),forward.value()),{radius:radius(),loop:def.loop});rebuild();};
    const a=angles();
    const d=slider('Hướng (0 buông xuống · 90 dang ngang · 180 giơ thẳng · 270 vắt qua người)',{min:0,max:360,step:1,value:a.angle,format:v=>`${Math.round(v)}°`},apply);
    const f=slider('Ra phía trước (âm là ra sau)',{min:-85,max:85,step:1,value:a.forward,format:v=>`${Math.round(v)}°`},apply);
    direction={value:()=>Number(d.field.querySelector('input').value)};forward={value:()=>Number(f.field.querySelector('input').value)};
    controls=[()=>{const x=angles();d.set(x.angle);f.set(x.forward);}];
    $('controls').append(d.field,f.field);
  }else{
    const c=columns.indexOf(part.id),format=v=>part.unit?`${decimal(v,1)}${part.unit}`:decimal(v,3);
    const s=slider(part.label,{min:part.min,max:part.max,step:part.step,value:rows[frameAt(time)][c],format},value=>{
      rows=editValue(gestureBase,columns,part.id,frameAt(time),value,{radius:radius(),loop:def.loop});rebuild();
    });
    controls=[()=>s.set(rows[frameAt(time)][c])];
    $('controls').append(s.field);
  }
}
function refreshControls(){if(!gestureBase)controls.forEach(update=>update());}
$('part').onchange=buildControls;buildControls();

function undo(){
  if(!history.length){message('Không còn gì để hoàn tác.');return;}
  rows=history.pop();rebuild();refreshControls();saveDraft();message('Đã hoàn tác.');
}
$('undo').onclick=undo;
$('revert').onclick=()=>{
  const before=rows.map(r=>r.slice());
  for(const {index,weight} of neighbourhood(frameAt(time),radius(),count,def.loop))
    rows[index]=rows[index].map((v,c)=>Number((v+(original[index][c]-v)*weight).toFixed(4)));
  try{rebuild();}catch{rows=before;rebuild();message('Không trả về được ở khung này.',true);return;}
  history.push(before);saveDraft();refreshControls();message(`Đã trả khung ${frameAt(time)} (và vùng lân cận) về số đo.`);
};

// --- saving --------------------------------------------------------------------
const moduleText=()=>danceModuleText({...source,reference},rows,`// Edited by hand in dance-editor.html (${new Date().toISOString().slice(0,10)}), starting from the measured dance.\n`);
$('download').onclick=()=>{
  const link=Object.assign(document.createElement('a'),{href:URL.createObjectURL(new Blob([moduleText()],{type:'text/javascript'})),download:`${danceId}.mjs`});
  link.click();setTimeout(()=>URL.revokeObjectURL(link.href),2000);
  message(`Đã tải ${danceId}.mjs. Chép vào web_tool/mao-5070/draco/dances/ để dùng.`);
};
$('save').onclick=async()=>{
  message('Đang lưu…');
  try{
    const response=await fetch(`/api/dance?id=${encodeURIComponent(danceId)}`,{method:'POST',headers:{'Content-Type':'text/javascript'},body:moduleText()});
    const result=await response.json().catch(()=>({error:`HTTP ${response.status}`}));
    if(!response.ok)throw new Error(result.error||`HTTP ${response.status}`);
    original=rows.map(r=>r.slice());history.length=0;store.remove(draftKey);drawMarks();
    message(`Đã lưu vào ${result.file}`+(result.backup?` (bản cũ: ${result.backup})`:'')+'.');
  }catch(error){message(`Chưa lưu được: ${error.message}. Mở trang qua scripts/start_dance_editor.ps1, hoặc dùng “Tải file .mjs”.`,true);}
};

// --- loop ----------------------------------------------------------------------
let last=performance.now();
function loop(now){
  requestAnimationFrame(loop);
  const dt=Math.min(.1,(now-last)/1000);last=now;
  if(playing){
    let next=videoReady()&&!video.paused?video.currentTime-offset():time+dt*speed();
    if(next>=cycle||(videoReady()&&video.ended)){next=cycle-1/fps;advance(time,next,dt);time=next;pause();}
    else{advance(time,Math.max(0,next),dt);time=Math.max(0,next);updateClock();}
  }else{actor.setDance(def,time);actor.update(dt);}
  updateBones();fitRenderer();renderer.render(scene,camera);drawReference();
}
showPose(0);updateClock();
status(`${count} khung · ${decimal(cycle)} s · ${fps} khung/giây`);
requestAnimationFrame(loop);
window.danceEditor={seek,play,pause,get time(){return time;},get rows(){return rows;}};
