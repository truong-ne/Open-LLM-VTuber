#!/usr/bin/env node
// Turns the pose landmarks of ONE dancer (MediaPipe Pose, image + world
// landmarks per frame) into a Mao choreography module for dance-body.mjs.
//
//   node scripts/dance_from_pose.mjs pose_raw.json out.mjs --id my-dance --label "My dance" --bpm 124
//
// Input: {fps, frames:[{i, poses:[{image:[[x,y,z,visibility]*33], world:[[x,y,z,visibility]*33]}]}]}
// where image x/y are normalised to a crop of --crop WxH source pixels around the dancer.
// The pose detector itself is not part of the repository; see doc/mao_dance.vi.md.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';

export const LM={NOSE:0,L_SH:11,R_SH:12,L_EL:13,R_EL:14,L_WR:15,R_WR:16,L_HIP:23,R_HIP:24,L_ANK:27,R_ANK:28};
const KEY=[LM.L_SH,LM.R_SH,LM.L_EL,LM.R_EL,LM.L_WR,LM.R_WR,LM.L_HIP,LM.R_HIP];
const deg=r=>r*180/Math.PI,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const smoothstep=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
const mean=a=>a.reduce((s,v)=>s+v,0)/Math.max(1,a.length);
const percentile=(values,p)=>{const s=[...values].sort((a,b)=>a-b);return s[clamp(Math.round((s.length-1)*p),0,s.length-1)];};
const median=values=>percentile(values,.5);
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]],dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=v=>{const n=Math.hypot(...v)||1;return [v[0]/n,v[1]/n,v[2]/n];};
const mid=(a,b)=>[(a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2];

// --- choosing the right person -------------------------------------------------
const quality=pose=>mean(KEY.map(i=>pose.image[i][3]));
const hipCentre=pose=>[(pose.image[LM.L_HIP][0]+pose.image[LM.R_HIP][0])/2,(pose.image[LM.L_HIP][1]+pose.image[LM.R_HIP][1])/2];

// One pose per frame (or null): the detection nearest to where the dancer was last
// seen, starting from `hint` (normalised crop coordinates of her hips).
const torsoHeight=pose=>Math.hypot(
  (pose.image[LM.L_SH][0]+pose.image[LM.R_SH][0]-pose.image[LM.L_HIP][0]-pose.image[LM.R_HIP][0])/2,
  (pose.image[LM.L_SH][1]+pose.image[LM.R_SH][1]-pose.image[LM.L_HIP][1]-pose.image[LM.R_HIP][1])/2);

// Every detection in a frame is a candidate (the neighbours in the crop are detected
// too). The dancer is the one nearest where she was, of a similar size; the search
// radius grows slowly while she is lost but never far enough to reach a neighbour.
export function trackDancer(frames,{hint=[.5,.45],minQuality=.35,baseJump=.07,growth=.015,maxJump=.18}={}){
  let last=null,lost=0;const sizes=[];
  return frames.map(frame=>{
    const reference=sizes.length?median(sizes.slice(-30)):null;
    const candidates=frame.poses.filter(p=>quality(p)>=minQuality).map(pose=>({pose,c:hipCentre(pose),size:torsoHeight(pose)}));
    const from=last||hint;
    let best=null,bestCost=Infinity,bestDistance=Infinity;
    for(const c of candidates){
      const d=Math.hypot(c.c[0]-from[0],c.c[1]-from[1]);
      // A person of another size (or a half-seen one) is unlikely to be her.
      const mismatch=reference?Math.abs(c.size-reference)/reference:0;
      if(mismatch>.45)continue;
      const cost=d+.1*mismatch;
      if(cost<bestCost){best=c;bestCost=cost;bestDistance=d;}
    }
    const allowed=last?Math.min(maxJump,baseJump+growth*lost):.2;
    if(!best||bestDistance>allowed){lost++;return null;}
    last=best.c;lost=0;sizes.push(best.size);return best.pose;
  });
}

// Detectors sometimes swap left and right (a twisting torso, crossing legs). Limbs
// cannot jump across the body between frames, so compare each frame with the
// previous one and swap a group whose labels fit better the other way round.
const SWAP_GROUPS=[[[11,12],[13,14],[15,16]],[[23,24],[25,26],[27,28]]];
export function fixSwaps(poses,{ratio:ratioLimit=.6,margin=.04}={}){
  const out=[];let previous=null;
  for(const pose of poses){
    if(!pose){out.push(null);continue;}
    let current=pose;
    if(previous){
      for(const group of SWAP_GROUPS){
        let same=0,swapped=0;
        for(const [l,r] of group){
          const d=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
          same+=d(current.image[l],previous.image[l])+d(current.image[r],previous.image[r]);
          swapped+=d(current.image[l],previous.image[r])+d(current.image[r],previous.image[l]);
        }
        if(swapped<same*ratioLimit&&same-swapped>margin){
          const swap=part=>{const copy=part.map(p=>p.slice());for(const [l,r] of group){copy[l]=part[r].slice();copy[r]=part[l].slice();}return copy;};
          current={image:swap(current.image),world:swap(current.world)};
        }
      }
    }
    out.push(current);previous=current;
  }
  return out;
}

// --- combining detector passes -------------------------------------------------
// The same frames run through the detector more than once (mirrored, shrunk) have
// independent errors. Each pass is tracked on its own; per landmark, the passes that
// agree are averaged by confidence, and a landmark they disagree on is trusted less.
export function mergePasses(passes,{agree=.035,sameDancer=.06}={}){
  const n=Math.max(...passes.map(p=>p.length));
  return Array.from({length:n},(_,i)=>{
    let poses=passes.map(p=>p[i]).filter(Boolean);
    if(!poses.length)return null;
    const centres=poses.map(hipCentre),cx=median(centres.map(c=>c[0])),cy=median(centres.map(c=>c[1]));
    poses=poses.filter((_,k)=>Math.hypot(centres[k][0]-cx,centres[k][1]-cy)<sameDancer);
    if(!poses.length)return null;
    const image=[],world=[];
    for(let j=0;j<poses[0].image.length;j++){
      // The passes that agree with each other, choosing the group the detector is most
      // sure of: when two passes see a raised arm and two a lowered one, the median would
      // put the elbow halfway, where it is in neither.
      const near=(p,q)=>Math.hypot(p.image[j][0]-q.image[j][0],p.image[j][1]-q.image[j][1])<=agree;
      let use=poses,best=-1;
      for(const p of poses){
        const group=poses.filter(q=>near(p,q)),score=group.reduce((s,q)=>s+q.image[j][3],0);
        if(score>best){best=score;use=group;}
      }
      const weights=use.map(p=>Math.max(.05,p.image[j][3])),total=weights.reduce((a,b)=>a+b,0);
      const average=(key,c)=>use.reduce((sum,p,k)=>sum+p[key][j][c]*weights[k],0)/total;
      const sure=mean(use.map(p=>p.image[j][3]))*use.length/poses.length;
      image.push([average('image',0),average('image',1),average('image',2),sure]);
      world.push([average('world',0),average('world',1),average('world',2),sure]);
    }
    return {image,world};
  });
}

// --- depth from bone length ----------------------------------------------------
// A single camera sees depth badly but sees how long a bone looks very well. A bone of
// length L that looks d long must reach sqrt(L²-d²) toward or away from the camera;
// only that sign is uncertain. The sign can only change while the bone crosses the
// picture plane (d close to L), so between two crossings it is held and decided by the
// detector's own depth estimate over the whole stretch, not frame by frame.
export const BONES={Lu:[11,13],Lf:[13,15],Ru:[12,14],Rf:[14,16],Lt:[23,25],Ls:[25,27],Rt:[24,26],Rs:[26,28]};
const CHAIN=[['Lu','Lf'],['Ru','Rf'],['Lt','Ls'],['Rt','Rs']];

// `fixes`: [{bone:'Lf', from, to, side:'front'|'back'}] in pose indices, for stretches
// whose sign was checked by eye against the video. Returns poses whose `world` is the
// rebuilt skeleton (crop pixels; x and y as in the image, z toward the camera) plus
// per-bone details for inspection.
export function liftPoses(poses,{crop=[150,213],fixes=[],cross=.4,lengthPercentile=.9,deadZone=.25,trust=.3,ramp=3}={}){
  const [cw,ch]=crop,valid=poses.filter(Boolean);
  const px=(p,j)=>[p.image[j][0]*cw,p.image[j][1]*ch];
  const length2=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]),length3=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
  // Which way the detector's depth axis points: the nose is in front of the shoulders.
  const forward=Math.sign(median(valid.map(p=>p.world[LM.NOSE][2]-mid(p.world[LM.L_SH],p.world[LM.R_SH])[2])))||1;
  // Image pixels per world unit, from the torso, which mostly faces the camera.
  const scale=percentile(valid.flatMap(p=>{
    const torso2=length2(mid(px(p,LM.L_SH),px(p,LM.R_SH)),mid(px(p,LM.L_HIP),px(p,LM.R_HIP)));
    const torso3=length3(mid(p.world[LM.L_SH],p.world[LM.R_SH]),mid(p.world[LM.L_HIP],p.world[LM.R_HIP]));
    return [torso2/torso3,length2(px(p,LM.L_SH),px(p,LM.R_SH))/length3(p.world[LM.L_SH],p.world[LM.R_SH])];
  }).filter(Number.isFinite),.7);
  const lengths={},details={};
  for(const [name,[a,b]] of Object.entries(BONES)){
    // Seen at full length at least now and then: a high percentile of how long it looks,
    // but never shorter than the detector's own 3D length (a bone that always points
    // somewhat toward the camera never shows its full length).
    const sureFrames=valid.filter(p=>Math.min(p.image[a][3],p.image[b][3])>=.5),use=sureFrames.length>20?sureFrames:valid;
    const seen=percentile(use.map(p=>length2(px(p,a),px(p,b))),lengthPercentile);
    const modelled=scale*median(use.map(p=>length3(p.world[a],p.world[b])));
    lengths[name]=Math.max(seen,modelled);
    const L=lengths[name];
    lengths[name+'Seen']=seen;lengths[name+'Modelled']=modelled;
    // Near the picture plane a few percent of noise in the seen length turns into a large
    // depth (the square root is steep there), so a small depth (below about `deadZone` of
    // the bone, 15°) is faded out; from twice that on it is kept exactly.
    const measured=poses.map(p=>{
      if(!p)return Number.NaN;
      const r=Math.sqrt(Math.max(0,1-(length2(px(p,a),px(p,b))/L)**2));
      return L*r*smoothstep(r/(2*deadZone));
    });
    const reach=measured;
    const guess=fillGaps(poses.map(p=>p?forward*scale*(p.world[b][2]-p.world[a][2]):Number.NaN));
    const sure=poses.map(p=>p?Math.min(p.image[a][3],p.image[b][3]):0);
    // A joint the detector has lost (a hand hidden behind the hip) is placed by guesswork,
    // often right next to its parent, which would read as a bone aimed at the camera.
    // There the detector's own 3D estimate, which comes from the whole body, is used
    // instead; between `trust` and twice it the two are blended.
    const belief=sure.map(s=>smoothstep((s-trust/2)/trust));
    const smooth=gaussian(guess,1.5),sign=new Array(poses.length).fill(1);
    for(let i=0;i<poses.length;){
      if(!(reach[i]>=cross*L)){sign[i]=Math.sign(smooth[i])||1;i++;continue;}
      let j=i;while(j<poses.length&&reach[j]>=cross*L)j++;
      let vote=0;for(let k=i;k<j;k++)vote+=guess[k]*Math.max(.05,sure[k]);
      for(let k=i;k<j;k++)sign[k]=Math.sign(vote)||1;
      i=j;
    }
    // A fix may also ask for a least depth (`min`, fraction of the bone), e.g. a hand that
    // must clear the back of the head.
    // The least depth ramps in and out over `ramp` frames, so a fix starts as a movement.
    const least=new Array(poses.length).fill(0),fixedAt=new Array(poses.length).fill(false);
    for(const fix of fixes)if(fix.bone===name&&fix.side)for(let k=Math.max(0,fix.from);k<=Math.min(poses.length-1,fix.to);k++){
      const edge=Math.min(k-fix.from,fix.to-k)+1;
      fixedAt[k]=true;sign[k]=fix.side==='back'?-1:1;least[k]=clamp(fix.min||0,0,.95)*L*smoothstep(edge/(ramp+1));
    }
    const depth=reach.map((r,k)=>{
      if(!Number.isFinite(r))return Number.NaN;
      const fixed=fixedAt[k],rebuilt=sign[k]*Math.max(r,least[k]);
      return fixed?rebuilt:rebuilt*belief[k]+clamp(guess[k],-L,L)*(1-belief[k]);
    });
    details[name]={length:L,reach,guess,sign,depth};
  }
  const lifted=poses.map((p,i)=>{
    if(!p)return null;
    // The torso keeps the detector's depth (it rarely turns far); limbs are rebuilt
    // outward from it, bone by bone.
    const world=p.world.map((w,j)=>[...px(p,j),forward*scale*w[2],w[3]]);
    for(const chain of CHAIN)for(const name of chain){
      const [a,b]=BONES[name],[x,y]=px(p,b);
      world[b]=[x,y,world[a][2]+details[name].depth[i],p.world[b][3]];
    }
    return {image:p.image,world};
  });
  return {poses:lifted,lengths,scale,details};
}

