import test from 'node:test';
import assert from 'node:assert/strict';
import {
  LM,bridgeUnsure,clean,closeLoop,keyCurve,despikeDirections,fixSwaps,fillGaps,hampel,limitArmSpeed,measure,mergePasses,normalizeDirections,toModule,trackDancer,worldAxes,COLUMN_ORDER
} from '../scripts/dance_from_pose.mjs';
import {sampleDance,validateDance} from '../web_tool/mao-5070/draco/dance-body.mjs';

// A synthetic dancer facing the camera. World axes follow one detector convention
// (x to the image right, y down, z toward the camera is negative); the converter has
// to work that out from anatomy. Image coordinates are normalised to a crop.
const norm=v=>{const n=Math.hypot(...v);return v.map(x=>x/n);};
function dancer({R={upper:[0,-1,0],fore:[0,-1,0]},L={upper:[0,-1,0],fore:[0,-1,0]},at=[.5,.5],ankles=[.1,.1],lift=[0,0],visibility=1}={}){
  const w=Array.from({length:33},()=>[0,0,0]);
  const body=(x,up,fwd)=>[x,-up,-fwd];                 // body frame (left, up, forward) → world
  const set=(i,p)=>{w[i]=p;};
  set(LM.NOSE,body(0,.65,.08));
  set(LM.L_SH,body(.2,.5,0));set(LM.R_SH,body(-.2,.5,0));
  set(LM.L_HIP,body(.1,0,0));set(LM.R_HIP,body(-.1,0,0));
  for(const [side,sh,el,wr,arm] of [['L',LM.L_SH,LM.L_EL,LM.L_WR,L],['R',LM.R_SH,LM.R_EL,LM.R_WR,R]]){
    const u=norm(arm.upper).map(v=>v*.3),f=norm(arm.fore).map(v=>v*.25);
    const shoulder=[side==='L'?.2:-.2,.5,0];
    const elbow=[shoulder[0]+u[0],shoulder[1]+u[1],shoulder[2]+u[2]];
    set(el,body(...elbow));set(wr,body(elbow[0]+f[0],elbow[1]+f[1],elbow[2]+f[2]));
  }
  set(LM.L_ANK,body(ankles[0],-.85+lift[0],0));set(LM.R_ANK,body(-ankles[1],-.85+lift[1],0));
  // A real camera: the same pixel scale across and down the default 130x170 crop.
  const image=w.map(p=>[at[0]+p[0]*.8,at[1]+p[1]*.8*130/170,p[2],visibility]);
  return {image,world:w.map(p=>[...p,visibility])};
}
const sequence=(count,make)=>Array.from({length:count},(_,i)=>({i:i+1,poses:[make(i)]}));
const near=(a,b,tolerance=.03)=>assert.ok(a.every((v,i)=>Math.abs(v-b[i])<tolerance),`${a.map(v=>v.toFixed(3))} ≠ ${b}`);

test('axes are worked out from anatomy, whatever the detector convention',()=>{
  const poses=sequence(10,()=>dancer()).map(f=>f.poses[0]);
  assert.deepEqual(worldAxes(poses),{x:1,y:-1,z:-1});
  // The same dancer seen with every axis mirrored gives the same body measurements.
  const mirrored=poses.map(p=>({image:p.image,world:p.world.map(([x,y,z,v])=>[-x,-y,-z,v])}));
  assert.deepEqual(worldAxes(mirrored),{x:-1,y:1,z:1});
});

test('arm directions come out in the dancer’s body frame, per side',()=>{
  const frames=sequence(30,()=>dancer({L:{upper:[1,0,0],fore:[1,.5,0]},R:{upper:[0,1,0],fore:[-.5,.5,.7]}}));
  const {columns}=measure(trackDancer(frames));
  const at=prefix=>['X','Y','Z'].map(a=>columns[prefix+a][15]);
  near(at('Lu'),[1,0,0]);near(at('Lf'),norm([1,.5,0]));
  near(at('Ru'),[0,1,0]);near(at('Rf'),norm([-.5,.5,.7]));
});

