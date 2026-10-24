import * as T from '../3d/vendor/three.module.js';
import {BodyActor} from './motion.mjs?v=30';
import {ACTION_META} from './actions.mjs';

export const PERFORMANCE_META={...ACTION_META,
  hipSway:{label:'Lắc hông',group:'story',at:2.2},
  refuse:{label:'Không chịu đâu',group:'story',at:2.1}};
export const PERFORMANCE_ACTIONS=Object.keys(PERFORMANCE_META);
const clamp=T.MathUtils.clamp;
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
const envelope=(t,hip=false)=>smooth(t/(hip?.55:.85))*(1-smooth((t-(hip?5.15:4.9))/(hip?1.25:1.5)));
// Reference 2.0–3.6s: skirt-center peaks around 2.35/3.15s, troughs
// around 2.8/3.6s. Keep the sway small; faster cadence is not bigger rotation.
export const HIP_SWAY_PERIOD=.84;
const profiles={
  hipSway:side=>({anchor:'chest',offset:[side*.18,-.12,.025],along:[side*.12,-1,-.06],normal:[-side*.9,0,-.15],pole:[side*.85,-.35,-.35]}),
  refuse:side=>({anchor:'chest',offset:[side*.20,.13,.20],along:[side*.12,1,.02],normal:[0,0,1],pole:[side*.4,-1,.16]})
};

// Shared desktop/preview extension. Pose offsets run at the original solver's
// foot-IK boundary, before the single cloth step.
export class PerformanceBodyActor extends BodyActor{
  constructor(asset){
    super(asset);this.previewDelta=new T.Quaternion();this.previewEuler=new T.Euler();this.previewScale=new T.Vector3();
    this.previewCoat=this.dynamics.segments.filter(s=>s.type==='coat').map(segment=>({segment,stiffness:segment.stiffness,drag:segment.drag,limit:segment.limit}));
    this.previewHair=this.dynamics.segments.filter(s=>s.type==='hair'&&!s.headAnchored).map(segment=>({segment,stiffness:segment.stiffness,drag:segment.drag}));
  }
  play(action){
    if(!profiles[action])return super.play(action);
    this.from=new Map([...this.state].map(([key,value])=>[key,value.x]));this.action=action;this.started=this.time;return true;
  }
  reachArm(side,profile,amount){
    if(profiles[this.action]){
      const standing=1-clamp((this.locomotion?.speed||0)*2.3,0,.8);
      const singing=this.action==='hipSway'&&this.songPerformance?.playing;
      return super.reachArm(side,profiles[this.action](side==='L'?1:-1),(singing?smooth(this.songPerformance.time/.8):envelope(this.time-this.started,this.action==='hipSway'))*standing);
    }
    return super.reachArm(side,profile,amount);
  }
  solveFeet(){
    const active=profiles[this.action]?this.action:null,t=this.time-this.started;
    const standing=1-clamp((this.locomotion?.speed||0)*2.3+Math.abs(this.locomotion?.yawRate||0)*.25,0,.85);
    const singing=active==='hipSway'&&this.songPerformance?.playing;
    const strength=(singing?smooth(this.songPerformance.time/.8):envelope(t,active==='hipSway'))*standing,phase=singing?this.songPerformance.time*this.songPerformance.bpm/60*Math.PI:(t-.28)*Math.PI*2/HIP_SWAY_PERIOD;
    const sway=active==='hipSway'?strength:0,no=active==='refuse'?strength:0;
    const spring=(name,value)=>this.spring('preview-'+name,value,1/120,active==='hipSway'?3.6:2.5,active==='hipSway'?.96:.98);
    const lateral=spring('hipX',sway*Math.sin(phase)*.030),back=spring('backZ',-no*.010);
    const dip=spring('hipY',-sway*(1-Math.cos(phase*2))*.001);
    // Whole-trunk balance response: follow acceleration with a small delay.
    // Spine/shoulders share it; neck/head counterbalance to keep the gaze calm.
    const motion=this.locomotion,finite=value=>Number.isFinite(value)?value:0;
    const balance=(name,target)=>this.spring('preview-balance-'+name,clamp(target,-.012,.012),1/120,1.9,.98);
    const roll=balance('roll',finite(motion?.acceleration?.x)*.006+(this.state.get('preview-hipX')?.v||0)*.040);
    const pitch=balance('pitch',-finite(motion?.acceleration?.z)*.006);
    const yaw=balance('yaw',-finite(motion?.yawAcceleration)*.003);
    this.upperBodyFollow={roll,pitch,yaw};
    const coatBlend=spring('coat-settle',sway);
    for(const {segment,stiffness,drag,limit} of this.previewCoat){
      segment.stiffness=T.MathUtils.lerp(stiffness,24,coatBlend);
      segment.drag=T.MathUtils.lerp(drag,25,coatBlend);
      segment.limit=T.MathUtils.lerp(limit,.075,coatBlend);
    }
    const hairBlend=spring('hair-settle',clamp(sway+finite(motion?.speed)*.8,0,1));
    for(const {segment,stiffness,drag} of this.previewHair){
      segment.stiffness=T.MathUtils.lerp(stiffness,20,hairBlend);
      segment.drag=T.MathUtils.lerp(drag,15,hairBlend);
    }
    this.joints.waist.parent.getWorldScale(this.previewScale);
    this.joints.waist.position.x+=lateral*this.dynamics.unit/this.previewScale.x;
    this.joints.waist.position.y+=dip*this.dynamics.unit/this.previewScale.y;
    this.joints.waist.position.z+=back*this.dynamics.unit/this.previewScale.z;
    const offsets={
      pelvis:[0,sway*Math.sin(phase+.20)*.035,-sway*Math.sin(phase)*.055],
      spine:[no*.018+pitch*.65,-sway*Math.sin(phase+.18)*.020+yaw*.65,sway*Math.sin(phase+.12)*.032+roll*.65],
      chest:[pitch*.35,-sway*Math.sin(phase+.30)*.014+no*Math.sin(t*7.1)*.015+yaw*.35,sway*Math.sin(phase+.3)*.014+roll*.35],
      neck:[-pitch*.45,-yaw*.45,-roll*.45],
      head:[-no*.025-pitch*.55,no*Math.sin(t*7.1)*.16-yaw*.55,-sway*Math.sin(phase+.5)*.016+no*Math.sin(t*3.55)*.035-roll*.55],
      clavicleL:[pitch*.15,0,no*.035+roll*.12],clavicleR:[pitch*.15,0,-no*.035+roll*.12]
    };
    for(const [name,xyz] of Object.entries(offsets)){
      const bone=this.joints[name],rest=this.rest.get(bone);
      const [x,y,z]=xyz.map((value,i)=>spring(name+i,value));
      this.previewDelta.setFromEuler(this.previewEuler.set(x,y,z));
      bone.quaternion.multiply(rest.worldInverse.clone().multiply(this.previewDelta).multiply(rest.world));
    }
    this.asset.updateMatrixWorld(true);super.solveFeet();
  }
}