// --- axes ----------------------------------------------------------------------
// Detectors disagree about axis directions, so derive them from anatomy: her left
// shoulder is on +X, her head is above her hips, her nose is in front of her shoulders.
export function worldAxes(poses){
  const valid=poses.filter(Boolean);
  const sx=Math.sign(median(valid.map(p=>p.world[LM.L_SH][0]-p.world[LM.R_SH][0])))||1;
  const sy=Math.sign(median(valid.map(p=>p.world[LM.NOSE][1]-mid(p.world[LM.L_HIP],p.world[LM.R_HIP])[1])))||-1;
  // The nose is ahead of the shoulder line; "forward" is the side the nose lies on.
  const sz=Math.sign(median(valid.map(p=>p.world[LM.NOSE][2]-mid(p.world[LM.L_SH],p.world[LM.R_SH])[2])))||1;
  // sy: head above hips means up = sign(nose.y - hips.y); sz: forward = sign(nose.z - shoulders.z)
  return {x:sx,y:sy,z:sz};
}
const bodyPoint=(pose,index,axes)=>{const w=pose.world[index];return [w[0]*axes.x,w[1]*axes.y,w[2]*axes.z];};

// The torso's own axes, so an arm is described relative to her body, not the camera.
export function torsoFrame(pose,axes){
  const p=i=>bodyPoint(pose,i,axes);
  const up=norm(sub(mid(p(LM.L_SH),p(LM.R_SH)),mid(p(LM.L_HIP),p(LM.R_HIP))));
  const shoulders=sub(p(LM.L_SH),p(LM.R_SH));
  const left=norm(sub(shoulders,up.map(v=>v*dot(shoulders,up))));
  return {up,left,forward:cross(left,up)};
}
// Unit direction of a limb segment in the torso frame: x toward her left, y up, z forward.
export function limbDirection(vector,frame){
  return norm([dot(vector,frame.left),dot(vector,frame.up),dot(vector,frame.forward)]);
}