test('the right person is followed, not a neighbour or a stray detection',()=>{
  const frames=sequence(40,i=>dancer({at:[.5+(i>20?.02:0),.5]}));
  const neighbour=dancer({at:[.82,.5]}),stray=dancer({at:[.05,.5]});
  frames.forEach(f=>f.poses.push(neighbour,stray));
  frames[10].poses=[neighbour];                      // she is missed, only the neighbour is seen
  const tracked=trackDancer(frames);
  assert.equal(tracked[10],null,'a neighbour is never taken for her');
  tracked.forEach((p,i)=>{if(i!==10)assert.ok(Math.abs(p.image[LM.L_HIP][0]-(.5+.1*.8+(i>20?.02:0)))<1e-6,`frame ${i}`);});
});

test('swapped left/right labels are repaired from one frame to the next',()=>{
  const frames=sequence(20,()=>dancer({L:{upper:[1,0,0],fore:[1,0,0]},R:{upper:[0,-1,0],fore:[0,-1,0]},ankles:[.2,.05]}));
  const poses=frames.map(f=>f.poses[0]);
  const swap=pose=>{const s=part=>{const c=part.map(p=>p.slice());for(const [l,r] of [[11,12],[13,14],[15,16],[23,24],[25,26],[27,28]]){c[l]=part[r].slice();c[r]=part[l].slice();}return c;};return {image:s(pose.image),world:s(pose.world)};};
  poses[8]=swap(poses[8]);poses[9]=swap(poses[9]);
  const fixed=fixSwaps(poses);
  fixed.forEach((p,i)=>near(p.image[LM.L_WR],poses[0].image[LM.L_WR],1e-6,`frame ${i}`));
  near(fixed[9].image[LM.R_ANK],poses[0].image[LM.R_ANK],1e-6);
});

test('gaps, spikes and low-confidence landmarks do not reach the dance',()=>{
  assert.deepEqual(fillGaps([1,Number.NaN,Number.NaN,4]).map(v=>Number(v.toFixed(2))),[1,2,3,4]);
  assert.deepEqual(fillGaps([Number.NaN,5,Number.NaN]),[5,5,5]);
  assert.deepEqual(hampel([1,1,1,9,1,1,1],{radius:2,floor:.01}),[1,1,1,1,1,1,1]);
  const frames=sequence(40,()=>dancer({R:{upper:[0,-1,0],fore:[0,-1,0]}}));
  const poses=frames.map(f=>f.poses[0]);
  // A wrist the detector has given up on is dropped and filled in.
  const wild=(pose,visibility)=>({...pose,image:pose.image.map((p,i)=>i===LM.R_WR?[.9,.1,0,visibility]:p),world:pose.world.map((p,i)=>i===LM.R_WR?[3,3,3,visibility]:p)});
  poses[20]=wild(poses[20],.05);
  const lost=measure(poses);
  assert.ok(Number.isNaN(lost.columns.RfX[20]),'a lost wrist is dropped');
  near(['X','Y','Z'].map(a=>clean(lost.columns,{confidence:lost.confidence})['Rf'+a][20]),[0,-1,0],.05);
  // An unsure (but not lost) wrist is kept, and weighs less than the sure frames around it.
  poses[20]=wild(frames[20].poses[0],.3);
  const unsure=measure(poses);
  assert.ok(Number.isFinite(unsure.columns.RfX[20])&&unsure.confidence.Rf[20]===.3);
  const trusted=clean(unsure.columns),weighted=clean(unsure.columns,{confidence:unsure.confidence});
  const away=c=>Math.acos(-c.RfY[20])*180/Math.PI;
  assert.ok(away(weighted)<=away(trusted)&&away(weighted)<10,'confidence weighting pulls an unsure glitch back');
});

