import * as T from './vendor/three.module.js';
import {OrbitControls} from './vendor/OrbitControls.js';
import {GLTFExporter} from './vendor/GLTFExporter.js';
import {buildMao} from './model.mjs';
import {Actor,actions} from './animation.mjs';
const $=id=>document.getElementById(id),canvas=$('scene');
const renderer=new T.WebGLRenderer({canvas,alpha:true,antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;
const scene=new T.Scene(),camera=new T.PerspectiveCamera(32,1,.05,30);camera.position.set(0,1.2,3.8);
const controls=new OrbitControls(camera,canvas);controls.target.set(0,1.0,0);controls.enableDamping=true;controls.minDistance=.7;controls.maxDistance=5;controls.maxPolarAngle=Math.PI*.65;controls.update();
scene.add(new T.HemisphereLight(0xfff7ff,0x695574,2));
const key=new T.DirectionalLight(0xfff4e8,2.5);key.position.set(-2,4,4);key.castShadow=true;key.shadow.mapSize.set(2048,2048);key.shadow.camera.left=-2;key.shadow.camera.right=2;key.shadow.camera.top=3;key.shadow.camera.bottom=-1;key.shadow.normalBias=.025;scene.add(key);
const rim=new T.DirectionalLight(0xbc9bf2,2.0);rim.position.set(2,2,-3);scene.add(rim);
const floor=new T.Mesh(new T.CylinderGeometry(.65,.7,.035,96),new T.MeshStandardMaterial({color:0xe6d9ee,roughness:.7}));floor.position.y=-.022;floor.receiveShadow=true;scene.add(floor);
const ring=new T.Mesh(new T.TorusGeometry(.64,.003,8,96),new T.MeshBasicMaterial({color:0xffffff}));ring.rotation.x=Math.PI/2;ring.position.y=-.003;scene.add(ring);
const model=buildMao();scene.add(model.group);let actor=new Actor(model);actor.play('greet');
model.eyes.forEach((e,i)=>e.name=`eyeExpression${i}`);model.mouth.name='mouthExpression';
const skeleton=new T.SkeletonHelper(model.group);skeleton.visible=false;scene.add(skeleton);
const names={idle:'Đứng nghỉ',greet:'Vẫy tay chào',explain:'Trò chuyện',laugh:'Cười',shy:'Ngượng ngùng',sad:'Buồn',turn:'Xoay vai và đầu'};
function select(action){actor.play(action);$('action').textContent=names[action];document.querySelectorAll('[data-action]').forEach(b=>b.classList.toggle('active',b.dataset.action===action));if(['greet','explain','laugh','shy'].includes(action)){$('reference').src=`../poses/${action}.png`;$('reference').alt=`Ảnh tham chiếu ${names[action]}`;$('ref-label').textContent=`${names[action]} · ảnh mục tiêu, chưa phải render 3D`;}}
document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>{$('auto').checked=false;select(b.dataset.action);}));
$('skeleton').addEventListener('change',e=>skeleton.visible=e.target.checked);
function view(position,target){camera.position.set(...position);controls.target.set(...target);controls.update();}
$('front').onclick=()=>view([0,1.2,3.8],[0,1,0]);$('side').onclick=()=>view([2.8,1.25,2.8],[0,1.05,0]);$('back').onclick=()=>view([0,1.2,-3.8],[0,1,0]);$('face').onclick=()=>view([0,1.65,1.5],[0,1.5,0]);
let audioContext,analyser,data;
$('speak').onclick=async()=>{try{if(!audioContext){audioContext=new AudioContext();analyser=audioContext.createAnalyser();analyser.fftSize=1024;data=new Float32Array(1024);audioContext.createMediaElementSource($('audio')).connect(analyser);analyser.connect(audioContext.destination);}await audioContext.resume();$('audio').currentTime=0;await $('audio').play();$('auto').checked=false;select('explain');}catch(error){$('status').textContent=error.message;}};
let last=performance.now(),next=8,index=0,frames=0,metric=last;const sequence=['greet','explain','laugh','shy','turn','idle'];
function frame(now){requestAnimationFrame(frame);const dt=(now-last)/1000;last=now;controls.update();let rms=0;if(analyser&&!$('audio').paused){analyser.getFloatTimeDomainData(data);rms=Math.sqrt(data.reduce((s,x)=>s+x*x,0)/data.length);}if(!$('pause').checked)actor.update(dt,rms);
  if($('auto').checked&&actor.time>next){index=(index+1)%sequence.length;select(sequence[index]);next=actor.time+8;}
  const w=canvas.clientWidth,h=canvas.clientHeight;if(canvas.width!==Math.round(w*renderer.getPixelRatio())||canvas.height!==Math.round(h*renderer.getPixelRatio())){renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
  renderer.render(scene,camera);frames++;if(now-metric>1000){$('metrics').textContent=`${Math.round(frames*1000/(now-metric))} FPS · ${model.skeleton.bones.length} khớp`;frames=0;metric=now;}
  canvas.dataset.action=actor.action;canvas.dataset.fingerJoints='30';canvas.dataset.bones=String(model.skeleton.bones.length);
}
$('status').textContent='3D LOCAL · SẴN SÀNG';requestAnimationFrame(frame);
function bake(){
  const clips=[];for(const action of actions){const sim=new Actor(model);for(let i=0;i<120;i++)sim.update(1/120);sim.play(action);const times=[],positions=model.skeleton.bones.map(()=>[]),rotations=model.skeleton.bones.map(()=>[]);
    for(let f=0;f<=210;f++){sim.update(1/30);times.push(f/30);model.skeleton.bones.forEach((b,i)=>{positions[i].push(...b.position.toArray());rotations[i].push(...b.quaternion.toArray());});}
    const tracks=[];model.skeleton.bones.forEach((b,i)=>{tracks.push(new T.VectorKeyframeTrack(`${b.name}.position`,times,positions[i]),new T.QuaternionKeyframeTrack(`${b.name}.quaternion`,times,rotations[i]));});clips.push(new T.AnimationClip(action,7,tracks));
  }return clips;
}
let exportUrl;
$('export').onclick=async()=>{const button=$('export');button.disabled=true;button.textContent='Đang xuất model và 7 chuyển động…';try{const clips=bake();actor=new Actor(model);actor.play('greet');next=8;const glb=await new GLTFExporter().parseAsync(model.group,{binary:true,animations:clips,onlyVisible:true});if(exportUrl)URL.revokeObjectURL(exportUrl);exportUrl=URL.createObjectURL(new Blob([glb],{type:'model/gltf-binary'}));$('download').href=exportUrl;$('download').hidden=false;button.textContent='Xuất lại model GLB + chuyển động';}catch(error){$('status').textContent=error.message;console.error(error);}finally{button.disabled=false;}};
