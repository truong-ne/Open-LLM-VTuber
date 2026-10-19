import * as T from '../3d/vendor/three.module.js';
import {GarmentDynamics} from './secondary.mjs';
import {prepareGarmentRig,clothBoneName} from './garment-rig.mjs';
import {SkirtClearance} from './skirt-clearance.mjs?v=3';

import {ACTIONS,STORY_ACTIONS} from './actions.mjs';
export {ACTIONS} from './actions.mjs';
export const BOW_ANGLE=Math.PI/6;
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v);return v*v*v*(v*(v*6-15)+10);};
const track=(t,keys)=>{if(t<=keys[0][0])return keys[0][1];for(let i=1;i<keys.length;i++)if(t<keys[i][0]){const [a,x]=keys[i-1],[b,y]=keys[i];return T.MathUtils.lerp(x,y,smooth((t-a)/(b-a)));}return keys.at(-1)[1];};
const hash=n=>{const v=Math.sin(n*127.1+311.7)*43758.5453;return (v-Math.floor(v))*2-1;};
const drift=(t,seed,period=3.7)=>{const n=Math.floor(t/period),f=smooth(t/period-n);return T.MathUtils.lerp(hash(n+seed*83),hash(n+1+seed*83),f);};
const pulse=(t,start,peak,hold,end)=>track(t,[[start,0],[peak,1],[hold,1],[end,0]]);
const faceHand={offset:[.075,-.100,.12],along:[-.65,.75,0],normal:[0,0,-1]};
const HAND_POSES={
  chuckle:{L:faceHand},
  laugh:{L:faceHand,R:{offset:[-.045,-.31,.19],along:[1,.12,-.06],normal:[0,0,-1]}},
  think:{R:{offset:[-.065,-.14,.16],along:[.2,1,0],normal:[0,.15,-1]}},
  // A hand resting diagonally against the chest: fingertips incline inward,
  // with wrist flexion and relaxed fingers. Merely rolling
  // the palm leaves the fingers upright and floating in front of the torso.
  shy:{L:{anchor:'chest',offset:[.075,-.005,.17],along:[-.95,.28,-.5],normal:[0,0,-1],pole:[.8,-.6,.35]}},
  reassure:{R:{anchor:'chest',offset:[-.075,-.005,.17],along:[.95,.28,-.5],normal:[0,0,-1],pole:[-.8,-.6,.35]}},
  emphasize:{R:{offset:[-.19,-.16,.16],along:[0,1,0],normal:[.3,0,1]}}
};