test('depth comes from how long a bone looks, its sign is held between plane crossings',()=>{
  // The forearm swings from hanging (full length in the picture) to 60° toward the
  // camera. The detector's depth is far too small; the rebuilt depth follows the length.
  const fore=i=>{const a=Math.min(1,i/20)*Math.PI/3;return [0,-Math.cos(a),Math.sin(a)];};
  const frames=sequence(30,i=>dancer({L:{upper:[0,-1,0],fore:fore(i)}}));
  const poses=trackDancer(frames).map(p=>({image:p.image,world:p.world.map((w,j)=>j===LM.L_WR?[w[0],w[1],w[2]*.3,w[3]]:w)}));
  const {columns}=measure(poses);
  near(['X','Y','Z'].map(a=>columns['Lf'+a][25]),fore(25),.05);
  // A sign checked by eye wins over the detector, with a least depth (a hand behind the head).
  const fixed=measure(poses,{fixes:[{bone:'Lf',from:10,to:20,side:'back',min:.5}]}).columns;
  assert.ok(fixed.LfZ[15]<-.4,'the forearm is turned away from the camera');
  assert.ok(fixed.LfZ[25]>.8,'outside the fix the measured side is kept');
});

test('several detector passes are merged, and a pass that disagrees counts less',()=>{
  const a=dancer(),b=dancer(),c=dancer();
  b.image[LM.L_WR]=[a.image[LM.L_WR][0]+.01,a.image[LM.L_WR][1],0,1];
  c.image[LM.L_WR]=[.95,.05,0,1];                    // one pass loses the wrist
  const [merged]=mergePasses([[a],[b],[c]]);
  near(merged.image[LM.L_WR].slice(0,2),[a.image[LM.L_WR][0]+.005,a.image[LM.L_WR][1]],1e-6);
  assert.ok(merged.image[LM.L_WR][3]<.7,'agreement of two passes in three lowers the confidence');
  assert.equal(mergePasses([[null],[null]])[0],null);
});

test('keyframes are joined smoothly and holds are eased into and out of',()=>{
  const up=[0,1,0],out=[1,0,0],down=[0,-1,0];
  const curve=keyCurve([[0,down],[10,out],[20,up],[30,up]]);
  near(curve(10),out,1e-9);near(curve(25),up,1e-9);
  const step=f=>Math.acos(Math.max(-1,Math.min(1,curve(f).reduce((s,v,i)=>s+v*curve(f+1)[i],0))))*180/Math.PI;
  // Flowing through the middle key: no change of speed there.
  assert.ok(Math.abs(step(9)-step(10))<1.5,`speed is continuous through a key (${step(9).toFixed(2)} vs ${step(10).toFixed(2)})`);
  // Easing into the hold: the last step before it is much slower than the middle of the move.
  assert.ok(step(19)<step(14)*.5,'the arm slows down into a held pose');
  assert.ok(step(0)<step(5)*.5,'and starts gently out of the first key');
});

test('a run of unsure glitches between sure samples follows the sure path',()=>{
  const n=20,make=()=>{const c={};for(const name of COLUMN_ORDER)c[name]=Array(n).fill(0);return c;};
  const columns=make(),confidence={Ru:Array(n).fill(1),Rf:Array(n).fill(1),Lu:Array(n).fill(1),Lf:Array(n).fill(1)};
  for(const prefix of ['Ru','Rf','Lu','Lf'])columns[prefix+'Y']=Array(n).fill(1);   // arm up the whole time
  for(const i of [8,9,10]){columns.LfY[i]=-1;confidence.Lf[i]=.15;}                // except three dim frames
  columns.LfX[12]=.5;columns.LfY[12]=.87;confidence.Lf[12]=.15;                     // a dim frame that agrees
  const out=bridgeUnsure(columns,confidence);
  for(const i of [8,9,10])assert.ok(out.LfY[i]>.99,`frame ${i} follows the sure path`);
  assert.equal(out.LfX[12],.5,'an unsure sample that agrees keeps its own value');
});

