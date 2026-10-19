import * as T from './vendor/three.module.js';
const clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return x*x*(3-2*x);};
const pulse=(t,start,end)=>ease((t-start)/.65)*(1-ease((t-end+.9)/.9));
export const actions=['idle','greet','explain','laugh','shy','sad','turn'];

export class Actor{
  constructor(model){this.model=model;this.time=0;this.action='idle';this.start=0;this.state={};this.from={};this.audio=0;this.accumulator=0;}
  play(action){if(!actions.includes(action))return;this.from=Object.fromEntries(Object.entries(this.state).map(([k,v])=>[k,v.x]));this.action=action;this.start=this.time;}
  spring(key,target,dt,frequency=3){
    if(this.from[key]!==undefined&&this.time-this.start<.55)target=T.MathUtils.lerp(this.from[key],target,ease((this.time-this.start)/.55));
    const s=this.state[key]||={x:0,v:0},w=frequency*Math.PI*2;s.v+=(w*w*(target-s.x)-1.8*w*s.v)*dt;s.x+=s.v*dt;return s.x;
  }
  update(dt,audio=0){this.accumulator+=Math.min(.1,Math.max(0,dt));this.audio=audio;while(this.accumulator>=1/120){this.step(1/120);this.accumulator-=1/120;}}
  step(dt){
    const {joints:j,eyes,mouth,hair}=this.model,t=this.time+=dt,a=t-this.start,e=pulse(a,0,6.5),on=name=>this.action===name?e:0;
    const greet=on('greet'),explain=on('explain'),laugh=on('laugh'),shy=on('shy'),sad=on('sad'),turn=on('turn');
    const wave=Math.sin(a*7)*pulse(a,.8,4.5),beat=explain*(.7+.3*Math.sin(a*2.8));
    const speech=clamp(this.audio*4),accent=speech*(.5+.5*Math.sin(t*4.1));
    const s=(key,target,f=3)=>this.spring(key,target,dt,f);
    j.hips.position.set(s('hipX',Math.sin(t*.5)*.008+greet*.018-shy*.018,1.7),1.024-s('crouch',sad*.016+laugh*.006*(1+Math.sin(a*8)),2),0);
    j.hips.rotation.set(0,s('hipYaw',turn*.24*Math.sin(a*1.1)+explain*.10,1.8),s('hipZ',greet*-.035+shy*.04,1.8));
    j.spine.rotation.set(s('spineX',sad*.10+laugh*.065,2),s('spineY',explain*-.14,2),s('spineZ',greet*.025-shy*.025,2));
    j.chest.rotation.set(s('chestX',laugh*.04,2.5),s('chestY',turn*.25*Math.sin(a*1.1)+greet*-.06,2),s('chestZ',Math.sin(t*.65)*.012+explain*.035,2));
    j.head.rotation.set(s('headX',sad*.14+shy*.11+accent*.04+laugh*.035*Math.sin(a*8),3),s('headY',turn*.28*Math.sin(a*1.1)-shy*.12+Math.sin(t*.33)*.035,2.5),s('headZ',-greet*.12+shy*.14+explain*.07,2.7));
    // Right-side arm: outward upper arm, forearm upright, palm facing camera.
    j.upperR.rotation.set(s('upperRx',-.12-greet*.05-explain*.30),s('upperRy',explain*-.16),s('upperRz',.08+greet*1.24+beat*.48+accent*.14));
    j.elbowR.rotation.set(s('elbowRx',-.15-explain*.45-laugh*.3),0,s('elbowRz',greet*1.79+beat*.80+laugh*1.15));
    j.wristR.rotation.set(s('wristRx',explain*-.9),s('wristRy',greet*.04+explain*.35),s('wristRz',greet*wave*.20+beat*.12));
    // Left-side hand approaches face for laughter/shyness; the other hand rests.
    const faceHand=Math.max(laugh,shy),leftExplain=explain*(.65+.35*Math.sin(a*2.8+1.7));
    j.upperL.rotation.set(s('upperLx',-.10-faceHand*.45-leftExplain*.30),s('upperLy',faceHand*.12),s('upperLz',-.09-faceHand*.15-leftExplain*.26));
    j.elbowL.rotation.set(s('elbowLx',-.12-faceHand*2.25-leftExplain*1.10),0,s('elbowLz',faceHand*.30-leftExplain*.25));
    j.wristL.rotation.set(s('wristLx',faceHand*.55-leftExplain*.35),s('wristLy',faceHand*-.55),s('wristLz',faceHand*-.22));
    for(const side of ['L','R']){
      const open=side==='R'?Math.max(greet,explain):explain*.7;
      for(let i=0;i<4;i++){
        const spread=(i-1.5)*.075*open*(side==='R'?1:-1);
        for(const segment of ['a','b','c']){const b=j[`finger${side}${i}${segment}`];b.rotation.x=s(`curl${side}${i}${segment}`,.22*(1-open)+(side==='L'?faceHand*.20:0),4);b.rotation.z=segment==='a'?spread:0;}
      }
      j[`thumb${side}a`].rotation.z=(side==='R'?-1:1)*(.10+open*.22);
      j[`thumb${side}b`].rotation.x=.15*(1-open);
    }
    const blinkPhase=(t+1.3)%4.1,blink=blinkPhase<.24?Math.sin(blinkPhase/.24*Math.PI)**2:0;
    const closed=Math.max(blink,laugh*.92);
    eyes.forEach(eye=>{eye.scale.y=Math.max(.045,1-closed);});
    mouth.scale.y=.12+s('mouth',Math.max(speech,laugh*(.6+.2*Math.sin(a*8))),7);mouth.scale.x=1+laugh*.15;
    if(this.model.face){this.model.face.morphTargetInfluences[0]=closed;this.model.face.morphTargetInfluences[1]=Math.max(0,mouth.scale.y-.12);}
    hair.forEach((lock,i)=>{lock.rotation.z=Math.sin(t*2.3+i*.37)*.012-j.head.rotation.z*.12;lock.rotation.x=Math.sin(t*1.8+i*.3)*.01+j.head.rotation.x*.08;});
    this.solveFeet();this.model.group.updateMatrixWorld(true);
    if(a>7.5&&this.action!=='idle')this.play('idle');
  }
  solveFeet(){
    const {group,joints:j}=this.model;group.updateMatrixWorld(true);
    const down=new T.Vector3(0,-1,0);
    for(const [side,sign] of [['L',-1],['R',1]]){
      const thigh=j[`thigh${side}`],knee=j[`knee${side}`],ankle=j[`ankle${side}`];
      const h=thigh.getWorldPosition(new T.Vector3()),f=group.localToWorld(new T.Vector3(sign*.095,.155,0));
      const axis=f.clone().sub(h),d=Math.min(axis.length(),.425+.435-.00001);axis.normalize();
      const along=(.425**2-.435**2+d*d)/(2*d),height=Math.sqrt(Math.max(0,.425**2-along**2));
      const pole=new T.Vector3(0,0,1).applyQuaternion(group.getWorldQuaternion(new T.Quaternion()));pole.addScaledVector(axis,-pole.dot(axis)).normalize();
      const k=h.clone().addScaledVector(axis,along).addScaledVector(pole,height);
      const parentQ=thigh.parent.getWorldQuaternion(new T.Quaternion()).invert();
      thigh.quaternion.copy(parentQ).multiply(new T.Quaternion().setFromUnitVectors(down,k.clone().sub(h).normalize()));thigh.updateWorldMatrix(false,true);
      const thighQ=thigh.getWorldQuaternion(new T.Quaternion()).invert();
      knee.quaternion.copy(thighQ).multiply(new T.Quaternion().setFromUnitVectors(down,f.clone().sub(k).normalize()));knee.updateWorldMatrix(false,true);
      const parentFoot=knee.getWorldQuaternion(new T.Quaternion()).invert();ankle.quaternion.copy(parentFoot).multiply(group.getWorldQuaternion(new T.Quaternion()));
    }
  }
}
