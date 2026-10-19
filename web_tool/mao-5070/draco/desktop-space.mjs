import * as T from '../3d/vendor/three.module.js';
import {roomDestination} from './room-orientation.mjs';
const clamp=T.MathUtils.clamp,TAU=Math.PI*2;
const ease=t=>{t=clamp(t,0,1);return t*t*t*(10+t*(-15+6*t));};
const mix=(a,b,t)=>a+(b-a)*t;
const nearAngle=(from,to)=>from+Math.atan2(Math.sin(to-from),Math.cos(to-from));
export const PET_BOUNDS=Object.freeze({minX:-.42,maxX:.42,minZ:-.72,maxZ:.10});
const sideCurve=t=>{
  const keys=[[0,0],[.32,-.04],[1.05,.28],[1.55,.78],[2.20,1],[2.60,1]];
  for(let i=1;i<keys.length;i++)if(t<keys[i][0]){const [a,x]=keys[i-1],[b,y]=keys[i];return mix(x,y,ease((t-a)/(b-a)));}
  return 1;
};
export function desktopCommand(text){
  const original=String(text||'').toLowerCase();
  if(/(?:^|\s)đừng\s/.test(original))return null;
  const t=original.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
  if(/\b(?:dung lai|dung di|dung buoc|dung xoay|dung quay|stop)\b/.test(t))return 'stop';
  if(/\b(?:khong|dung|cho|chang)\b.{0,20}\b(?:xoay|quay|di|buoc)\b/.test(t))return null;
  const direction=t.match(/\b(?:di|buoc|tien)\s+(?:ve\s+|theo\s+|sang\s+|den\s+|toi\s+|huong\s+|phia\s+)*(bac|nam|dong|tay)\b/);
  if(direction)return {bac:'north',nam:'south',dong:'east',tay:'west'}[direction[1]];
  if(/\b(?:di|buoc|toi|den)\b.{0,22}\b(?:ban dj|san khau|cho dj)\b/.test(t))return 'dj';
  if(/\b(?:di|buoc|toi|den)\b.{0,22}\b(?:giua phong|giua san|trung tam)\b/.test(t))return 'center';
  if(/\b(?:di|buoc|toi|den)\b.{0,22}\b(?:ghe|lounge)\s+(?:ben\s+|phia\s+)?(?:tay|trai)\b/.test(t))return 'lounge-west';
  if(/\b(?:di|buoc|toi|den)\b.{0,22}\b(?:ghe|lounge)\s+(?:ben\s+|phia\s+)?(?:dong|phai)\b/.test(t))return 'lounge-east';
  if(/\b(?:xoay|quay)\s+(?:(?:cho (?:minh|toi)|giup (?:minh|toi))\s+)?(?:(?:1|mot)\s+vong|360(?:\s*do)?|tron\s+(?:1|mot)\s+vong)\b/.test(t))return 'spin';
  if(/\b(?:di|buoc)\s+(?:nhe\s+)?(?:(?:sang|qua|ve|ben)\s+)*(?:trai)\b/.test(t))return 'left';
  if(/\b(?:di|buoc)\s+(?:nhe\s+)?(?:(?:sang|qua|ve|ben)\s+)*(?:phai)\b/.test(t))return 'right';
  if(/\b(?:lui lai|di lui|di ra xa)\b/.test(t))return 'back';
  if(/\b(?:lai day|di toi|di len truoc)\b/.test(t))return 'forward';
  if(/\b(?:di lai|di dao|di qua di lai|di qua lai)\b/.test(t))return 'walk';
  return null;
}

