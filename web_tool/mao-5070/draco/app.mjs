import * as T from '../3d/vendor/three.module.js';
import {OrbitControls} from '../3d/vendor/OrbitControls.js';
import {GLTFLoader} from '../3d/vendor/loaders/GLTFLoader.js';
import {GLTFExporter} from '../3d/vendor/GLTFExporter.js';
import {clone} from '../3d/vendor/utils/SkeletonUtils.js';
import {bakeBodyClips} from './motion.mjs?v=30';
import {ACTIONS as BASE_ACTIONS,STORY_ACTIONS,SAMPLE_STORY} from './actions.mjs';
import {faceForAction,planPerformanceStory as planStory} from './performance-context.mjs?v=2';
import {PERFORMANCE_ACTIONS as ACTIONS,PERFORMANCE_META as ACTION_META} from './performance-motion.mjs?v=2';
import {AdaptiveBodyActor as BodyActor} from './motor-body.mjs';
import {AdaptiveFaceRig} from './motor-face.mjs';
import {attachMotorPreview} from './motor-preview.mjs';
import {FACE_PRESETS} from './performance-face.mjs?v=1';
import {validateDance} from './dance-body.mjs?v=2';
import whiteTopDance from './dances/white-top-dance.mjs';
const $=id=>document.getElementById(id),canvas=$('scene');
const DANCES=Object.fromEntries([whiteTopDance].map(raw=>{const dance=validateDance(raw);return [dance.id,dance];}));
const renderer=new T.WebGLRenderer({canvas,antialias:true,alpha:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;
const scene=new T.Scene(),camera=new T.PerspectiveCamera(32,1,.02,30);camera.position.set(0,1.1,3.6);
const controls=new OrbitControls(camera,canvas);controls.target.set(0,.95,0);controls.enableDamping=true;controls.minDistance=.6;controls.maxDistance=8;controls.maxPolarAngle=Math.PI*.60;controls.update();
scene.add(new T.HemisphereLight(0xfff9ff,0x807587,2.0));
const light=new T.DirectionalLight(0xfff6ed,2.0);light.position.set(-2,3,4);light.castShadow=true;light.shadow.mapSize.set(1024,1024);light.shadow.camera.left=-2;light.shadow.camera.right=2;light.shadow.camera.top=3;light.shadow.camera.bottom=-1;light.shadow.normalBias=.012;scene.add(light);
const rim=new T.DirectionalLight(0xd3bef8,1.1);rim.position.set(2,2,-3);scene.add(rim);
const stage=new T.Mesh(new T.CylinderGeometry(.65,.68,.025,80),new T.MeshStandardMaterial({color:0xe5dcec,roughness:.85}));stage.position.y=-.016;stage.receiveShadow=true;scene.add(stage);
const gltf=await new GLTFLoader().loadAsync('character.glb',event=>{if(event.total)$('status').textContent=`Đang tải ${Math.round(event.loaded/event.total*100)}%`;});
const asset=gltf.scene,wrapper=new T.Group();wrapper.add(asset);scene.add(wrapper);asset.updateMatrixWorld(true);
const bounds=new T.Box3().setFromObject(asset),size=bounds.getSize(new T.Vector3()),center=bounds.getCenter(new T.Vector3());
const scale=1.8/size.y;wrapper.scale.setScalar(scale);wrapper.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale);wrapper.updateMatrixWorld(true);
wrapper.userData.motionVersion='story-actions-v8-hem-clearance';
asset.userData.source=gltf.asset.extras||{};asset.userData.changes='Procedural body animation and readable joint names; source geometry and textures preserved.';
asset.traverse(m=>{if(m.isMesh){m.castShadow=true;m.receiveShadow=false;m.frustumCulled=false;}});
let actor=new BodyActor(asset);for(let i=0;i<180;i++)actor.update(1/120);
const face=new AdaptiveFaceRig(asset);
function setFace(name){face.setExpression(name);document.querySelectorAll('[data-face]').forEach(b=>b.classList.toggle('active',b.dataset.face===name));}
for(const [name,label] of Object.entries(FACE_PRESETS)){const button=document.createElement('button');button.dataset.face=name;button.textContent=label;button.onclick=()=>{$('face-auto').checked=false;demo=false;setFace(name);if($('hold').checked)for(let i=0;i<90;i++)face.update(0,false,1/120);};$('face-actions').append(button);}
const skeleton=new T.SkeletonHelper(asset);skeleton.visible=false;scene.add(skeleton);
const labels=Object.fromEntries(ACTIONS.map(a=>[a,ACTION_META[a].label]));
for(const action of ACTIONS){const button=document.createElement('button');button.dataset.action=action;button.textContent=labels[action];$(ACTION_META[action].group==='story'?'story-actions':'base-actions').append(button);}
$('story-text').value=SAMPLE_STORY;
let storyQueue=[],storyIndex=0,storyDue=Infinity;
let selected='hipSway',demo=true,demoIndex=0;
const demoBeats=[['hipSway','smile'],['refuse','flat'],['chuckle','squint'],['surprise','surprised'],['shy','smile'],['greet','smile']];
const select=action=>{selected=action;actor.clearMotor();actor.play(action);if($('face-auto').checked)setFace(faceForAction(action));$('action').textContent=labels[action];document.querySelectorAll('[data-action]').forEach(b=>b.classList.toggle('active',b.dataset.action===action));if($('hold').checked)holdPose();};
function stopStory(){if(storyQueue.length)$('story-progress').textContent='Đã dừng diễn theo câu chuyện.';storyQueue=[];storyDue=Infinity;canvas.dataset.storyBeat='';$('story-caption').hidden=true;}
function playStoryBeat(){const beat=storyQueue[storyIndex];select(beat.action);$('story-caption').textContent=beat.text;$('story-caption').hidden=false;$('story-progress').textContent=`Câu ${storyIndex+1}/${storyQueue.length} · ${labels[beat.action]}`;canvas.dataset.storyBeat=String(storyIndex+1);storyDue=actor.time+beat.seconds;}
$('story-play').onclick=()=>{demo=false;$('audio').pause();const beats=planStory($('story-text').value);if(!beats.length){$('story-progress').textContent='Nhập ít nhất một câu để diễn.';return;}$('auto').checked=false;$('pause').checked=false;$('hold').checked=false;storyQueue=beats;storyIndex=0;playStoryBeat();};
attachMotorPreview({actor:()=>actor,face,start(){demo=false;stopStory();$('auto').checked=false;$('pause').checked=false;$('hold').checked=false;}});
$('story-stop').onclick=()=>{demo=false;stopStory();$('story-progress').textContent='Đã dừng đoạn diễn.';select('idle');};
function resetBind(){for(const b of actor.bones){const r=actor.rest.get(b);b.position.copy(r.position);b.quaternion.copy(r.quaternion);}asset.updateMatrixWorld(true);}
// Dance preview: plays on its own clock (no song needed) or freezes on one frame.
let danceDef=null,danceClock=0,danceFrozen=false;
for(const dance of Object.values(DANCES)){const option=document.createElement('option');option.value=dance.id;option.textContent=dance.label||dance.id;$('dance-select').append(option);}
const danceCycle=()=>danceDef.frames.length/danceDef.fps;
function showDanceClock(){const cycle=danceCycle(),t=((danceClock%cycle)+cycle)%cycle;$('dance-time').max=String(cycle);$('dance-time').value=String(t);$('dance-clock').textContent=`${t.toFixed(1).replace('.',',')} s`;canvas.dataset.danceTime=t.toFixed(3);}
function beginDance(){demo=false;stopStory();$('audio').pause();$('auto').checked=false;$('pause').checked=false;$('hold').checked=false;actor.clearMotor();select('idle');setFace('smile');$('face-auto').checked=false;danceDef=DANCES[$('dance-select').value];}
function playDance(){beginDance();danceClock=0;danceFrozen=false;actor.setDance(danceDef,0);showDanceClock();}
function stopDance(){danceDef=null;danceFrozen=false;actor.clearDance();canvas.dataset.danceTime='';}
function seekDance(time){
  beginDance();resetBind();actor=new BodyActor(asset);for(let i=0;i<180;i++)actor.update(1/120);actor.play('idle');
  danceClock=Math.max(0,time);
  for(let i=0;i<180;i++){actor.setDance(danceDef,danceClock);actor.update(1/120);}
  danceFrozen=true;asset.updateMatrixWorld(true);showDanceClock();
}
$('dance-play').onclick=playDance;$('dance-stop').onclick=stopDance;
$('dance-time').oninput=e=>seekDance(Number(e.target.value));
// Renders one frame on demand (also used by QA captures while the tab is hidden).
function snapshot(){fitCanvas();asset.updateMatrixWorld(true);renderer.render(scene,camera);return canvas.toDataURL('image/jpeg',.88);}
// Offline clip: the dance advances only when asked, so every frame is a fixed
// 1/fps step of the same simulation (hair and cloth stay continuous).
function startClip(){
  playDance();danceFrozen=true;
  for(let i=0;i<150;i++){actor.setDance(danceDef,0);actor.update(1/120);}
}
function stepClip(dt){
  // Advance the dance at the solver's own 120 Hz, so arms, hair and cloth move
  // continuously between video frames instead of in one jump per frame.
  const steps=Math.max(1,Math.round(dt*120));
  for(let i=0;i<steps;i++){danceClock+=dt/steps;actor.setDance(danceDef,danceClock);actor.update(dt/steps);}
  face.update(0,false,dt);showDanceClock();
  return snapshot();
}
// Fixed output size and camera, so a clip never depends on the window layout.
function setClipLook({background=0xe9e4f0,eye=[0,1.12,4.5],target=[0,.98,0],width=720,height=860}={}){
  clipSize={width,height};renderer.setPixelRatio(1);renderer.setSize(width,height,false);
  camera.aspect=width/height;camera.updateProjectionMatrix();renderer.setClearColor(background,1);
  controls.target.set(...target);camera.position.set(...eye);controls.update();
}
window.dracoPreview={playDance,stopDance,seekDance,snapshot,startClip,stepClip,setClipLook};
function holdPose(){resetBind();actor=new BodyActor(asset);for(let i=0;i<180;i++)actor.update(1/120);actor.play(selected);for(let i=0;i<Math.round((ACTION_META[selected].at||2)*120);i++)actor.update(1/120);}
document.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>{demo=false;stopStory();$('auto').checked=false;select(button.dataset.action);});
$('face-auto').onchange=()=>{if($('face-auto').checked)setFace(faceForAction(selected));};
$('demo').onclick=()=>{stopStory();$('audio').pause();$('auto').checked=false;$('pause').checked=false;$('hold').checked=false;$('face-auto').checked=true;demo=true;demoIndex=0;select(demoBeats[0][0]);setFace(demoBeats[0][1]);next=actor.time+6.8;};
$('hold').onchange=()=>{if($('hold').checked){demo=false;stopStory();$('auto').checked=false;holdPose();}};
$('auto').onchange=()=>{demo=false;if($('auto').checked){stopStory();$('pause').checked=false;$('hold').checked=false;next=actor.time;}};
$('skeleton').onchange=e=>skeleton.visible=e.target.checked;
// A canvas that has no layout yet (hidden tab, fresh pane) must not poison the camera with NaN.
const frameRatio=()=>{const ratio=.72/(canvas.clientWidth/canvas.clientHeight);return Number.isFinite(ratio)?Math.max(1,ratio):1;};
let framing=frameRatio();
camera.position.sub(controls.target).multiplyScalar(framing).add(controls.target);controls.update();
let clipSize=null;
function fitCanvas(){
  if(clipSize)return;
  const w=canvas.clientWidth,h=canvas.clientHeight,dpr=renderer.getPixelRatio();
  if(!w||!h||(canvas.width===Math.round(w*dpr)&&canvas.height===Math.round(h*dpr)))return;
  const fitted=frameRatio();camera.position.sub(controls.target).multiplyScalar(fitted/framing).add(controls.target);framing=fitted;
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
}
function view(p,t){controls.target.set(...t);camera.position.set(...p).sub(controls.target).multiplyScalar(framing).add(controls.target);controls.update();}
$('front').onclick=()=>view([0,1.1,3.6],[0,.95,0]);$('side').onclick=()=>view([2.5,1.25,2.8],[0,1,0]);$('back').onclick=()=>view([0,1.1,-3.6],[0,.95,0]);$('close').onclick=()=>view([.1,1.5,1.6],[.04,1.35,0]);
$('face-close').onclick=()=>view([0,1.64,.58],[0,1.64,.04]);
let context,analyser,samples;
$('speak').onclick=async()=>{try{demo=false;if(!context){context=new AudioContext();analyser=context.createAnalyser();analyser.fftSize=1024;samples=new Float32Array(1024);context.createMediaElementSource($('audio')).connect(analyser);analyser.connect(context.destination);}await context.resume();$('audio').currentTime=0;await $('audio').play();stopStory();$('auto').checked=false;$('hold').checked=false;$('pause').checked=false;select('talk');}catch(error){$('status').textContent=error.message;}};
let last=performance.now(),metric=last,frames=0,next=actor.time+7.5,index=0;const sequence=['hipSway','refuse',...STORY_ACTIONS,...BASE_ACTIONS.filter(a=>!STORY_ACTIONS.includes(a))];
function tick(now){requestAnimationFrame(tick);const dt=(now-last)/1000;last=now;let rms=0;if(analyser&&!$('audio').paused){analyser.getFloatTimeDomainData(samples);rms=Math.sqrt(samples.reduce((s,x)=>s+x*x,0)/samples.length);}if(danceDef&&!danceFrozen&&!$('pause').checked){danceClock+=dt;actor.setDance(danceDef,danceClock,undefined,{live:true});showDanceClock();}
  if(!$('pause').checked&&!$('hold').checked&&!danceFrozen)actor.update(dt,rms);
  face.setMotor(actor.motorRaw?actor.motorPolicy.apply(actor.motorRaw):null,actor.motorAmount);
  face.update(rms*5,!$('audio').paused,$('pause').checked||$('hold').checked?0:dt);asset.updateMatrixWorld(true);
  if(storyQueue.length&&actor.time>=storyDue){storyIndex++;if(storyIndex<storyQueue.length)playStoryBeat();else{stopStory();$('story-progress').textContent='Đã diễn xong câu chuyện.';select('idle');}}
  if($('auto').checked&&actor.time>=next){index=(index+1)%sequence.length;select(sequence[index]);next=actor.time+7.5;}
  if(demo&&actor.time>=next){demoIndex=(demoIndex+1)%demoBeats.length;select(demoBeats[demoIndex][0]);setFace(demoBeats[demoIndex][1]);next=actor.time+6.8;}
  controls.update();fitCanvas();renderer.render(scene,camera);frames++;
  if(now-metric>1000){$('metrics').textContent=`${Math.round(frames*1000/(now-metric))} FPS`;frames=0;metric=now;$('diagnostics').textContent=`${actor.bones.length} khớp; ${actor.dynamics.segments.length} đoạn tóc/vải; độ lệch cổ chân ${(actor.audit.footDrift*1000).toFixed(3)} mm; tiếp xúc ${actor.dynamics.audit.contacts}`;}
  canvas.dataset.action=actor.action;canvas.dataset.footDrift=actor.audit.footDrift.toFixed(8);canvas.dataset.bones=String(actor.bones.length);canvas.dataset.actionCount=String(ACTIONS.length);canvas.dataset.clothSegments=String(actor.dynamics.segments.length);canvas.dataset.clothContacts=String(actor.dynamics.audit.contacts);canvas.dataset.clothStretch=actor.dynamics.audit.maxStretch.toFixed(8);
}
$('status').textContent=`PREVIEW · ${ACTIONS.length} CỬ CHỈ · ${Object.keys(FACE_PRESETS).length} NÉT MẶT`;select('hipSway');requestAnimationFrame(tick);
let clipUrl,glbUrl;
$('record').onclick=()=>{demo=false;const button=$('record'),stream=canvas.captureStream(30),chunks=[],mime=['video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(x=>MediaRecorder.isTypeSupported(x));const recorder=new MediaRecorder(stream,mime?{mimeType:mime,videoBitsPerSecond:5000000}:undefined);recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onstop=()=>{stream.getTracks().forEach(t=>t.stop());renderer.setClearColor(0,0);if(clipUrl)URL.revokeObjectURL(clipUrl);clipUrl=URL.createObjectURL(new Blob(chunks,{type:recorder.mimeType}));$('record-link').href=clipUrl;$('record-link').hidden=false;button.disabled=false;button.textContent='Ghi clip 30 giây';};stopStory();$('hold').checked=false;$('pause').checked=false;$('auto').checked=true;index=0;select(sequence[0]);next=actor.time+7.5;renderer.setClearColor(0xf2edf7,1);button.disabled=true;button.textContent='Đang ghi…';recorder.start();setTimeout(()=>recorder.stop(),30000);};
$('export').onclick=async()=>{const button=$('export');button.disabled=true;const wasPaused=$('pause').checked;$('pause').checked=true;try{
    const copy=clone(wrapper),bind=new Map(actor.bones.map(b=>[b.name,actor.rest.get(b)]));
    copy.traverse(b=>{const r=b.isBone&&bind.get(b.name);if(r){b.position.copy(r.position);b.quaternion.copy(r.quaternion);}});copy.updateMatrixWorld(true);
    const extras=[];copy.traverse(m=>{if(!m.isMesh)return;if(m.name.startsWith('preview-'))extras.push(m);if(m.morphTargetInfluences)m.morphTargetInfluences.fill(0);if(['CEL5','material','material_15'].includes(m.material.name))m.visible=true;if(['mao_mouth_cavity','mao_lip_rim','mao_upper_teeth','mao_tongue'].includes(m.name))m.visible=false;});extras.forEach(m=>m.removeFromParent());
    const clips=bakeBodyClips(copy);
    const binary=await new GLTFExporter().parseAsync(copy,{binary:true,animations:clips});
    const replay=await new GLTFLoader().parseAsync(binary,'');if(replay.animations.length!==BASE_ACTIONS.length||!BASE_ACTIONS.every(a=>replay.animations.some(c=>c.name===a)))throw new Error('Tệp xuất thiếu animation');
    const mixer=new T.AnimationMixer(replay.scene);mixer.clipAction(replay.animations.find(c=>c.name==='greet')).play();mixer.setTime(2);replay.scene.updateMatrixWorld(true);
    const hand=replay.scene.getObjectByName('draco_wristL').getWorldPosition(new T.Vector3());if(hand.y<1.4)throw new Error('Kiểm tra phát lại động tác chào chưa đạt');
    canvas.dataset.exportClips=String(replay.animations.length);canvas.dataset.exportHandHeight=hand.y.toFixed(4);
    replay.scene.traverse(m=>{if(m.isMesh){m.geometry.dispose();for(const material of Array.isArray(m.material)?m.material:[m.material]){material.map?.dispose();material.dispose();}}});
    if(glbUrl)URL.revokeObjectURL(glbUrl);glbUrl=URL.createObjectURL(new Blob([binary],{type:'model/gltf-binary'}));$('motion-link').href=glbUrl;$('motion-link').hidden=false;$('status').textContent=`Đã xuất và kiểm tra ${BASE_ACTIONS.length} chuyển động cơ bản`;
  }catch(error){$('status').textContent=error.message;console.error(error);}finally{button.disabled=false;$('pause').checked=wasPaused;}};
window.addEventListener('pagehide',()=>{renderer.dispose();controls.dispose();context?.close();if(clipUrl)URL.revokeObjectURL(clipUrl);if(glbUrl)URL.revokeObjectURL(glbUrl);});