// --- smoothing -----------------------------------------------------------------
export function fillGaps(values){
  const out=[...values],n=out.length;
  let first=out.findIndex(Number.isFinite);
  if(first<0)return out.fill(0);
  for(let i=0;i<first;i++)out[i]=out[first];
  for(let i=first;i<n;){
    if(Number.isFinite(out[i])){i++;continue;}
    let j=i;while(j<n&&!Number.isFinite(out[j]))j++;
    const a=out[i-1],b=j<n?out[j]:a;
    for(let k=i;k<j;k++)out[k]=a+(b-a)*(k-i+1)/(j-i+1);
    i=j;
  }
  return out;
}
// Removes one-frame landmark swaps and spikes without rounding off real hits.
export function medianFilter(values,radius=2){
  return values.map((_,i)=>median(values.slice(Math.max(0,i-radius),Math.min(values.length,i+radius+1))));
}
// Hampel filter: a sample far from its neighbours' median (in robust standard
// deviations) is a detector glitch, so it is replaced by that median.
export function hampel(values,{radius=3,threshold=2.5,floor=1e-3}={}){
  return values.map((value,i)=>{
    const window=values.slice(Math.max(0,i-radius),Math.min(values.length,i+radius+1));
    const centre=median(window),spread=1.4826*median(window.map(v=>Math.abs(v-centre)));
    return Math.abs(value-centre)>threshold*Math.max(spread,floor)?centre:value;
  });
}
export function gaussian(values,sigma){
  if(sigma<=0)return [...values];
  const radius=Math.ceil(sigma*3),kernel=Array.from({length:radius*2+1},(_,k)=>Math.exp(-((k-radius)**2)/(2*sigma*sigma)));
  return values.map((_,i)=>{
    let sum=0,weight=0;
    for(let k=-radius;k<=radius;k++){const v=values[clamp(i+k,0,values.length-1)],w=kernel[k+radius];sum+=v*w;weight+=w;}
    return sum/weight;
  });
}
const rolling=(values,radius,reduce)=>values.map((_,i)=>reduce(values.slice(Math.max(0,i-radius),Math.min(values.length,i+radius+1))));

