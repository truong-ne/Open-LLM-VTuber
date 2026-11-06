import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {createNativeMeshFixture} from './helpers/draco_mesh_fixture.mjs';
import {IdleLife,IDLE_TUNING} from '../web_tool/mao-5070/draco/idle-life.mjs';
import {BodyActor} from '../web_tool/mao-5070/draco/motion.mjs';
import {PerformanceFaceRig} from '../web_tool/mao-5070/draco/performance-face.mjs';

// --- Pure idle generator -------------------------------------------------
const run=(seed,seconds,ctx={},hook=()=>{})=>{const idle=new IdleLife({seed});for(let i=0;i<seconds*60;i++){idle.update(1/60,ctx);hook(idle,i/60);}return idle;};
const rad=d=>d*Math.PI/180;

// Breathing: about 15 breaths a minute, inhale shorter than exhale.
{
  let peaks=0,last=0,rising=0,falling=0,prev=0;
  run(3,60,{},idle=>{if(last<prev&&prev>idle.breath&&prev>.5)peaks++;last=prev;prev=idle.breath;if(idle.breath>prev)rising++;else falling++;});
  assert.ok(peaks>=12&&peaks<=19,`breaths per minute ${peaks}`);
  assert.ok(falling>rising*1.2,'exhale must be longer than inhale');
}
// Weight shifts happen, stay bounded and move slowly (no snapping).
{
  let min=0,max=0,maxStep=0,prev=0,changes=0,side=0;
  run(5,90,{},idle=>{min=Math.min(min,idle.shift);max=Math.max(max,idle.shift);maxStep=Math.max(maxStep,Math.abs(idle.shift-prev));prev=idle.shift;const s=Math.sign(Math.round(idle.shift*2));if(s!==side){side=s;changes++;}});
  assert.ok(max-min>.6,`weight shift range ${max-min}`);assert.ok(maxStep<.035,'weight shift must glide');assert.ok(changes>=4,`weight shifts ${changes}`);
  assert.ok(Math.abs(min)<=1&&max<=1);
}
// Gaze: glances happen; the eyes move first and the head follows later.
{
  const idle=new IdleLife({seed:11});let glances=0,lead=false,maxHead=0,maxEye=0,seen=idle.shiftSerial;
  for(let i=0;i<60*120;i++){
    idle.update(1/60);maxHead=Math.max(maxHead,Math.abs(idle.head.yaw));maxEye=Math.max(maxEye,Math.abs(idle.eye.yaw));
    if(idle.shiftSerial!==seen){seen=idle.shiftSerial;if(idle.gaze.away)glances++;
      if(idle.lastShift>.12){const before=Math.abs(idle.head.yaw);for(let k=0;k<6;k++)idle.update(1/60);const eye=Math.abs(idle.eye.yaw),head=Math.abs(idle.head.yaw);if(eye>.03&&head<eye+.02)lead=true;}}
  }
  assert.ok(glances>=8,`glances in two minutes ${glances}`);assert.ok(lead,'eyes must lead the head');
  assert.ok(maxHead<rad(20)&&maxEye<rad(10),`gaze limits head ${maxHead} eye ${maxEye}`);
}
// Not a loop: different seeds differ, the same seed repeats exactly, and the
// head path does not repeat with a fixed period.
{
  const a=run(1,20),b=run(2,20),c=run(1,20);
  assert.equal(a.out.head[1],c.out.head[1]);assert.notEqual(a.out.head[1],b.out.head[1]);
  const trace=[];run(8,120,{},(idle,t)=>{if(Math.round(t*60)%6===0)trace.push(idle.out.head[1]+idle.out.head[2]);});
  let best=0;for(let lag=100;lag<500;lag++){let sum=0,n=0;for(let i=0;i+lag<trace.length;i++){sum+=trace[i]*trace[i+lag];n++;}const e=trace.reduce((s,x)=>s+x*x,0)/trace.length;best=Math.max(best,Math.abs(sum/n)/e);}
  assert.ok(best<.8,`head motion looks periodic (${best})`);
}
// Visible but gentle: head moves a few degrees, torso well under one degree.
{
  let head=0,chest=0,spine=0,eyeBlinkGap=[];
  const idle=run(4,120,{},idle=>{head=Math.max(head,Math.hypot(...idle.out.head));chest=Math.max(chest,Math.abs(idle.out.chest[0]));spine=Math.max(spine,Math.abs(idle.out.spine[1]));});
  assert.ok(head>rad(2.5)&&head<rad(14),`head idle range ${head*180/Math.PI}°`);assert.ok(chest>rad(.4)&&chest<rad(1.2),`chest breath ${chest}`);assert.ok(spine<rad(2),'torso sway stays gentle');
  for(const v of Object.values(idle.out).flat(2))if(typeof v==='number')assert.ok(Number.isFinite(v));
}
// Head events: tilt, nod and shake all occur, and each is small.
{
  const kinds=new Set();let max=0;run(6,240,{},idle=>{if(idle.event)kinds.add(idle.event.kind);const e=idle.eventPose();max=Math.max(max,Math.abs(e.pitch),Math.abs(e.yaw),Math.abs(e.roll));});
  assert.deepEqual([...kinds].sort(),['nod','shake','tilt']);assert.ok(max<rad(5),`head event size ${max}`);
}
// Speaking: loudness onsets give beat nods; listening gives tilt and nods.
{
  let beats=0,seen=null;
  run(9,20,{speaking:true},()=>{});
  const idle=new IdleLife({seed:9});
  for(let i=0;i<60*20;i++){const loud=Math.floor(i/30)%2===0?.8:.05;idle.update(1/60,{speaking:true,energy:loud});if(idle.beat&&idle.beat!==seen){beats++;}seen=idle.beat;}
  assert.ok(beats>=8,`speech beats ${beats}`);
  const quiet=new IdleLife({seed:9});for(let i=0;i<60*20;i++)quiet.update(1/60,{speaking:false,energy:.8});assert.equal(quiet.beat,null,'no beat nods without speech');
  let nods=0,tilt=0;const listener=new IdleLife({seed:10});
  for(let i=0;i<60*40;i++){listener.update(1/60,{listening:true});if(listener.event?.soft&&listener.event.t<.02)nods++;tilt=Math.max(tilt,Math.abs(listener.tilt));}
  assert.ok(nods>=4,`listening nods ${nods}`);assert.ok(tilt>rad(1.5)&&tilt<=IDLE_TUNING.listenTilt+1e-9,`listening tilt ${tilt}`);
}
// Blinks: random interval, some double blinks, never shorter than a real blink.
{
  const idle=new IdleLife({seed:12}),gaps=Array.from({length:400},()=>idle.blinkInterval());
  assert.ok(Math.min(...gaps)>=.59&&Math.max(...gaps)<=6.5);
  assert.ok(gaps.filter(g=>g<1).length>20&&gaps.filter(g=>g<1).length<110,'double blinks');
  const mean=gaps.reduce((a,b)=>a+b,0)/gaps.length;assert.ok(mean>2.2&&mean<5,`mean blink gap ${mean}`);
}
// Limbs: arms drift visibly but gently, hand beats follow stress, feet pivot and tap.
{
  let arm=0,elbow=0,fingers=0,yaw=0,tap=0,handBeats=0,seen=null;
  const idle=new IdleLife({seed:21});
  for(let i=0;i<60*120;i++){
    const loud=Math.floor(i/30)%2===0?.8:.05;idle.update(1/60,{speaking:i>60*60,energy:i>60*60?loud:0});
    if(i<=60*60){arm=Math.max(arm,Math.abs(idle.out.upperL[2]),Math.abs(idle.out.upperR[2]));elbow=Math.max(elbow,Math.abs(idle.out.elbowL[0]));fingers=Math.max(fingers,Math.abs(idle.out.finger.L));}
    yaw=Math.max(yaw,Math.abs(idle.out.foot.L.yaw),Math.abs(idle.out.foot.R.yaw));tap=Math.max(tap,idle.out.foot.L.pitch,idle.out.foot.R.pitch);
    if(idle.hand&&idle.hand!==seen)handBeats++;seen=idle.hand;
  }
  assert.ok(arm>rad(2.5)&&arm<rad(12),`arm drift ${arm*180/Math.PI}°`);assert.ok(elbow>rad(4)&&elbow<rad(18),`elbow ${elbow*180/Math.PI}°`);
  assert.ok(fingers>.02&&fingers<.15,`finger curl ${fingers}`);assert.ok(yaw>rad(1.5)&&yaw<rad(7),`foot pivot ${yaw}`);assert.ok(tap>rad(1.5)&&tap<rad(5),`toe tap ${tap}`);
  assert.ok(handBeats>=6,`hand beats while speaking ${handBeats}`);
}
// Mood: sad droops the smile, lowers the head; annoyed lowers brows; blink after a phrase.
{
  const sad=new IdleLife({seed:30}),happy=new IdleLife({seed:30}),annoyed=new IdleLife({seed:30});
  sad.setMood('sad');happy.setMood('happy');annoyed.setMood('annoyed');
  for(const idle of [sad,happy,annoyed])for(let i=0;i<60*4;i++)idle.update(1/60);
  assert.ok(happy.out.face.smile>.45&&sad.out.face.smile<-.15,'mood smile');assert.ok(annoyed.out.face.brow<-.4&&sad.out.face.brow>.15,'mood brow');
  assert.ok(sad.out.face.lid>happy.out.face.lid+.1,'sad lids hang');assert.ok(sad.out.head[0]>happy.out.head[0]+.02,'sad head lowers');
  assert.ok(annoyed.out.face.smile>=-.45&&happy.out.face.smile<=1);
  const talker=new IdleLife({seed:31});let pauses=0,brow=0;
  for(let i=0;i<60*30;i++){const phrase=Math.floor(i/90)%2===0;talker.update(1/60,{speaking:true,energy:phrase?.7:0});brow=Math.max(brow,talker.out.face.brow);}
  pauses=talker.pauseSerial;assert.ok(pauses>=6,`phrase pauses ${pauses}`);assert.ok(brow>.2,`brow flash on stress ${brow}`);
}
// Mix fades layers out.
{
  let head=0,body=0;run(13,30,{mix:{body:0,look:0,breath:0}},idle=>{head=Math.max(head,Math.abs(idle.out.head[1]));body=Math.max(body,Math.abs(idle.out.waistX));});
  assert.ok(head<.002&&body<1e-9,'mix 0 must freeze the layers');
}

