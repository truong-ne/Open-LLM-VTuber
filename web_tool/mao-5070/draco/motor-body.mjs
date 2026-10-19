import * as T from '../3d/vendor/three.module.js';
import {PerformanceBodyActor} from './performance-motion.mjs?v=3';
import {MotorPolicy,validateMotor} from './motor-policy.mjs';
const smooth=n=>{n=T.MathUtils.clamp(n,0,1);return n*n*(3-2*n);};

// New poses are composed from continuous goals. No clips are created, and the
// existing IK, palm constraints, cloth and skirt clearance remain authoritative.
export class AdaptiveBodyActor extends PerformanceBodyActor{
  constructor(asset,policy=new MotorPolicy()){
    super(asset);this.motorPolicy=policy;this.motorRaw=null;this.motorStarted=0;this.motorUntil=0;this.motorGuard=1;this.motorRejected=0;
  }
  setMotor(raw){
    const pose=validateMotor(raw);if(!pose){this.motorRejected++;return false;}
    this.motorRaw=pose;this.motorStarted=this.time;this.motorUntil=this.time+(pose.duration||4);this.play('talk');return true;
  }
  clearMotor(){this.motorUntil=Math.min(this.motorUntil,this.time);}
  spring(key,target,dt,f=2.7,damping=.95){
    if(this.motorRaw&&/^(reach|handDir)/.test(key))f*=this.motorPolicy.profile.tempo;
    return super.spring(key,target,dt,f,damping);
  }
  get motorActive(){return !!this.motorRaw&&this.time<this.motorUntil;}
  get motorAmount(){
    if(!this.motorRaw)return 0;
    const walking=T.MathUtils.clamp((this.locomotion?.speed||0)*4+Math.abs(this.locomotion?.yawRate||0),0,1);
    return smooth((this.time-this.motorStarted)/.7)*(1-smooth((this.time-this.motorUntil+.7)/.7))*(1-walking)*this.motorGuard;
  }
  reachArm(side,profile,amount){
    if(!this.motorRaw)return super.reachArm(side,profile,amount);
    const pose=this.motorPolicy.apply(this.motorRaw),strength=this.motorAmount;
    if(side==='L'){
      // Base step has already reset the skeleton and posed the trunk. Add before
      // the arm solver, so hands solve against the adjusted chest, not stale IK.
      for(const [name,xyz] of Object.entries({head:[pose.nod||0,0,pose.tilt||0],spine:[(pose.lean||0)*.65,0,0],chest:[(pose.lean||0)*.35,0,0]})){
        const angles=xyz.map((x,i)=>this.spring('motor-'+name+i,T.MathUtils.degToRad(x)*strength,1/120,2.1*this.motorPolicy.profile.tempo,.98));
        const rest=this.rest.get(this.joints[name]),q=new T.Quaternion().setFromEuler(new T.Euler(...angles));
        this.joints[name].quaternion.multiply(rest.worldInverse.clone().multiply(q).multiply(rest.world));
      }
      this.asset.updateMatrixWorld(true);
    }
    const key=side==='L'?'left':'right',open=pose[key]||0,sign=side==='L'?1:-1;
    if(Object.hasOwn(pose,key)){
      const target={anchor:'chest',offset:[sign*(.18+open*.15),-.12+(pose.height||0)+open*.12,.16+open*.08],along:[sign*.65,-.15,.6],normal:[0,1,.4],pole:[sign*.8,-1,.2]};
      return super.reachArm(side,target,strength*open);
    }
    return super.reachArm(side,profile,amount);
  }
  update(dt,rms=0){
    super.update(dt,rms);
    // Renderer feedback can only reduce an unsafe intention, never expand its
    // authority. This is a transient guard, not a fabricated human evaluation.
    if(this.motorActive&&(!Number.isFinite(this.audit.footDrift)||this.audit.footDrift>.012)){
      this.motorGuard=Math.max(.25,this.motorGuard-.08);this.motorRejected++;this.clearMotor();
    }
    if(this.motorRaw&&this.time>this.motorUntil+1.5){this.motorRaw=null;this.motorGuard=1;}
  }
}