// --- measurement ---------------------------------------------------------------
// Limb directions are stored as vectors: an angle pair is singular when an arm points
// straight at the camera, and measurement noise there would spin the arm.
const ARM_COLUMNS=['R','L'].flatMap(side=>['u','f'].flatMap(part=>['X','Y','Z'].map(axis=>side+part+axis)));
export const COLUMN_ORDER=[...ARM_COLUMNS,'roll','yaw','turn','pitch','hip','drop','Lx','Ly','Lz','Rx','Ry','Rz'];

// Smallest rotation (as a 3x3 matrix, rows) taking unit vector a onto unit vector b.
export function rotationBetween(a,b){
  const v=cross(a,b),c=dot(a,b);
  if(c<-.999999)return [[-1,0,0],[0,-1,0],[0,0,1]];
  const k=1/(1+c),[x,y,z]=v;
  return [[1-k*(y*y+z*z),k*x*y-z,k*x*z+y],[k*x*y+z,1-k*(x*x+z*z),k*y*z-x],[k*x*z-y,k*y*z+x,1-k*(x*x+y*y)]];
}
const apply=(m,v)=>m.map(row=>dot(row,v));

// A smooth path through direction keyframes [[frame, unit vector], ...]: a cubic Hermite
// curve per segment (normalised back to unit length). A key in a held pose (the same
// direction as the key before or after it) is passed at rest, so the arm eases into and
// out of a hold; any other key is passed at the Catmull-Rom speed, so motion flows through
// it instead of turning at a constant rate and changing speed abruptly at each key.
export function keyCurve(keys){
  const same=(a,b)=>a&&b&&angleBetween(a,b)<1;
  const tangent=i=>{
    const [t,p]=keys[i],before=keys[i-1],after=keys[i+1];
    if(!before||!after||same(p,before[1])||same(p,after[1]))return [0,0,0];
    return [0,1,2].map(c=>(after[1][c]-before[1][c])/(after[0]-before[0]));
  };
  const tangents=keys.map((_,i)=>tangent(i));
  return frame=>{
    if(frame<=keys[0][0])return [...keys[0][1]];
    if(frame>=keys.at(-1)[0])return [...keys.at(-1)[1]];
    let i=0;while(frame>keys[i+1][0])i++;
    const [t0,p0]=keys[i],[t1,p1]=keys[i+1],h=t1-t0,s=(frame-t0)/h;
    const h00=2*s**3-3*s**2+1,h10=s**3-2*s**2+s,h01=-2*s**3+3*s**2,h11=s**3-s**2;
    return norm([0,1,2].map(c=>h00*p0[c]+h10*h*tangents[i][c]+h01*p1[c]+h11*h*tangents[i+1][c]));
  };
}

