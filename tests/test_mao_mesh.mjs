import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
const window={};vm.runInNewContext(fs.readFileSync('web_tool/mao-5070/mesh-rig.js','utf8'),{window});
const {Rig,parts,mesh,deform}=window.MaoMesh;
const geometry=parts.map(part=>({part,...mesh(part)}));
const alphaPoints=geometry.flatMap(g=>Array.from({length:g.indices.length/3},(_,i)=>{
  const ix=[g.indices[i*3]*2,g.indices[i*3+1]*2,g.indices[i*3+2]*2];
  return [ix.reduce((s,j)=>s+g.source[j],0)/3,ix.reduce((s,j)=>s+g.source[j+1],0)/3];
}));
// Read-only alpha inspection: never changes the original generated atlas.
const visible=JSON.parse(execFileSync('.venv/Scripts/python.exe',['-c',`import json,sys;from PIL import Image;a=Image.open('web_tool/mao-5070/parts-atlas.png').getchannel('A');print(json.dumps([a.getpixel((int(x),int(y)))>180 for x,y in json.load(sys.stdin)]))`],{input:JSON.stringify(alphaPoints),maxBuffer:2e6}).toString());
const area=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
const report={parts:parts.length,triangles:alphaPoints.length,visibleTriangles:visible.filter(Boolean).length,actions:{},frameRateDrift:0};
for(const action of ['idle','talk','blink','laugh','sad','greet','curious','shy','explain','nod','weight','turn']){
  const rig=new Rig();for(let i=0;i<120;i++)rig.update(1/120);rig.play(action);
  let sample=0,folds=0,checked=0;const eyes=[],mouth=[];
  for(let frame=0;frame<120*9;frame++){
    const p=rig.update(1/120,action==='talk'&&frame<720?.2:0);eyes.push(p.blink);mouth.push(p.mouth);
    for(const value of Object.values(p))assert.ok(Number.isFinite(value));
    if(frame%120!==60)continue;
    sample=0;
    for(const g of geometry){
      const posed=[];for(let i=0;i<g.source.length;i+=2)posed.push(deform(g.part,g.source[i],g.source[i+1],p));
      for(let i=0;i<g.indices.length;i+=3){
        if(visible[sample++]){checked++;const [a,b,c]=[posed[g.indices[i]],posed[g.indices[i+1]],posed[g.indices[i+2]]];
          if(area(a,b,c)>=0)folds++;
        }
      }
      if(g.part.name.startsWith('leg')){
        const q=deform(g.part,g.part.anchor[0],1000,p);
        const rest=g.part.position[0];assert.ok(Math.abs(q[0]-rest)<1e-8,'boot slides');
        const side=g.part.name.at(-1),hip=[0,1,2].map(i=>p[`hip${side}${i}`]),knee=[0,1,2].map(i=>p[`knee${side}${i}`]);
        const foot=[rest,g.part.position[1]+(g.part.ankle-g.part.anchor[1])*g.part.scale,0];
        const length=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
        assert.ok(Math.abs(length(hip,knee)-(g.part.knee-g.part.anchor[1])*g.part.scale)<.01,'thigh changes length');
        assert.ok(Math.abs(length(knee,foot)-(g.part.ankle-g.part.knee)*g.part.scale)<.01,'shin changes length');
        assert.ok(knee[2]>0,'knee must bend forward in depth');
      }
    }
  }
  if(action==='talk'){assert.ok(Math.max(...mouth)>.7);assert.ok(mouth.at(-1)<.001);}
  assert.ok(Math.max(...eyes)>.95,'automatic blink missing');
  assert.equal(rig.action,'idle','action does not return to idle');
  report.actions[action]={visibleTrianglesChecked:checked,invertedTriangles:folds};
}
const fps=[];for(const hz of [30,60,120]){const r=new Rig();r.play('greet');for(let i=0;i<hz*3;i++)r.update(1/hz,.1);fps.push(r.p);}
for(const key of Object.keys(fps[0]))for(const p of fps)report.frameRateDrift=Math.max(report.frameRateDrift,Math.abs(p[key]-fps[0][key]));
assert.ok(report.frameRateDrift<1e-8);
// Mid-gesture interruptions must preserve the current pose, including a blink.
const transitionRig=new Rig();transitionRig.play('greet');
for(let i=0;i<180;i++)transitionRig.update(1/120);
const before={...transitionRig.p};transitionRig.play('sad');
assert.deepEqual({...transitionRig.p},before,'play teleports the pose');
transitionRig.play('blink');assert.equal(transitionRig.action,'sad','blink cancels emotion');
for(let i=0;i<12;i++)transitionRig.update(1/120);
assert.ok(transitionRig.p.blink>.95,'manual blink must fully close');
// Seeded irregular blinks are reproducible at every rendering frame rate.
const blinks=new Rig(),blinkTimes=[];let prior=0;
for(let i=0;i<120*45;i++){blinks.update(1/120);if(blinks.p.blink>.95&&prior<=.95)blinkTimes.push(blinks.time);prior=blinks.p.blink;}
assert.ok(blinkTimes.length>=7);
assert.ok(new Set(blinkTimes.slice(1).map((v,i)=>(v-blinkTimes[i]).toFixed(1))).size>3,'blink timing is mechanical');
// Speech gestures need real audio and settle after it stops.
const speechRig=new Rig(),silentRig=new Rig();
let accentCount=0,previousBeat=-10;
for(let i=0;i<120*12;i++){
  speechRig.update(1/120,i<120*8&&i%240<90?.22:0);silentRig.update(1/120,0);
  if(speechRig.lastBeat!==previousBeat){accentCount++;previousBeat=speechRig.lastBeat;}
}
assert.ok(accentCount>=3&&accentCount<=6,'audio accents should be occasional');
assert.equal(silentRig.lastBeat,-10,'silent rig invents speech gestures');
assert.ok(speechRig.p.mouth<.001);
report.behavior={irregularBlinks:blinkTimes.length,speechAccents:accentCount,blinkPreservesEmotion:true,transitionPoseContinuous:true};
// Review whole trajectories, not just isolated action snapshots. At 60 Hz,
// transition between actions halfway through them and bound visible jumps.
const moving=new Rig();for(let i=0;i<120;i++)moving.update(1/120);
const landmarks=[['head',288,340],['armL',180,980],['armR',1350,460],['body',768,240],['legL',763,690],['legR',1288,690]].map(([name,x,y])=>[parts.find(p=>p.name===name),x,y]);
let last=null,maxStep=0,headMin=Infinity,headMax=-Infinity,kneeMin=Infinity,kneeMax=-Infinity;
const sequence=['greet','explain','weight','turn','nod','shy','laugh','sad','idle'];
for(let frame=0;frame<60*27;frame++){
  if(frame%180===0)moving.play(sequence[frame/180]);
  const p=moving.update(1/60),points=landmarks.map(([part,x,y])=>deform(part,x,y,p));
  if(last)for(let i=0;i<points.length;i++)maxStep=Math.max(maxStep,Math.hypot(points[i][0]-last[i][0],points[i][1]-last[i][1]));
  headMin=Math.min(headMin,points[0][0]);headMax=Math.max(headMax,points[0][0]);
  kneeMin=Math.min(kneeMin,p.kneeL2);kneeMax=Math.max(kneeMax,p.kneeL2);last=points;
}
assert.ok(maxStep<35,'visible limb jumps between frames');
assert.ok(headMax-headMin>20,'full body gestures are too small');
assert.ok(kneeMax-kneeMin>10,'knees do not respond to weight shift');
report.trajectory={seconds:27,maxLandmarkStepAt60Hz:maxStep,headTravel:headMax-headMin,kneeDepthRange:kneeMax-kneeMin};
console.log(JSON.stringify(report,null,2));
assert.ok(Object.values(report.actions).every(x=>x.invertedTriangles===0),'Visible mesh folds found');