export class BodyActor{
  constructor(asset){
    prepareGarmentRig(asset);
    this.asset=asset;this.time=0;this.accumulator=0;this.action='idle';this.started=0;this.state=new Map();this.from=new Map();this.rms=0;
    asset.updateMatrixWorld(true);this.bones=[];this.rest=new Map();
    asset.traverse(b=>{if(!b.isBone)return;this.bones.push(b);const world=b.getWorldQuaternion(new T.Quaternion());this.rest.set(b,{position:b.position.clone(),quaternion:b.quaternion.clone(),world,worldInverse:world.clone().invert(),worldPosition:b.getWorldPosition(new T.Vector3())});});
    this.joints={};for(const name of ['waist','spine','chest','neck','head','pelvis','clavicleL','upperL','elbowL','wristL','clavicleR','upperR','elbowR','wristR','thighL','kneeL','ankleL','thighR','kneeR','ankleR']){const b=asset.getObjectByName(`draco_${name}`);if(!b?.isBone)throw new Error(`Thiếu khớp ${name}`);this.joints[name]=b;}
    this.feet={};this.legs={};
    this.arms={};this.reachPoses={L:faceHand,R:HAND_POSES.think.R};this.handGoals={};
    for(const side of ['L','R']){
      const [h,k,f]=['thigh','knee','ankle'].map(n=>this.rest.get(this.joints[n+side]).worldPosition);
      this.feet[side]=f.clone();this.legs[side]={a:h.distanceTo(k),b:k.distanceTo(f),upper:k.clone().sub(h).normalize(),lower:f.clone().sub(k).normalize()};
      const [shoulder,elbow,hand]=['upper','elbow','wrist'].map(n=>this.rest.get(this.joints[n+side]).worldPosition);
      this.arms[side]={a:shoulder.distanceTo(elbow),b:elbow.distanceTo(hand),upper:elbow.clone().sub(shoulder).normalize(),lower:hand.clone().sub(elbow).normalize()};
    }
    this.palms={};
    this.forearms={L:asset.getObjectByName('draco_bone_0080'),R:asset.getObjectByName('draco_bone_0167')};
    this.rollHelpers={L:[117,119,121],R:[204,206,208]};
    this.rollBones={};this.clothRollBones={};this.fingers={};
    for(const side of ['L','R']){
      this.rollBones[side]=this.rollHelpers[side].map(id=>asset.getObjectByName(`draco_bone_${String(id).padStart(4,'0')}`));
      this.clothRollBones[side]=(side==='L'?[80,117,119,121]:[167,204,206,208]).map(id=>asset.getObjectByName(clothBoneName(id)));
      this.fingers[side]=Array.from({length:5},(_,digit)=>Array.from({length:3},(_,segment)=>asset.getObjectByName(`draco_finger${side}${digit}_${segment}`)));
      const at=name=>this.rest.get(asset.getObjectByName(name)).worldPosition;
      const wrist=at(`draco_wrist${side}`),index=at(`draco_finger${side}1_0`),middle=at(`draco_finger${side}2_0`),pinky=at(`draco_finger${side}4_0`);
      const along=middle.clone().sub(wrist).normalize(),normal=pinky.clone().sub(index).cross(along).normalize();
      if(normal.x*(side==='L'?-1:1)<0)normal.negate();this.palms[side]={along,normal};
    }
    this.fingerAxes=new Map();
    for(const side of ['L','R'])for(let digit=0;digit<5;digit++)for(let segment=0;segment<3;segment++){
      const bone=this.fingers[side][digit][segment];
      const child=bone.children.find(b=>b.isBone);if(!child)continue;
      const direction=this.rest.get(child).worldPosition.clone().sub(this.rest.get(bone).worldPosition).normalize();
      this.fingerAxes.set(bone,{flex:direction.cross(this.palms[side].normal).normalize(),spread:this.palms[side].normal});
    }
    this.dynamics=new GarmentDynamics(this);
    this.skirtClearance=new SkirtClearance(this);
    this.delta=new T.Quaternion();this.euler=new T.Euler(0,0,0,'XYZ');this.audit={footDrift:0};
  }
  play(action){if(!ACTIONS.includes(action))return false;this.from=new Map([...this.state].map(([k,s])=>[k,s.x]));this.action=action;this.started=this.time;return true;}
  setLocomotion(value){this.locomotion=value;}
  spring(key,target,dt,f=2.7,damping=.95){
    if(this.from.has(key)&&this.time-this.started<.65)target=T.MathUtils.lerp(this.from.get(key),target,smooth((this.time-this.started)/.65));
    const s=this.state.get(key)||{x:0,v:0};const w=2*Math.PI*f;s.v+=(w*w*(target-s.x)-2*damping*w*s.v)*dt;s.x+=s.v*dt;this.state.set(key,s);return s.x;
  }
  rotateBone(b,x=0,y=0,z=0){
    const r=this.rest.get(b);this.delta.setFromEuler(this.euler.set(x,y,z));
    b.quaternion.copy(r.quaternion).multiply(r.worldInverse.clone().multiply(this.delta).multiply(r.world));
  }
  curlFinger(b,angle,spread){
    const axes=this.fingerAxes.get(b);if(!axes)return;
    const r=this.rest.get(b),q=new T.Quaternion().setFromAxisAngle(axes.spread,spread)
      .multiply(new T.Quaternion().setFromAxisAngle(axes.flex,angle));
    b.quaternion.copy(r.quaternion).multiply(r.worldInverse.clone().multiply(q).multiply(r.world));
  }
  update(dt,rms=0){this.rms=clamp(Number.isFinite(rms)?rms:0);this.accumulator+=clamp(Number.isFinite(dt)?dt:0,0,.1);let stepped=false;while(this.accumulator+1e-10>=1/120){this.step(1/120);this.accumulator-=1/120;stepped=true;}if(stepped)this.skirtClearance.update();}
  step(dt){
    this.time+=dt;const t=this.time,a=t-this.started;
    const duration=this.action==='nod'?3.7:this.action==='talk'?7.1:6.6;
    const on=name=>this.action===name?1:0;
    const s=(key,target,f=2.7,damping=.95)=>this.spring(key,target,dt,f,damping);
    const pose={};
    const add=(name,x=0,y=0,z=0)=>{const p=pose[name]||(pose[name]=[0,0,0]);p[0]+=x;p[1]+=y;p[2]+=z;};
    const rotation=(name,x,y,z,f=2.7)=>{const p=pose[name]||[0,0,0];this.rotateBone(this.joints[name],s(name+'X',x+p[0],f),s(name+'Y',y+p[1],f),s(name+'Z',z+p[2],f));};
    for(const b of this.bones){const r=this.rest.get(b);b.position.copy(r.position);b.quaternion.copy(r.quaternion);}
    // Prepare -> stroke -> hold -> settle. Each limb follows its own timing;
    // speech is a sequence of thoughts, rather than a bilateral sine wave.
    const greeting=on('greet'),talk=on('talk');
    const lift=greeting*pulse(a,.22,1.48,3.7,5.6);
    const elbowLift=greeting*pulse(a,.42,1.66,3.72,5.34);
    const wave=greeting*pulse(a,1.65,1.94,3.45,3.88)*Math.sin((a-1.9)*6.8);
    const accent=clamp(this.rms*3.5);
    const emphasis=.80+accent*.20;
    const left=talk*(pulse(a,.42,1.38,1.9,2.95)*.88+pulse(a,4.35,4.95,5.22,6.45)*.43)*emphasis;
    const right=talk*(pulse(a,2.15,3.1,3.58,4.65)*.88+pulse(a,4.5,5.1,5.37,6.6)*.38)*emphasis;
    const leftElbow=talk*(pulse(a,.56,1.53,1.98,3.03)*.88+pulse(a,4.48,5.1,5.3,6.5)*.43)*emphasis;
    const rightElbow=talk*(pulse(a,2.29,3.26,3.68,4.78)*.88+pulse(a,4.64,5.24,5.47,6.68)*.38)*emphasis;
    const weight=on('shift')*track(a,[[0,0],[.45,-.12],[1.9,.85],[3.1,.85],[4.8,-.65],[5.45,-.65],[6.6,0]]);
    const bow=on('bow')*pulse(a,.3,1.9,2.8,5.3);
    const turn=on('turn')*track(a,[[0,0],[.25,0],[1.25,1],[2.5,1],[4,-.7],[4.9,-.7],[6.3,0]]);
    const breath=Math.sin(t*1.46)+.18*Math.sin(t*2.92+.6);
    const gait=this.locomotion,walking=clamp((gait?.speed||0)*4+Math.abs(gait?.yawRate||0)*.16+(gait?.sidestep ? .4 : 0)),stride=(gait?.armSwing??Math.sin(gait?.phase||0))*walking;
    const support=(gait?.support||0)*walking,prepare=gait?.prepare||0,hipTwist=-stride*.045;
    const smallWeight=drift(t,2,6.8)*.007;
    const emotion={};for(const name of STORY_ACTIONS)emotion[name]=on(name)*pulse(a,.18,1.15,3.7,5.95);
    const {chuckle,laugh,surprise,think,shy,sad,shrug,emphasize,reassure,celebrate}=emotion;
    const jolt=[1.45,1.93,2.44,2.99,3.49].reduce((v,at,i)=>v+Math.exp(-Math.pow((a-at)/.105,2))*(1-i*.13),0);
    const laughter=(chuckle*.55+laugh)*jolt;
    add('spine',chuckle*.022+laugh*.050+sad*.035+shy*.015);
    add('chest',laugh*.020+laughter*.022+sad*.045,0,chuckle*-.012+shy*-.014);
    add('neck',laugh*-.020+surprise*-.02);
    add('head',chuckle*.025+laugh*.015+laughter*.014-surprise*.07+think*.025+shy*.075+sad*.13,
      think*-.04+shy*-.095,think*.065+shy*-.045+reassure*-.065);
    add('clavicleL',-laughter*.016,0,shrug*.08+surprise*.028+celebrate*.035-sad*.016);
    add('clavicleR',-laughter*.018,0,-shrug*.08-surprise*.028-celebrate*.03+sad*.016);
    add('upperL',-surprise*.18-shrug*.23-sad*.04-reassure*.16,0,
      surprise*.22+shrug*.23+celebrate*.39+reassure*.14);
    add('upperR',-surprise*.20-shrug*.22-sad*.04,0,-surprise*.22-shrug*.23-celebrate*.37);
    add('elbowL',-surprise*.22-shrug*.30-sad*.14-reassure*.34,0,
      surprise*1.15+shrug*.77+celebrate*1.38+reassure*.44);
    add('elbowR',-surprise*.24-shrug*.29-sad*.15,0,-surprise*1.1-shrug*.74-celebrate*1.35);
    add('wristL',-surprise*.10-shrug*.15,0,celebrate*.09);
    add('wristR',-surprise*.11-shrug*.15,0,-celebrate*.09);
    const joyBounce=celebrate*(Math.exp(-Math.pow((a-1.65)/.22,2))+Math.exp(-Math.pow((a-2.35)/.25,2))*.65);
    const waist=this.joints.waist;
    waist.position.x+=s('weightX',smallWeight+weight*.020+lift*.007+(left-right)*.003+support*.014-prepare*.008,gait?.feet?1.7:1.25);
    waist.position.y+=s('dropY',-.0035-bow*.008-Math.abs(weight)*.002+breath*.0006-laughter*.0018+joyBounce*.0018-walking*.028+walking*Math.cos((gait?.phase||0)*2)*.006-prepare*.004,gait?.feet?1.8:1.5);
    waist.position.z+=s('bowBalanceZ',-bow*.028,1.65);
    // A 30-degree trunk bow, led from the hips. Small spine contributions
    // keep the back from folding sharply at one joint.
    rotation('waist',bow*BOW_ANGLE*.70+drift(t,3,5.1)*.003+clamp((gait?.forwardSpeed||0)*.10,-.035,.045),turn*.045,-weight*.021-support*.012,1.65);
    // Waist is a common ancestor of the trunk and pelvis on this rig. Cancel
    // its pitch on the pelvis branch so the skirt stays around the thighs.
    rotation('pelvis',-.006-bow*BOW_ANGLE*.70,weight*.018+hipTwist,-weight*.023-smallWeight*.45+support*.018,1.65);
    rotation('spine',bow*BOW_ANGLE*.22+breath*.0028,turn*.065+(right-left)*.016-hipTwist*.45,weight*.023+smallWeight*.35+support*.007,1.9);
    rotation('chest',bow*BOW_ANGLE*.08+breath*.0035,turn*.08+(right-left)*.025-hipTwist*.65,weight*.012-lift*.012+support*.006,2.05);
    rotation('neck',bow*.035+talk*.004,turn*.015,drift(t,4,4.2)*.004,2.5);
    const nod=on('nod')*track(a,[[0,0],[.4,-.035],[.86,.135],[1.37,-.018],[1.86,.065],[2.65,0],[3.7,0]]);
    const listen=talk*(pulse(a,1.45,1.69,1.77,2.22)*.018+pulse(a,3.47,3.74,3.82,4.32)*.014);
    rotation('head',nod+bow*.045+listen+drift(t,5,4.7)*.009,
      turn*.24+drift(t,6,3.1)*.025+(right-left)*.027+(gait?.lookYaw||0),
      -lift*.038+talk*.012+drift(t,7,4.9)*.009,2.6);
    // Shoulder initiates the gesture; elbow and wrist settle slightly later.
    rotation('clavicleL',-lift*.025,0,lift*.035+left*.012,2.4);
    rotation('clavicleR',-right*.016,0,-right*.020,2.3);
    rotation('upperL',-.045-left*.25-bow*.38+greeting*pulse(a,.03,.23,.28,.65)*.035+stride*.25*(1-Math.max(lift,left)*.8),
      left*-.035,-.50+lift*1.04+left*.24,2.35);
    rotation('elbowL',-.10-leftElbow*.56,0,elbowLift*1.91+leftElbow*.68,2.7);
    rotation('wristL',-.025-leftElbow*.20,lift*.055,lift*.025+wave*.14,2.45);
    rotation('upperR',-.065-right*.28-bow*.38-stride*.25*(1-right*.8),right*.03,.47-right*.25,2.3);
    rotation('elbowR',-.105-rightElbow*.62,0,-rightElbow*.69,2.6);
    rotation('wristR',-.018-rightElbow*.22,rightElbow*.08,-rightElbow*.035,2.35);
    for(const side of ['L','R']){
      const open=Math.max(side==='L'?Math.max(lift,leftElbow*.82):rightElbow*.82,surprise*.8,shrug*.8,reassure*.6);
      for(let digit=0;digit<5;digit++)for(let segment=0;segment<3;segment++){
        const b=this.fingers[side][digit][segment];if(!b)continue;
        const point=side==='R'?emphasize:0;
        const curl=s(`curl${side}${digit}_${segment}`,
          (1-open)*(.09+digit*.012)*(segment===0?.65:1)+(digit===0?.018:0)
          +celebrate*.62+point*(digit===1?-.09:.34)+(think&&side==='R'&&digit>1?think*.70:0),3.1);
        this.curlFinger(b,curl*(digit===0?.55:1),segment===0&&digit>0?(digit-2.5)*open*.014*(side==='L'?1:-1):0);
      }
    }
    this.facePalm('L',Math.max(lift,leftElbow*.78,shrug*.72,reassure*.6,surprise*.85),lift>.001||surprise>.001?new T.Vector3(0,0,1):new T.Vector3(0,1,.35));
    this.facePalm('R',Math.max(rightElbow*.78,shrug*.72,surprise*.85),surprise>.001?new T.Vector3(0,0,1):new T.Vector3(0,1,.35));
    for(const side of ['L','R']){
      const profile=HAND_POSES[this.action]?.[side];if(profile)this.reachPoses[side]=profile;
      this.reachArm(side,this.reachPoses[side],profile?emotion[this.action]:0);
    }
    this.solveFeet();this.dynamics.step(dt);this.asset.updateMatrixWorld(true);
    this.audit.cloth=this.dynamics.audit;
    if(a>duration+.35&&this.action!=='idle')this.play('idle');
  }
  reachArm(side,profile,amount){
    const alpha=this.spring('reach'+side,amount,1/120,2.1,.98);
    const local=new T.Vector3(...profile.offset.map((v,i)=>this.spring(`reach${side}${i}`,v,1/120,2.1,.98)));
    const handAlong=new T.Vector3(...profile.along);
    handAlong.fromArray(handAlong.toArray().map((v,i)=>this.spring(`handDir${side}${i}`,v,1/120,2.4,.98)));
    const pole=new T.Vector3(...(profile.pole||[side==='L'?.65:-.65,-1,.45]).map((v,i)=>this.spring(`reachPole${side}${i}`,v,1/120,2.1,.98)));
    if(alpha<.00001){delete this.handGoals[side];return;}
    this.asset.updateMatrixWorld(true);
    const upper=this.joints['upper'+side],elbow=this.joints['elbow'+side],wrist=this.joints['wrist'+side],arm=this.arms[side];
    const affected=[upper,elbow];
    const before=affected.map(b=>b.quaternion.clone());
    const head=this.joints.head,chest=this.joints.chest;
    const anchorMix=this.spring('reachAnchor'+side,profile.anchor==='chest'?1:0,1/120,2.1,.98);
    const headChange=head.getWorldQuaternion(new T.Quaternion()).multiply(this.rest.get(head).worldInverse);
    const chestChange=chest.getWorldQuaternion(new T.Quaternion()).multiply(this.rest.get(chest).worldInverse);
    const anchorChange=headChange.slerp(chestChange,clamp(anchorMix));
    const target=head.getWorldPosition(new T.Vector3()).lerp(chest.getWorldPosition(new T.Vector3()),clamp(anchorMix)).add(local.multiplyScalar(this.dynamics.unit).applyQuaternion(anchorChange));
    const shoulder=upper.getWorldPosition(new T.Vector3()),axis=target.clone().sub(shoulder);
    const distance=clamp(axis.length(),Math.abs(arm.a-arm.b)+.001,arm.a+arm.b-.001);axis.normalize();
    const along=(arm.a**2-arm.b**2+distance**2)/(2*distance),height=Math.sqrt(Math.max(0,arm.a**2-along**2));
    pole.addScaledVector(axis,-pole.dot(axis)).normalize();
    const bend=shoulder.clone().addScaledVector(axis,along).addScaledVector(pole,height);
    const aim=(bone,direction,restDir)=>{
      const world=new T.Quaternion().setFromUnitVectors(restDir,direction.normalize()).multiply(this.rest.get(bone).world);
      bone.quaternion.copy(bone.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(world);bone.updateWorldMatrix(false,true);
    };
    aim(upper,bend.clone().sub(shoulder),arm.upper);aim(elbow,target.clone().sub(bend),arm.lower);
    affected.forEach((b,i)=>{const result=b.quaternion.clone();b.quaternion.copy(before[i]).slerp(result,clamp(alpha));});
    this.asset.updateMatrixWorld(true);
    wrist.updateWorldMatrix(true,false);
    const current=wrist.getWorldQuaternion(new T.Quaternion()),change=current.clone().multiply(this.rest.get(wrist).worldInverse);
    const alongNow=this.palms[side].along.clone().applyQuaternion(change);
    handAlong.normalize().applyQuaternion(anchorChange);
    const forearmAxis=wrist.getWorldPosition(new T.Vector3()).sub(elbow.getWorldPosition(new T.Vector3())).normalize();
    const bendAngle=Math.acos(clamp(forearmAxis.dot(handAlong),-1,1)),maxBend=T.MathUtils.degToRad(52);
    if(bendAngle>maxBend){const q=new T.Quaternion().setFromUnitVectors(forearmAxis,handAlong);q.slerp(new T.Quaternion(),1-maxBend/bendAngle);handAlong.copy(forearmAxis).applyQuaternion(q);}
    const align=new T.Quaternion().setFromUnitVectors(alongNow,handAlong);
    const normal=this.palms[side].normal.clone().applyQuaternion(change).applyQuaternion(align);
    const palmNormal=new T.Vector3(...profile.normal).applyQuaternion(anchorChange);
    palmNormal.addScaledVector(handAlong,-palmNormal.dot(handAlong)).normalize();
    const roll=Math.atan2(handAlong.dot(normal.clone().cross(palmNormal)),normal.dot(palmNormal));
    const desired=new T.Quaternion().setFromAxisAngle(handAlong,roll).multiply(align).multiply(current);
    desired.copy(current.clone().slerp(desired,clamp(alpha)));
    // Filter the orientation as a quaternion. Linear interpolation of opposite
    // palm normals passes through zero and flips the hand mid-transition.
    const goal=this.handGoals[side]||(this.handGoals[side]=current.clone());
    const goalAngle=goal.angleTo(desired);
    goal.slerp(desired,Math.min(1-Math.exp(-16/120),3.8/120/Math.max(goalAngle,1e-8)));desired.copy(goal);
    const difference=desired.clone().multiply(current.clone().invert());
    if(difference.w<0)difference.set(-difference.x,-difference.y,-difference.z,-difference.w);
    const projection=new T.Vector3(difference.x,difference.y,difference.z).dot(forearmAxis);
    const twist=clamp(2*Math.atan2(projection,difference.w),-2.8,2.8)*.8;
    const key='reachRoll'+side,previous=this.state.get(key)?.x||0;
    this.spring(key,twist,1/120,2.6,.98);
    const state=this.state.get(key);state.x=clamp(state.x,previous-3.5/120,previous+3.5/120);state.v=clamp(state.v,-3.5,3.5);
    this.distributeForearmTwist(side,forearmAxis,state.x);
    wrist.quaternion.copy(wrist.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(desired);
    this.asset.updateMatrixWorld(true);
  }
  distributeForearmTwist(side,axis,angle){
    const apply=(bone,weight)=>{
      const world=new T.Quaternion().setFromAxisAngle(axis,angle*weight).multiply(bone.getWorldQuaternion(new T.Quaternion()));
      bone.quaternion.copy(bone.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(world);bone.updateWorldMatrix(false,true);
    };
    apply(this.forearms[side],1);
    this.rollBones[side].forEach((bone,i)=>apply(bone,[.35,.65,.9][i]));
    this.clothRollBones[side].forEach((bone,i)=>apply(bone,[1,.35,.65,.9][i]*.10));
  }
  facePalm(side,amount,target){
    const wrist=this.joints['wrist'+side];wrist.updateWorldMatrix(true,false);
    const current=wrist.getWorldQuaternion(new T.Quaternion()),change=current.clone().multiply(this.rest.get(wrist).worldInverse);
    const along=this.palms[side].along.clone().applyQuaternion(change),normal=this.palms[side].normal.clone().applyQuaternion(change);
    target.addScaledVector(along,-target.dot(along));if(target.lengthSq()<.01)return;target.normalize();
    const angle=Math.atan2(along.dot(normal.clone().cross(target)),normal.dot(target));
    const twist=this.spring('palmTwist'+side,clamp(angle*amount,-2.6,2.6),1/120,3.2,.98);
    const world=new T.Quaternion().setFromAxisAngle(along,twist).multiply(current);
    // Pronation belongs mostly to the forearm; leaving it entirely at the
    // wrist creates the old sharply twisted hand/sleeve join.
    const forearm=this.forearms[side];
    const axis=wrist.getWorldPosition(new T.Vector3()).sub(forearm.getWorldPosition(new T.Vector3())).normalize();
    // MMD twist helpers are siblings of the main roll joint, not descendants.
    // They must share its rotation or the weighted sleeve pinches at the seam.
    this.distributeForearmTwist(side,axis,twist*.65);
    wrist.quaternion.copy(wrist.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(world);
  }
  solveFeet(){
    this.asset.updateMatrixWorld(true);let drift=0;
    if(this.locomotion?.feet){
      let needed=0;
      for(const side of ['L','R']){
        const h=this.joints['thigh'+side].getWorldPosition(new T.Vector3()),foot=this.locomotion.feet[side],leg=this.legs[side],reach=leg.a+leg.b-.001;
        const horizontal=(h.x-foot.x)**2+(h.z-foot.z)**2;
        needed=Math.max(needed,h.y-foot.y-Math.sqrt(Math.max(0,reach*reach-horizontal)));
      }
      needed=clamp(needed,0,.04);
      const drop=Math.max(needed,this.spring('walkReachDrop',needed,1/120,4,.98));
      this.joints.waist.position.y-=drop/this.joints.waist.parent.getWorldScale(new T.Vector3()).y;
      this.audit.pelvisDrop=drop;this.asset.updateMatrixWorld(true);
    }
    for(const side of ['L','R']){
      const thigh=this.joints['thigh'+side],knee=this.joints['knee'+side],ankle=this.joints['ankle'+side],leg=this.legs[side],foot=this.locomotion?.feet?.[side]||this.feet[side];
      const h=thigh.getWorldPosition(new T.Vector3()),axis=foot.clone().sub(h),distance=Math.min(axis.length(),leg.a+leg.b-.000001);axis.normalize();
      const along=(leg.a**2-leg.b**2+distance**2)/(2*distance),height=Math.sqrt(Math.max(0,leg.a**2-along**2));
      const pole=new T.Vector3(0,0,1);pole.addScaledVector(axis,-pole.dot(axis)).normalize();
      const k=h.clone().addScaledVector(axis,along).addScaledVector(pole,height);
      const aim=(bone,direction,restDir)=>{const world=new T.Quaternion().setFromUnitVectors(restDir,direction.normalize()).multiply(this.rest.get(bone).world);bone.quaternion.copy(bone.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(world);bone.updateWorldMatrix(false,true);};
      aim(thigh,k.clone().sub(h),leg.upper);aim(knee,foot.clone().sub(k),leg.lower);
      const sole=new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),this.locomotion?.footYaw?.[side]||0)
        .multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),this.locomotion?.footPitch?.[side]||0)).multiply(this.rest.get(ankle).world);
      ankle.quaternion.copy(ankle.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(sole);ankle.updateWorldMatrix(false,true);
      drift=Math.max(drift,ankle.getWorldPosition(new T.Vector3()).distanceTo(foot));
    }
    this.audit.footDrift=drift;
  }
}

export function bakeBodyClips(asset){
  const clips=[];
  for(const action of ACTIONS){const actor=new BodyActor(asset);for(let f=0;f<180;f++)actor.update(1/120);actor.play(action);const times=[],positions=actor.bones.map(()=>[]),rotations=actor.bones.map(()=>[]);
    for(let frame=0;frame<=240;frame++){
      if(frame>0)actor.update(1/30);times.push(frame/30);
      // Settle into the exact opening pose before a GLB clip wraps. Blend the
      // sampled values only, so physics continues to integrate independently.
      const close=smooth((frame/30-7.4)/.6);
      actor.bones.forEach((b,i)=>{
        const p=b.position.clone(),q=b.quaternion.clone();
        if(close>0){p.lerp(new T.Vector3().fromArray(positions[i]),close);q.slerp(new T.Quaternion().fromArray(rotations[i]),close);}
        positions[i].push(...p.toArray());rotations[i].push(...q.toArray());
      });
    }
    const tracks=[];actor.bones.forEach((b,i)=>{const r=actor.rest.get(b),bindP=r.position.toArray(),bindQ=r.quaternion.toArray();const moved=positions[i].some((v,k)=>Math.abs(v-positions[i][k%3])>1e-7)||positions[i].slice(0,3).some((v,k)=>Math.abs(v-bindP[k])>1e-7),rotated=rotations[i].some((v,k)=>Math.abs(v-rotations[i][k%4])>1e-7)||rotations[i].slice(0,4).some((v,k)=>Math.abs(v-bindQ[k])>1e-7);if(moved)tracks.push(new T.VectorKeyframeTrack(`${b.name}.position`,times,positions[i]).optimize());if(rotated)tracks.push(new T.QuaternionKeyframeTrack(`${b.name}.quaternion`,times,rotations[i]).optimize());});clips.push(new T.AnimationClip(action,8,tracks));
    actor.bones.forEach(b=>{const r=actor.rest.get(b);b.position.copy(r.position);b.quaternion.copy(r.quaternion);});asset.updateMatrixWorld(true);
  }return clips;
}