// One value per column and frame, in the units dance-body.mjs expects. `crop` is the
// crop size in source pixels (image landmarks are normalised to it). Limb depth is
// rebuilt from bone lengths first (liftPoses); `fixes` are depth signs checked by eye.
export function measure(input,{crop=[130,170],fps=30,minVisibility=.1,fixes=[]}={}){
  const lift=liftPoses(input,{crop,fixes}),poses=lift.poses;
  const axes=worldAxes(poses),[cw,ch]=crop;
  const px=(pose,i)=>[pose.image[i][0]*cw,pose.image[i][1]*ch];
  const valid=poses.filter(Boolean);
  // Body height in pixels, from nose to ankles.
  const height=median(valid.map(p=>(mid(px(p,LM.L_ANK),px(p,LM.R_ANK))[1]-px(p,LM.NOSE)[1])))/.84;
  const columns=Object.fromEntries(COLUMN_ORDER.map(name=>[name,poses.map(()=>Number.NaN)]));
  const raw=poses.map(pose=>{
    if(!pose)return null;
    const frame=torsoFrame(pose,axes),p=i=>bodyPoint(pose,i,axes);
    // A limb the detector is unsure of (partly hidden, smeared by motion blur) still
    // carries the motion, so it is kept with its confidence and only weighs less in the
    // smoothing; only a landmark it has practically given up on is dropped.
    const sure=(...indices)=>Math.min(...indices.map(i=>pose.image[i][3]));
    const arms={};
    for(const [side,sh,el,wr] of [['L',LM.L_SH,LM.L_EL,LM.L_WR],['R',LM.R_SH,LM.R_EL,LM.R_WR]]){
      const upper=sure(sh,el),fore=sure(el,wr);
      arms[side]={
        upper:upper>=minVisibility?limbDirection(sub(p(el),p(sh)),frame):null,upperSure:upper,
        fore:fore>=minVisibility?limbDirection(sub(p(wr),p(el)),frame):null,foreSure:fore
      };
    }
    return {arms,frame};
  });
  // The floor frame: the camera looks down a little, so "up" in the picture is not
  // quite vertical. Her average trunk direction is taken as vertical and every point is
  // turned by the same small rotation, which separates a foot placed forward (lower in
  // the picture) from a foot lifted off the floor.
  // Only the camera's pitch is taken out: a sideways average lean is hers, not the camera's.
  const ups=raw.filter(Boolean).map(r=>r.frame.up);
  const up0=norm([0,median(ups.map(u=>u[1])),median(ups.map(u=>u[2]))]);
  const level=rotationBetween(up0,[0,1,0]);
  const ground=(pose,i)=>apply(level,bodyPoint(pose,i,axes));
  const yawOf=(a,b)=>deg(Math.atan2(-(a[2]-b[2]),a[0]-b[0]));
  const parts=poses.map(pose=>{
    if(!pose)return null;
    const pelvis=mid(ground(pose,LM.L_HIP),ground(pose,LM.R_HIP)),neck=mid(ground(pose,LM.L_SH),ground(pose,LM.R_SH));
    const up=norm(sub(neck,pelvis));
    return {pelvis,ankleL:ground(pose,LM.L_ANK),ankleR:ground(pose,LM.R_ANK),
      roll:deg(Math.atan2(up[0],up[1])),pitch:deg(Math.atan2(up[2],up[1])),
      turn:yawOf(ground(pose,LM.L_HIP),ground(pose,LM.R_HIP)),
      yaw:yawOf(ground(pose,LM.L_SH),ground(pose,LM.R_SH))-yawOf(ground(pose,LM.L_HIP),ground(pose,LM.R_HIP))};
  });
  const confidence=Object.fromEntries(ARM_COLUMNS.map(name=>name.slice(0,2)).filter((p,i,all)=>all.indexOf(p)===i).map(prefix=>[prefix,poses.map(()=>0)]));
  raw.forEach((r,i)=>{
    if(!r)return;
    for(const side of ['R','L'])for(const [part,key] of [['u','upper'],['f','fore']]){
      const direction=r.arms[side][key];
      if(direction)['X','Y','Z'].forEach((axis,k)=>{columns[side+part+axis][i]=direction[k];});
      confidence[side+part][i]=direction?r.arms[side][key+'Sure']:0;
    }
  });
  // A direction checked by eye ({bone:'Lu', from, to, dir:[x,y,z]} in the body frame:
  // x to her left, y up, z forward) replaces what the detector saw, as a sure sample.
  // Keyframes ({bone, keys:[[frame,[x,y,z]], ...]}) set a move the detector cannot follow
  // (forearms swapping across the chest); between keys the direction turns evenly.
  const setDirection=(bone,k,d)=>{
    if(k<0||k>=poses.length)return;
    ['X','Y','Z'].forEach((axis,a)=>{columns[bone+axis][k]=d[a];});confidence[bone][k]=1;
  };
  for(const fix of fixes){
    if(!confidence[fix.bone])continue;
    if(fix.dir){const d=norm(fix.dir);for(let k=Math.max(0,fix.from);k<=Math.min(poses.length-1,fix.to);k++)setDirection(fix.bone,k,d);}
    if(fix.keys){
      const keys=[...fix.keys].sort((a,b)=>a[0]-b[0]).map(([frame,d])=>[frame,norm(d)]);
      const curve=keyCurve(keys);
      for(let k=keys[0][0];k<=keys.at(-1)[0];k++)setDirection(fix.bone,k,curve(k));
    }
  }
  parts.forEach((r,i)=>{if(r)for(const name of ['roll','yaw','turn','pitch'])columns[name][i]=r[name];});
  // Shoulder and hip landmarks sit at slightly different depths, and the camera may not
  // face her square on: her average twist, turn and lean are taken as zero.
  for(const name of ['yaw','turn','pitch']){const bias=median(columns[name].filter(Number.isFinite));columns[name]=columns[name].map(v=>v-bias);}
  // Floor, centre line and standing hip height drift slowly with the camera and her
  // travel, so they are tracked with wide windows instead of fixed numbers. In the
  // floor frame y is up and z toward the camera.
  const filled=pick=>fillGaps(parts.map(r=>r?pick(r):Number.NaN));
  const hipX=filled(r=>r.pelvis[0]),hipY=filled(r=>r.pelvis[1]),hipZ=filled(r=>r.pelvis[2]);
  const ankle={};
  for(const side of ['L','R'])ankle[side]=[0,1,2].map(k=>filled(r=>r['ankle'+side][k]));
  const floor=rolling(ankle.L[1].map((v,i)=>Math.min(v,ankle.R[1][i])),Math.round(fps*1.2),values=>percentile(values,.15));
  const centre=rolling(ankle.L[0].map((v,i)=>(v+ankle.R[0][i])/2),Math.round(fps*.7),mean);
  const standing=percentile(hipY.map((y,i)=>(y-floor[i])/height),.9);
  // Forward reach is measured from the pelvis; a foot's usual place under the body is zero.
  const reach=side=>ankle[side][2].map((z,i)=>(z-hipZ[i])/height);
  const neutral=median([...reach('L'),...reach('R')]),reachL=reach('L'),reachR=reach('R');
  // The detector places one ankle a little higher than the other (a flared hem, the
  // shoe), which would leave that foot hovering: each foot's usual height when it
  // stands is its own zero.
  const raised=side=>ankle[side][1].map((y,i)=>(y-floor[i])/height);
  const resting=side=>percentile(raised(side),.25),liftL=raised('L').map(v=>v-resting('L')),liftR=raised('R').map(v=>v-resting('R'));
  parts.forEach((r,i)=>{
    if(!r)return;
    columns.hip[i]=(hipX[i]-centre[i])/height;
    columns.drop[i]=standing-(hipY[i]-floor[i])/height;
    columns.Lx[i]=(ankle.L[0][i]-centre[i])/height;columns.Rx[i]=(centre[i]-ankle.R[0][i])/height;
    columns.Ly[i]=Math.max(0,liftL[i]);columns.Ry[i]=Math.max(0,liftR[i]);
    columns.Lz[i]=reachL[i]-neutral;columns.Rz[i]=reachR[i]-neutral;
  });
  return {columns,confidence,height,axes,lift};
}