// A bounded XZ stage for both the pet overlay and the room. Paths are eased
// in world space; spin is an unwrapped
// 2π turn so quaternion shortest-path interpolation cannot erase the rotation.
export class DesktopSpace{
  constructor({bounds=PET_BOUNDS,roam='pet',speed=.24}={}){this.bounds=bounds;this.roam=roam;this.walkSpeed=speed;this.x=0;this.z=0;this.yaw=0;this.audienceYaw=0;this.phase='idle';this.time=0;this.nextRoam=roam==='room'?8:16;this.serial=0;this.steps=[];this.elapsed=0;this.distance=0;this.gaitPhase=0;this.pose={speed:0,yawRate:0,yawAcceleration:0,acceleration:{x:0,z:0}};this.previousVelocity={x:0,z:0};this.completedSpins=0;}
  setAudienceYaw(yaw){if(!Number.isFinite(yaw))return false;this.audienceYaw=Math.atan2(Math.sin(yaw),Math.cos(yaw));return true;}
  enqueue(kind,x,z,yaw,duration){this.steps.push({kind,x:clamp(x,this.bounds.minX,this.bounds.maxX),z:clamp(z,this.bounds.minZ,this.bounds.maxZ),yaw,duration});}
  planWalk(x,z,faceViewer=true){
    x=clamp(x,this.bounds.minX,this.bounds.maxX);z=clamp(z,this.bounds.minZ,this.bounds.maxZ);
    const from=this.steps.at(-1)||this,dx=x-from.x,dz=z-from.z,distance=Math.hypot(dx,dz);
    if(distance<.015)return;
    const heading=nearAngle(from.yaw,Math.atan2(dx,dz)),turn=Math.abs(heading-from.yaw);
    if(turn>.08)this.enqueue('orient',from.x,from.z,heading,Math.max(.65,turn/1.65));
    // Feet get a brief weight-transfer beat before the first moving step.
    this.enqueue('weight-shift',from.x,from.z,heading,.25);
    this.enqueue('walk',x,z,heading,Math.max(1.6,distance/this.walkSpeed));
    this.enqueue('arrive',x,z,heading,.45);
    if(faceViewer){const front=nearAngle(heading,this.audienceYaw);if(Math.abs(front-heading)>.08)this.enqueue('face-viewer',x,z,front,Math.max(.65,Math.abs(front-heading)/1.65));this.enqueue('settle',x,z,front,.4);}
  }
  moveTo(x,z){if(!Number.isFinite(x)||!Number.isFinite(z))return false;if(Math.abs(z-this.z)<.015&&Math.abs(x-this.x)<=.20&&Math.abs(nearAngle(this.yaw,this.audienceYaw)-this.yaw)<.08)return this.stepAside(Math.sign(x-this.x),Math.abs(x-this.x));this.steps=[];this.planWalk(x,z);this.start();return true;}
  stepAside(direction,distance=.16){
    this.steps=[];const front=nearAngle(this.yaw,this.audienceYaw),x=clamp(this.x+direction*clamp(distance,0,.20),this.bounds.minX,this.bounds.maxX);
    if(Math.abs(front-this.yaw)>.08)this.enqueue('face-viewer',this.x,this.z,front,Math.max(.65,Math.abs(front-this.yaw)/1.65));
    if(Math.abs(x-this.x)>.015)this.enqueue('sidestep',x,this.z,front,2.6);
    this.start();return true;
  }
  perform(command){
    this.nextRoam=this.time+22;
    const destination=roomDestination(command,this.x,this.z);
    if(destination)return this.roam==='room'?this.moveTo(destination.x,destination.z):false;
    if(command==='stop'){this.steps=[];this.phase='idle';this.segment=null;this.sideStep=null;this.pose.speed=0;this.nextRoam=Infinity;return true;}
    if(command==='spin'){
      if(this.phase==='step-back'||this.phase==='spin'||this.steps.some(s=>s.kind==='spin'))return false;
      this.steps=[];const z=Math.max(this.bounds.minZ+.07,this.z-.42),x=clamp(this.x,this.bounds.minX+.2,this.bounds.maxX-.2);
      this.enqueue('step-back',x,z,this.yaw,2.4);
      this.enqueue('prepare',x,z,this.yaw,.35);
      this.enqueue('spin',x,z,this.yaw+TAU,4.2);
      this.enqueue('settle',x,z,this.yaw+TAU,.7);this.start();return true;
    }
    if(command==='left')return this.stepAside(-1);
    if(command==='right')return this.stepAside(1);
    if(command==='back')return this.moveTo(this.x,this.z-.28);
    if(command==='forward')return this.moveTo(this.x,this.z+.28);
    if(command==='walk'){this.steps=[];if(this.roam==='room'){this.planWalk(-1.8,-1.2,false);this.planWalk(1.8,-2.8,false);this.planWalk(0,-1.8,true);}else{this.planWalk(-.30,-.22,false);this.planWalk(.30,-.34,false);this.planWalk(0,-.18,true);}this.start();return true;}
    return false;
  }
  start(){
    const next=this.steps.shift();
    // Resolve the viewer at arrival, rather than keeping the camera bearing
    // recorded before a long walk. Never retarget a deliberate full spin.
    if(next?.kind==='face-viewer'){
      next.yaw=nearAngle(this.yaw,this.audienceYaw);next.duration=Math.max(.65,Math.abs(next.yaw-this.yaw)/1.65);
      if(['settle','sidestep'].includes(this.steps[0]?.kind))this.steps[0].yaw=next.yaw;
    }
    this.segment=next?{...next,fromX:this.x,fromZ:this.z,fromYaw:this.yaw}:null;this.phase=next?.kind||'idle';this.elapsed=0;this.sideStep=next?.kind==='sidestep'?{id:(this.sideSerial=(this.sideSerial||0)+1),fromX:this.x,fromZ:this.z,toX:next.x,yaw:next.yaw,time:0}:null;
  }
  predict(seconds){const s=this.segment;if(!s){const error=nearAngle(this.yaw,this.audienceYaw)-this.yaw;return {x:this.x,z:this.z,yaw:this.yaw+clamp(error*(1-Math.exp(-seconds*2.8)),-seconds*1.1,seconds*1.1)};}const p=ease((this.elapsed+seconds)/s.duration);return {x:mix(s.fromX,s.x,p),z:mix(s.fromZ,s.z,p),yaw:mix(s.fromYaw,s.yaw,p)};}
  update(dt,{enabled=true,paused=false}={}){
    dt=clamp(dt,0,.1);this.time+=dt;
    if(!enabled||paused){this.pose.speed=0;this.pose.yawRate=0;this.pose.yawAcceleration=0;this.pose.acceleration={x:0,z:0};this.previousVelocity={x:0,z:0};return this;}
    if(!this.segment&&this.time>=this.nextRoam){
      if(this.roam==='room'){const destinations=[[-1.8,-1.5],[1.9,-3.2],[2.3,-.6],[-2.2,-3.4],[0,-1.4]],point=destinations[this.serial++%destinations.length];this.moveTo(...point);}
      else{this.nextRoam=this.time+23;const side=(this.serial++%2?1:-1);if(this.serial%2)this.stepAside(side);else this.moveTo(side*.24,-.15-(this.serial%3)*.10);}
    }
    const oldX=this.x,oldZ=this.z,oldYaw=this.yaw,previousYawRate=this.pose.yawRate;
    if(this.segment){const s=this.segment;this.elapsed+=dt;const p=s.kind==='sidestep'?sideCurve(this.elapsed):ease(this.elapsed/s.duration);this.x=mix(s.fromX,s.x,p);this.z=mix(s.fromZ,s.z,p);this.yaw=s.kind==='sidestep'?s.yaw:mix(s.fromYaw,s.yaw,p);if(this.sideStep)this.sideStep.time=this.elapsed;
      if(this.elapsed>=s.duration){if(s.kind==='spin')this.completedSpins++;this.start();if(!this.segment){this.yaw=((this.yaw+Math.PI)%TAU+TAU)%TAU-Math.PI;this.nextRoam=this.time+(this.roam==='room'?12:22);}}
    }else{
      // Follow the audience only at rest. Feed this turn through the same gait
      // as walking so the feet replant instead of sliding under a rotated image.
      const error=nearAngle(this.yaw,this.audienceYaw)-this.yaw;
      const wanted=clamp(error*2.8,-1.1,1.1),rate=clamp(previousYawRate+clamp(wanted-previousYawRate,-dt*2.4,dt*2.4),-1.1,1.1);
      this.yaw+=Math.abs(rate*dt)>Math.abs(error)?error:rate*dt;
    }
    const vx=(this.x-oldX)/Math.max(dt,1e-6),vz=(this.z-oldZ)/Math.max(dt,1e-6);
    // Subtract the completed full turn before computing angular velocity.
    let dy=this.yaw-oldYaw;if(dy<-Math.PI)dy+=TAU;if(dy>Math.PI)dy-=TAU;
    const yawRate=dy/Math.max(dt,1e-6),travel=Math.hypot(this.x-oldX,this.z-oldZ);
    const speed=Math.hypot(vx,vz);
    this.distance+=travel;this.gaitPhase+=(travel/.34+Math.abs(dy)/Math.PI)*TAU;
    this.pose={speed,yawRate,yawAcceleration:clamp((yawRate-previousYawRate)/Math.max(dt,1e-6),-4,4),vx,vz,lookYaw:clamp(nearAngle(this.yaw,this.segment?.yaw??this.audienceYaw)-this.yaw,-.5,.5)*.55,prepare:this.phase==='weight-shift'?Math.sin(Math.PI*clamp(this.elapsed/.25,0,1)):0,acceleration:{x:clamp((vx-this.previousVelocity.x)/Math.max(dt,1e-6),-1,1),z:clamp((vz-this.previousVelocity.z)/Math.max(dt,1e-6),-1,1)}};
    this.previousVelocity={x:vx,z:vz};return this;
  }
}