test('fast genuine arm motion survives the clean-up',()=>{
  // A 3 Hz forearm roll in front of the chest, as at the start of the reference clip.
  const frames=sequence(60,i=>{const a=2*Math.PI*3*i/30;return dancer({L:{upper:[.6,-.6,.5],fore:[-.8,.25*Math.sin(a),.5+.25*Math.cos(a)]}});});
  const {columns,confidence}=measure(trackDancer(frames));
  const cleaned=clean(columns,{confidence});
  const swing=values=>Math.max(...values.slice(10,50))-Math.min(...values.slice(10,50));
  assert.ok(swing(cleaned.LfY)>.6*swing(columns.LfY),`the roll keeps most of its size (${swing(cleaned.LfY).toFixed(2)} of ${swing(columns.LfY).toFixed(2)})`);
});

test('a one-frame spike in an arm direction is removed and fast moves are capped',()=>{
  const n=30,down=[0,-1,0],up=[0,1,0];
  const make=vectors=>{const c={};for(const name of COLUMN_ORDER)c[name]=Array(n).fill(0);
    for(const prefix of ['Ru','Rf','Lu','Lf']){c[prefix+'X']=vectors.map(v=>v[0]);c[prefix+'Y']=vectors.map(v=>v[1]);c[prefix+'Z']=vectors.map(v=>v[2]);}return c;};
  const spiked=make(Array.from({length:n},(_,i)=>i===12?up:down));
  const despiked=despikeDirections(normalizeDirections(spiked),1);
  near([despiked.RuX[12],despiked.RuY[12],despiked.RuZ[12]],down,1e-6);
  // A genuine fast throw is kept, but not faster than the cap.
  const throwing=make(Array.from({length:n},(_,i)=>i<15?down:up));
  const capped=limitArmSpeed(throwing,1200,30);
  const angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,a[0]*b[0]+a[1]*b[1]+a[2]*b[2])))*180/Math.PI;
  for(let i=1;i<n;i++)assert.ok(angle([capped.RuX[i],capped.RuY[i],capped.RuZ[i]],[capped.RuX[i-1],capped.RuY[i-1],capped.RuZ[i-1]])<=40.001);
  assert.ok(capped.RuY[n-1]>.99,'the arm still gets there');
});

test('closing the loop blends the end into the start',()=>{
  const columns={};for(const name of COLUMN_ORDER)columns[name]=Array.from({length:60},(_,i)=>i/60);
  const closed=closeLoop(columns,12);
  assert.equal(closed.roll.length,48,'the cross-faded frames are cut from the start');
  // The last frame hands over to the first with no more of a step than the clip itself has.
  assert.ok(Math.abs(closed.roll.at(-1)-closed.roll[0])<=1/60+1e-9,'no seam at the wrap-around');
  assert.equal(closed.roll[10],columns.roll[22],'frames before the blend are untouched');
});

test('generated module is a valid dance that reproduces the measured pose',async()=>{
  const frames=sequence(60,i=>dancer({R:{upper:[0,1,0],fore:[0,1,0]},L:{upper:[1,0,0],fore:[1,0,0]},ankles:[.15+.02*Math.sin(i/5),.15],lift:[i>30?.1:0,0]}));
  const poses=trackDancer(frames);
  const {columns}=measure(poses);
  const cleaned=closeLoop(clean(columns),6);
  const source=toModule({id:'synthetic-dance',label:'Điệu thử',bpm:120,fps:30,columns:cleaned,from:0});
  const module=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const def=validateDance(module.default);
  assert.equal(def.label,'Điệu thử');assert.equal(def.frames.length,54,'six cross-faded frames are cut');
  const pose=sampleDance(def,.5);
  near(pose.arms.R.upper,[0,1,0],.05);near(pose.arms.L.upper,[1,0,0],.05);
  assert.ok(sampleDance(def,1.5).feet.L.y>.03,'a lifted foot survives the round trip');
});