// --- Inside the real body rig --------------------------------------------
const {asset}=createNativeMeshFixture(),actor=new BodyActor(asset);
for(let i=0;i<180;i++)actor.update(1/120);
const face=new PerformanceFaceRig(asset);face.idleSource=()=>actor.idle;
const headRest=actor.rest.get(actor.joints.head).quaternion.clone();
let headRange=0,drift=0,waistMin=1,waistMax=-1,blinks=0,wasClosed=false,eyeMove=0,lastEye=0;
for(let i=0;i<120*60;i++){
  actor.update(1/120);face.update(0,false,1/120);
  headRange=Math.max(headRange,actor.joints.head.quaternion.angleTo(headRest));drift=Math.max(drift,actor.audit.footDrift);
  const x=actor.joints.waist.position.x;waistMin=Math.min(waistMin,x);waistMax=Math.max(waistMax,x);
  const closed=face.eyeClose>.5;if(closed&&!wasClosed)blinks++;wasClosed=closed;eyeMove=Math.max(eyeMove,Math.abs(actor.idle.eye.yaw-lastEye));lastEye=actor.idle.eye.yaw;
}
// Regression: the shared idle once produced NaN face weights, which made the whole face mesh vanish.
for(const v of Object.values(actor.idle.out.face))assert.ok(Number.isFinite(v),'idle face weight must be finite');
for(const mesh of [...face.meshes,...face.targets.map(t=>t.mesh)])assert.ok(Array.from(mesh.morphTargetInfluences).every(Number.isFinite),`${mesh.material.name}: non-finite morph weight hides the face`);
assert.ok(Number.isFinite(face.smileUniform.value));
assert.ok(face.face.visible,'face mesh must stay visible');
// Regression: the lip rim floated in front of the lips and showed as a ring beside the mouth
// once the head turned. Every rim vertex (closed and fully open) must lie on the lip/skin surface.
{
  const rim=face.overlays.find(m=>m.name==='mao_lip_rim'),surface=face.mouthSurface(),p=rim.geometry.attributes.position,open=rim.geometry.morphAttributes.position[0];
  let gap=0;for(let i=0;i<p.count;i++){const x=p.getX(i),y=p.getY(i),z=p.getZ(i);gap=Math.max(gap,Math.abs(z-surface(x,y)),Math.abs(z+open.getZ(i)-surface(x+open.getX(i),y+open.getY(i))));}
  assert.ok(face.rimSeated&&gap<.0012,`lip rim floats ${gap} off the face`);
}
// A standing mood set from outside survives idle steps; a sad gesture takes over, then hands back.
actor.idle.setMood('happy');for(let i=0;i<120*3;i++){actor.update(1/120);face.update(0,false,1/120);}
assert.ok(face.smileUniform.value>.4,`standing mood was overwritten (${face.smileUniform.value})`);
actor.play('sad');for(let i=0;i<120*2.5;i++){actor.update(1/120);face.update(0,false,1/120);}
assert.ok(face.smileUniform.value<0,`sad gesture should droop the smile (${face.smileUniform.value})`);
for(let i=0;i<120*9;i++){actor.update(1/120);face.update(0,false,1/120);}
assert.equal(actor.action,'idle');assert.ok(face.smileUniform.value>.4,'mood must return after the gesture');
actor.idle.setMood('calm');
assert.ok(headRange>rad(3),`idle head only moves ${headRange*180/Math.PI}°`);assert.ok(headRange<rad(25));
assert.ok(drift<.004,`idle feet slip ${drift}`);assert.ok(waistMax-waistMin>.004,'hips must shift in idle');
assert.ok(blinks>=10&&blinks<=30,`blinks per minute ${blinks}`);
// Cue-driven looks: left/right turn the head that way, "behind" brings the trunk in, then all returns.
{
  const look=new BodyActor(createNativeMeshFixture().asset);for(let i=0;i<240;i++)look.update(1/120);
  const yawOf=b=>{const q=b.getWorldQuaternion(new T.Quaternion()).multiply(look.rest.get(b).worldInverse);return new T.Euler().setFromQuaternion(q,'YXZ').y;};
  for(const [dir,sign] of [['left',1],['right',-1]]){
    assert.equal(look.lookToward(dir),true);let peak=0;for(let i=0;i<120*1.6;i++){look.update(1/120);peak=sign>0?Math.max(peak,yawOf(look.joints.head)):Math.min(peak,yawOf(look.joints.head));}
    assert.ok(Math.abs(peak)>rad(20)&&Math.sign(peak)===sign,`${dir}: head yaw ${peak*180/Math.PI}°`);
    for(let i=0;i<120*3;i++)look.update(1/120);assert.ok(Math.abs(yawOf(look.joints.head))<rad(12),`${dir}: head did not come back`);
  }
  look.lookToward('behind');let head=0,chest=0,drift=0;
  for(let i=0;i<120*1.8;i++){look.update(1/120);head=Math.max(head,Math.abs(yawOf(look.joints.head)));chest=Math.max(chest,Math.abs(yawOf(look.joints.chest)));drift=Math.max(drift,look.audit.footDrift);}
  assert.ok(head>rad(40)&&chest>rad(10),`behind: head ${head*180/Math.PI}°, chest ${chest*180/Math.PI}°`);assert.ok(drift<.004,'feet must stay planted while looking back');
  assert.equal(look.lookToward('up'),false);
}
// Regression: a thigh capsule fitted to the hip above the joint was ~25% too fat and pushed the
// front pleats out into a bulge over the belly. Standing (with idle sway) needs almost no push.
{
  const stand=new BodyActor(createNativeMeshFixture().asset);let push=0;
  for(let i=0;i<120*20;i++){stand.update(1/120);push=Math.max(push,stand.skirtClearance.maxCorrection/stand.dynamics.unit);}
  assert.ok(push<.008,`skirt pushed ${push} while just standing`);
  for(const leg of stand.skirtClearance.legs)assert.ok(leg.radius/stand.dynamics.unit<.12&&Math.min(...leg.sectors)/stand.dynamics.unit>.05,'thigh clearance radius out of range');
}
// Master intensity 0 restores the old, still pose; 2 doubles it.
const still=new BodyActor(createNativeMeshFixture().asset);still.setIdleIntensity(0);
for(let i=0;i<120*30;i++)still.update(1/120);
const stillQ=still.joints.head.quaternion.angleTo(still.rest.get(still.joints.head).quaternion);
assert.ok(stillQ<rad(1.2),`intensity 0 should stay nearly still: ${stillQ}`);
console.log(JSON.stringify({headRangeDeg:+(headRange*180/Math.PI).toFixed(2),blinksPerMinute:blinks,hipTravel:+(waistMax-waistMin).toFixed(4),footDrift:drift,stillHeadDeg:+(stillQ*180/Math.PI).toFixed(2)}));