// Per-column clean-up: fill gaps, drop single-frame spikes, then low-pass.
// Frames at 30 fps: sigma 1.2 is about 40 ms, short enough to keep a 3 Hz arm roll.
// Depth (Z) is the least reliable axis of a single camera, so it is smoothed harder.
const SIGMA={roll:2.5,yaw:3,turn:3,pitch:3,hip:2.5,drop:2.5,Lx:2,Rx:2,Ly:2,Ry:2,Lz:2.5,Rz:2.5,
  ...Object.fromEntries(ARM_COLUMNS.map(name=>[name,name.endsWith('Z')?1.6:1.2]))};
// Smoothing weight of a sample from the detector's confidence in it.
const weightOf=sure=>clamp((sure-.1)/.5,.03,1);
export function weightedGaussian(values,sigma,weights){
  const radius=Math.ceil(sigma*3),kernel=Array.from({length:radius*2+1},(_,k)=>Math.exp(-((k-radius)**2)/(2*sigma*sigma)));
  return values.map((_,i)=>{
    let sum=0,total=0;
    for(let k=-radius;k<=radius;k++){const j=clamp(i+k,0,values.length-1),w=kernel[k+radius]*weights[j];sum+=values[j]*w;total+=w;}
    return total>0?sum/total:values[i];
  });
}
const LIMITS={roll:[-30,30],yaw:[-45,45],turn:[-60,60],pitch:[-30,30],hip:[-.3,.3],drop:[-.1,.3],Lx:[-.5,.5],Rx:[-.5,.5],Ly:[-.1,.5],Ry:[-.1,.5],Lz:[-.5,.5],Rz:[-.5,.5],
  ...Object.fromEntries(ARM_COLUMNS.map(name=>[name,[-1,1]]))};
// `confidence` (optional): per arm segment ('Ru', 'Rf', ...) and frame, how sure the
// detector was. Unsure samples still count, but less. `maxArmSpeed` is only a safety
// net against glitches: a hard cap on real motion makes arms move at a constant rate
// and then stop dead, which reads as stiff.
export function clean(columns,{sigmaScale=1,fps=30,maxArmSpeed=2100,confidence=null}={}){
  const filled={};
  for(const name of COLUMN_ORDER)filled[name]=fillGaps(columns[name]);
  const despiked=bridgeUnsure(despikeDirections(despikeDirections(normalizeDirections(filled),1),2),confidence);
  const out={};
  for(const name of COLUMN_ORDER){
    let values=despiked[name];
    if(!ARM_COLUMNS.includes(name)){
      values=hampel(values,{radius:3,threshold:2.5,floor:['roll','yaw','turn','pitch'].includes(name)?.5:.02});
      values=medianFilter(values,1);
      values=gaussian(values,SIGMA[name]*sigmaScale);
    }else{
      const sure=confidence?.[name.slice(0,2)];
      values=sure?weightedGaussian(values,SIGMA[name]*sigmaScale,sure.map(weightOf)):gaussian(values,SIGMA[name]*sigmaScale);
    }
    const [low,high]=LIMITS[name];
    out[name]=values.map(v=>clamp(v,low,high));
  }
  return limitArmSpeed(normalizeDirections(out),maxArmSpeed,fps);
}