// Plant each stance foot in floor space; only a swing foot changes its target.
// Convert the goals back into the stable skeleton simulation space for leg IK.
export class FloorFeet{
  constructor(rest){this.rest=rest;this.legs={};this.yaws={L:0,R:0};this.pitches={L:0,R:0};this.support=0;this.armSwing=0;this.idle=0;for(const side of ['L','R'])this.legs[side]={anchor:rest[side].clone(),point:rest[side].clone(),swing:false,yaw:0,pitch:0};}
  toFloor(point,space){return point.clone().applyAxisAngle(new T.Vector3(0,1,0),space.yaw).add(new T.Vector3(space.x,0,space.z));}
  updateSide(space,dt){
    const step=space.sideStep,direction=Math.sign(step.toX-step.fromX),t=step.time;
    if(this.sidePlan?.id!==step.id){
      const leading=['L','R'].sort((a,b)=>direction*(this.rest[b].x-this.rest[a].x))[0];
      this.sidePlan={id:step.id,leading,feet:{}};
      for(const side of ['L','R']){const leg=this.legs[side];this.sidePlan.feet[side]={from:leg.point.clone(),to:this.toFloor(this.rest[side],{x:step.toX,z:step.fromZ,yaw:step.yaw}),yaw:leg.yaw};leg.landing=null;}
    }
    const goals={};
    for(const side of ['L','R']){
      const leg=this.legs[side],plan=this.sidePlan.feet[side],leading=side===this.sidePlan.leading;
      const start=leading ? .32 : 1.55,end=leading ? 1.05 : 2.20,p=clamp((t-start)/(end-start),0,1);
      leg.point.copy(plan.from).lerp(plan.to,ease(p));leg.point.y+=Math.sin(Math.PI*p)**2*.025;
      leg.swing=p>0&&p<1;
      if(p>=1)leg.anchor.copy(plan.to);else if(p===0)leg.anchor.copy(plan.from);
      leg.yaw=mix(plan.yaw,nearAngle(plan.yaw,step.yaw),ease(p));leg.pitch*=Math.exp(-dt*14);
      this.yaws[side]=leg.yaw-space.yaw;this.pitches[side]=leg.pitch;
      goals[side]=leg.point.clone().sub(new T.Vector3(space.x,0,space.z)).applyAxisAngle(new T.Vector3(0,1,0),-space.yaw);
    }
    const support=t<.32?-direction*ease(t/.32):t<1.05?-direction:t<1.55?mix(-direction,direction,ease((t-1.05)/.50)):t<2.20?direction:direction*(1-ease((t-2.20)/.40));
    this.support=mix(this.support,support,1-Math.exp(-dt*12));this.armSwing*=Math.exp(-dt*10);this.idle=0;
    return goals;
  }
  update(space,dt){
    if(space.sideStep){this.wasSide=true;return this.updateSide(space,dt);}
    const moving=space.pose.speed>.002||Math.abs(space.pose.yawRate)>.01;
    if(this.wasSide){
      for(const side of ['L','R']){
        const leg=this.legs[side];leg.swing=false;leg.anchor.copy(leg.point);
        if(leg.point.y>this.rest[side].y+.003)leg.landing={from:leg.point.clone(),to:this.toFloor(this.rest[side],space),elapsed:0,yaw:leg.yaw,targetYaw:nearAngle(leg.yaw,space.yaw),pitch:leg.pitch,closing:false};
      }
      this.wasSide=false;
    }
    this.idle=moving?0:this.idle+dt;const feet={};
    for(const [index,side] of ['L','R'].entries()){
      const leg=this.legs[side],previousYaw=leg.yaw,cycle=((space.gaitPhase/TAU+index*.5)%1+1)%1,swing=moving&&cycle<.42;
      const home=this.toFloor(this.rest[side],space);
      const needsClose=!moving&&this.idle>.12&&!Object.values(this.legs).some(l=>l.landing)&&(leg.anchor.distanceTo(home)>.012||Math.abs(nearAngle(leg.yaw,space.yaw)-leg.yaw)>.12);
      if(!leg.landing&&(!moving&&leg.swing||needsClose))leg.landing={from:leg.point.clone(),to:home,elapsed:0,yaw:leg.yaw,targetYaw:nearAngle(leg.yaw,space.yaw),pitch:leg.pitch,closing:needsClose};
      if(leg.landing){
        const landing=leg.landing;landing.elapsed+=dt;const t=clamp(landing.elapsed/.34,0,1),p=ease(t);
        leg.point.copy(landing.from).lerp(landing.to,p);if(landing.closing)leg.point.y+=Math.sin(Math.PI*t)**2*.022;
        leg.yaw=mix(landing.yaw,landing.targetYaw,p);leg.pitch=mix(landing.pitch,0,p);leg.swing=false;
        if(t>=1){leg.anchor.copy(landing.to);leg.landing=null;}
      }else{
        if(swing&&!leg.swing){
          leg.from=leg.point.clone();leg.fromYaw=leg.yaw;leg.startCycle=cycle;
          // Predict touchdown plus half of the next stance. A fixed short time
          // lead used to plant both feet behind the moving hips.
          const translating=space.phase==='walk'||space.phase==='step-back';
          const lead=translating?clamp(.74*.34/Math.max(space.pose.speed,.01),.35,1.35):.20;
          const predicted=space.predict(lead);leg.target=this.toFloor(this.rest[side],predicted);leg.targetYaw=nearAngle(leg.yaw,predicted.yaw);
        }
        if(swing){
          const p=clamp((cycle-leg.startCycle)/Math.max(.42-leg.startCycle,.01),0,1);
          leg.point.copy(leg.from).lerp(leg.target,ease(p));leg.point.y+=Math.sin(Math.PI*p)**2*.040;
          leg.yaw=mix(leg.fromYaw,leg.targetYaw,ease(p));leg.pitch=mix(.14,-.12,ease(p));
        }else{
          if(leg.swing){leg.anchor.copy(leg.target);leg.yaw=leg.targetYaw;}
          leg.point.copy(leg.anchor);
          const contact=clamp((cycle-.42)/.58,0,1);
          leg.pitch=moving?-.12*(1-ease(contact/.22))+.16*ease((contact-.76)/.24):leg.pitch*Math.exp(-dt*12);
        }
        leg.swing=swing;
      }
      // Heel contact -> flat support -> toe-off, with ankle height compensation.
      if(!leg.swing&&!leg.landing)leg.point.y=this.rest[side].y+Math.sin(Math.abs(leg.pitch))*.055;
      feet[side]=leg.point.clone().sub(new T.Vector3(space.x,0,space.z)).applyAxisAngle(new T.Vector3(0,1,0),-space.yaw);
      const turn=leg.yaw-previousYaw;leg.yaw=previousYaw+clamp(Math.atan2(Math.sin(turn),Math.cos(turn)),-dt*6,dt*6);
      this.yaws[side]=leg.yaw-space.yaw;this.pitches[side]=leg.pitch;
    }
    const leftFree=this.legs.L.swing||!!this.legs.L.landing,rightFree=this.legs.R.swing||!!this.legs.R.landing;
    const support=leftFree&&!rightFree?-1:rightFree&&!leftFree?1:0;
    this.support=mix(this.support,support,1-Math.exp(-dt*12));
    const advance=(feet.L.z-this.rest.L.z)-(feet.R.z-this.rest.R.z);
    this.armSwing=mix(this.armSwing,clamp(advance/.20,-1,1),1-Math.exp(-dt*10));
    return feet;
  }
}

export function locomotionFrame(space,feet,dt){
  const goals=feet.update(space,dt),a=new T.Vector3(space.pose.acceleration.x,0,space.pose.acceleration.z).applyAxisAngle(new T.Vector3(0,1,0),-space.yaw);
  const velocity=new T.Vector3(space.pose.vx||0,0,space.pose.vz||0).applyAxisAngle(new T.Vector3(0,1,0),-space.yaw);
  return {speed:space.pose.speed,yawRate:space.pose.yawRate,yawAcceleration:space.pose.yawAcceleration,phase:space.gaitPhase,feet:goals,footYaw:feet.yaws,footPitch:feet.pitches,support:feet.support,armSwing:feet.armSwing,sidestep:!!space.sideStep,forwardSpeed:velocity.z,lookYaw:space.pose.lookYaw||0,prepare:space.pose.prepare||0,acceleration:a};
}
