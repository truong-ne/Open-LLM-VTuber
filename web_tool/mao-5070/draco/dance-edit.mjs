// Pure helpers for hand-editing a choreography (dance-editor.html). They work on the
// plain rows of a dance file, so the result can be validated and saved as-is.
import {COLUMNS} from './dance-body.mjs?v=2';

const SIGN={L:1,R:-1};
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const rad=d=>d*Math.PI/180,deg=r=>r*180/Math.PI;

// An arm segment as two angles a person can read: direction in the frontal plane
// (0 = hanging down, 90 = out to the side, 180 = straight up, 270 = across the body
// toward the other side) and how far it points toward the audience (degrees).
export function vectorToAngles(side,[x,y,z]){
  const length=Math.hypot(x,y,z)||1;
  const forward=deg(Math.asin(clamp(z/length,-1,1)));
  let angle=deg(Math.atan2(SIGN[side]*x,-y));
  if(angle<0)angle+=360;
  return {angle,forward};
}
export function anglesToVector(side,angle,forward){
  const a=rad(angle),f=rad(forward);
  return [SIGN[side]*Math.sin(a)*Math.cos(f),-Math.cos(a)*Math.cos(f),Math.sin(f)];
}

const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const unit=v=>{const n=Math.hypot(...v)||1;return v.map(x=>x/n);};
// Rodrigues rotation of v about a unit axis.
const rotate=(v,axis,angle)=>{
  const c=Math.cos(angle),s=Math.sin(angle),k=cross(axis,v),d=dot(axis,v);
  return [0,1,2].map(i=>v[i]*c+k[i]*s+axis[i]*d*(1-c));
};

// Cosine falloff: full effect on the edited frame, fading to nothing `radius` frames away.
export function falloff(distance,radius){
  if(radius<=0)return distance===0?1:0;
  return Math.abs(distance)>radius?0:.5+.5*Math.cos(Math.PI*Math.abs(distance)/(radius+1));
}
// Frames touched by an edit at `frame`, with their weights (wrapping for a loop).
export function neighbourhood(frame,radius,count,loop=true){
  const out=[];
  for(let d=-radius;d<=radius;d++){
    let i=frame+d;
    if(loop)i=((i%count)+count)%count;else if(i<0||i>=count)continue;
    if(out.some(o=>o.index===i))continue;
    out.push({index:i,weight:falloff(d,radius)});
  }
  return out;
}

const column=(columns,name)=>{const c=columns.indexOf(name);if(c<0)throw new Error(`No column ${name}`);return c;};
export function readArm(rows,columns,prefix,frame){
  return ['X','Y','Z'].map(axis=>rows[frame][column(columns,prefix+axis)]);
}

// Turn an arm segment at `frame` to `target`, and its neighbours by the same turn
// scaled by the falloff, so the motion around the edit keeps its shape.
export function editArm(rows,columns,prefix,frame,target,{radius=6,loop=true}={}){
  const out=rows.map(r=>r.slice()),cx=column(columns,prefix+'X');
  const from=unit(readArm(rows,columns,prefix,frame)),to=unit(target);
  let axis=cross(from,to);const sin=Math.hypot(...axis),angle=Math.atan2(sin,dot(from,to));
  if(angle<1e-9)return out;
  axis=sin>1e-9?axis.map(v=>v/sin):unit(cross(from,Math.abs(from[0])<.9?[1,0,0]:[0,0,1]));
  for(const {index,weight} of neighbourhood(frame,radius,rows.length,loop)){
    if(!weight)continue;
    const v=rotate(unit(readArm(rows,columns,prefix,index)),axis,angle*weight);
    for(let k=0;k<3;k++)out[index][cx+k]=Number(clamp(v[k],-1,1).toFixed(4));
  }
  return out;
}

// Move a single number (lean, hip, a foot...) to `value` at `frame`, easing the change
// into the neighbours. Values stay inside the dance format's limits.
export function editValue(rows,columns,name,frame,value,{radius=6,loop=true}={}){
  const out=rows.map(r=>r.slice()),c=column(columns,name),[low,high]=COLUMNS[name];
  const delta=value-rows[frame][c];
  for(const {index,weight} of neighbourhood(frame,radius,rows.length,loop)){
    out[index][c]=Number(clamp(rows[index][c]+delta*weight,low,high).toFixed(name==='roll'||name==='yaw'?2:4));
  }
  return out;
}

// Frames whose values differ from the original (for marking the timeline).
export function changedFrames(original,edited,tolerance=1e-6){
  const out=[];
  edited.forEach((row,i)=>{if(row.some((v,c)=>Math.abs(v-original[i][c])>tolerance))out.push(i);});
  return out;
}

// Source text of a dance module, in the same layout scripts/dance_from_pose.mjs writes.
export function danceModuleText(def,rows,comment=''){
  const lines=rows.map((row,i)=>`    [${row.join(',')}]${i===rows.length-1?'':','}`+(i%def.fps===0?` // ${(i/def.fps).toFixed(0)} s`:''));
  const reference=def.reference?`  reference:${JSON.stringify(def.reference)},\n`:'';
  return `${comment}export default {
  id:${JSON.stringify(def.id)},
  label:${JSON.stringify(def.label||def.id)},
  bpm:${def.bpm},
  fps:${def.fps},
  loop:${def.loop!==false},
  overlay:${JSON.stringify(def.overlay||{bounce:0,sway:0})},
${reference}  columns:${JSON.stringify(def.columns)},
  frames:[
${lines.join('\n')}
  ]
};
`;
}