// --- direction vectors ---------------------------------------------------------
const ARM_PREFIXES=[...new Set(ARM_COLUMNS.map(name=>name.slice(0,2)))];
const angleBetween=(a,b)=>deg(Math.acos(clamp(a[0]*b[0]+a[1]*b[1]+a[2]*b[2],-1,1)));
const slerpUnit=(a,b,t)=>{
  const omega=Math.acos(clamp(a[0]*b[0]+a[1]*b[1]+a[2]*b[2],-1,1));
  if(omega<1e-6)return [...b];
  if(Math.PI-omega<1e-4){
    // Exactly opposite directions have no unique path: turn through any perpendicular.
    const axis=norm(cross(a,Math.abs(a[0])<.9?[1,0,0]:[0,0,1])),angle=t*Math.PI;
    return a.map((v,i)=>v*Math.cos(angle)+axis[i]*Math.sin(angle));
  }
  const sa=Math.sin((1-t)*omega)/Math.sin(omega),sb=Math.sin(t*omega)/Math.sin(omega);
  return [a[0]*sa+b[0]*sb,a[1]*sa+b[1]*sb,a[2]*sa+b[2]*sb];
};
const readDirections=(columns,prefix)=>columns[prefix+'X'].map((_,i)=>[columns[prefix+'X'][i],columns[prefix+'Y'][i],columns[prefix+'Z'][i]]);
const writeDirections=(columns,prefix,vectors)=>{
  columns[prefix+'X']=vectors.map(v=>v[0]);columns[prefix+'Y']=vectors.map(v=>v[1]);columns[prefix+'Z']=vectors.map(v=>v[2]);
};

// A sample far from both neighbours while the neighbours agree with each other is a
// detector glitch (a smeared wrist); replace it by the midpoint of its neighbours.
export function despikeDirections(columns,radius=1,{spike=55,agree=60}={}){
  const out={...columns};
  for(const prefix of ARM_PREFIXES){
    const vectors=readDirections(columns,prefix);
    for(let i=radius;i<vectors.length-radius;i++){
      const before=vectors[i-radius],after=vectors[i+radius];
      if(angleBetween(before,after)>agree)continue;
      // The `radius` samples between the neighbours are all suspect together.
      const far=[];for(let k=i;k<i+radius;k++)far.push(Math.min(angleBetween(before,vectors[k]),angleBetween(after,vectors[k])));
      if(Math.min(...far)>spike)for(let k=i;k<i+radius;k++)vectors[k]=slerpUnit(before,after,(k-i+1)/(radius+1));
    }
    writeDirections(out,prefix,vectors);
  }
  return out;
}

// Several unsure samples in a row (a hand blurred or leaving the frame) can outvote the
// sure ones around them in the smoothing. Between two sure samples (`anchor` or more,
// at most `maxGap` frames apart) an unsure sample that points more than `disagree`
// degrees away from the path between them is a glitch and takes that path instead. An
// unsure sample that agrees with it keeps its own value, so real motion seen only
// dimly (the hand roll at the start) survives.
export function bridgeUnsure(columns,confidence,{anchor=.35,maxGap=10,disagree=60}={}){
  const out={...columns};
  for(const prefix of ARM_PREFIXES){
    const sure=confidence?.[prefix];if(!sure)continue;
    const vectors=readDirections(columns,prefix);
    let last=-1;
    for(let i=0;i<vectors.length;i++){
      if(!(sure[i]>=anchor))continue;
      if(last>=0&&i-last>1&&i-last<=maxGap)for(let k=last+1;k<i;k++){
        const path=slerpUnit(vectors[last],vectors[i],(k-last)/(i-last));
        if(angleBetween(path,vectors[k])>disagree)vectors[k]=path;
      }
      last=i;
    }
    writeDirections(out,prefix,vectors);
  }
  return out;
}

// Real arms swing fast but not instantly: cap what is left after despiking.
export function limitArmSpeed(columns,maxDegPerSecond,fps){
  const out={...columns},step=maxDegPerSecond/fps;
  for(const prefix of ARM_PREFIXES){
    const vectors=readDirections(columns,prefix);
    for(let i=1;i<vectors.length;i++){
      const a=angleBetween(vectors[i-1],vectors[i]);
      if(a>step)vectors[i]=slerpUnit(vectors[i-1],vectors[i],step/a);
    }
    writeDirections(out,prefix,vectors);
  }
  return out;
}

// Averaging unit vectors shortens them where the direction changes quickly; turn every
// arm segment back into a unit vector, holding the last good one if it collapsed.
export function normalizeDirections(columns){
  const out={...columns};
  for(const prefix of ARM_PREFIXES){
    let last=[0,-1,0];
    writeDirections(out,prefix,readDirections(columns,prefix).map(v=>{
      const length=Math.hypot(...v);
      last=length>.05?[v[0]/length,v[1]/length,v[2]/length]:last;return last;
    }));
  }
  return out;
}

// Make the clip loop without a seam: cross-fade its last `frames` frames into its first
// ones and start the loop after them, so the final frame hands over to the frame that
// follows it in the original. The result is `frames` shorter than the input.
export function closeLoop(columns,frames=12){
  const out={};
  for(const name of COLUMN_ORDER){
    const v=[...columns[name]],n=v.length;
    for(let k=0;k<frames;k++){const t=(k+1)/frames,w=t*t*(3-2*t);v[n-frames+k]=v[n-frames+k]*(1-w)+v[k]*w;}
    out[name]=v.slice(frames);
  }
  return normalizeDirections(out);
}

export function toModule({id,label,bpm,fps,columns,from,comment='',reference=null}){
  const names=COLUMN_ORDER,n=columns[names[0]].length;
  const round=(name,v)=>['roll','yaw','turn','pitch'].includes(name)?Number(v.toFixed(1)):Number(v.toFixed(3));
  const rows=[];
  for(let i=from;i<n;i++){
    const row=names.map(name=>round(name,columns[name][i]));
    const last=i===n-1;
    rows.push(`    [${row.join(',')}]${last?'':','}`+(((i-from)%fps===0)?` // ${((i-from)/fps).toFixed(0)} s`:''));
  }
  return `${comment}export default {
  id:'${id}',
  label:${JSON.stringify(label)},
  bpm:${bpm},
  fps:${fps},
  loop:true,
  overlay:{bounce:0,sway:0},
${reference?`  reference:${JSON.stringify(reference)},\n`:''}  columns:${JSON.stringify(names)},
  frames:[
${rows.join('\n')}
  ]
};
`;
}

function main(argv){
  const [input,output,...flags]=argv;
  // --label may also be given as --label-file path, since shells mangle non-ASCII arguments.
  const option=(name,fallback)=>{
    if(name==='label'){const f=flags.indexOf('--label-file');if(f>=0)return fs.readFileSync(flags[f+1],'utf8').trim();}
    const i=flags.indexOf('--'+name);return i>=0?flags[i+1]:fallback;
  };
  if(!input||!output){console.error('usage: dance_from_pose.mjs pose.json[,pass2.json...] out.mjs --id slug --label text --bpm 124 [--crop 150x213] [--hint x,y] [--loop-blend 12] [--fixes depth.json]');process.exit(2);}
  // Several passes over the same frames (comma-separated files) are tracked one by one and merged.
  const passes=input.split(',').map(file=>JSON.parse(fs.readFileSync(file,'utf8')));
  const data=passes[0],fps=data.fps;
  const [cw,ch]=option('crop','150x213').split('x').map(Number),hint=option('hint','.53,.56').split(',').map(Number);
  const poses=mergePasses(passes.map(pass=>fixSwaps(trackDancer(pass.frames,{hint}))));
  const first=poses.findIndex(Boolean);
  if(first<0){console.error('no dancer was found');process.exit(1);}
  // --fixes: {"offset":17,"fixes":[{"bone":"Lf","from":84,"to":90,"side":"back"}, ...]}. Frames are
  // dance frames; `offset` is the pose-file frame of dance frame 0 (printed as startFrame).
  const fixFile=option('fixes',null)?JSON.parse(fs.readFileSync(option('fixes'),'utf8')):{fixes:[]};
  const toPose=frame=>frame+(fixFile.offset||0)-data.frames[0].i;
  const fixes=fixFile.fixes.map(f=>({...f,from:toPose(f.from??0),to:toPose(f.to??0),...(f.keys?{keys:f.keys.map(([frame,d])=>[toPose(frame),d])}:{})}));
  const {columns,confidence,height,axes}=measure(poses,{crop:[cw,ch],fps,fixes});
  const blend=Number(option('loop-blend',12));
  const cleaned=clean(columns,{fps,confidence});
  const trimmed=Object.fromEntries(COLUMN_ORDER.map(name=>[name,cleaned[name].slice(first)]));
  const looped=closeLoop(trimmed,blend);
  const missing=poses.slice(first).filter(p=>!p).length;
  // The loop starts after the cross-faded frames, so dance time 0 is a little later in the source.
  const start=data.frames[first+blend].i;
  const comment=`// Generated by scripts/dance_from_pose.mjs from ${poses.length-first} tracked frames at ${fps} fps\n// (${missing} filled by interpolation). Dance time 0 is source frame ${start}.\n`;
  // Where the dance sits in the original video, for the editor's side-by-side view:
  // --source-offset is the video time of the first extracted frame, --source-crop the
  // crop (x,y,w,h in video pixels) the frames were cut from.
  const sourceOffset=Number(option('source-offset',Number.NaN));
  const sourceCrop=option('source-crop',null)?.split(',').map(Number);
  const reference=Number.isFinite(sourceOffset)?{offset:Number((sourceOffset+(start-1)/fps).toFixed(4)),...(sourceCrop?.length===4?{crop:sourceCrop}:{})}:null;
  fs.writeFileSync(output,toModule({id:option('id','dance'),label:option('label','Dance'),bpm:Number(option('bpm',120)),fps,columns:looped,from:0,comment,reference}));
  console.log(JSON.stringify({startFrame:start,frames:poses.length-first-blend,missing,bodyHeightPx:Number(height.toFixed(1)),axes}));
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main(process.argv.slice(2));
