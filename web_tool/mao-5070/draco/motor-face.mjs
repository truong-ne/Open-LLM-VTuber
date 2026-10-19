import * as T from '../3d/vendor/three.module.js';
import {PerformanceFaceRig} from './performance-face.mjs?v=1';
export class AdaptiveFaceRig extends PerformanceFaceRig{
  constructor(asset){super(asset);this.motorFace={};this.motorFaceTargets={};}
  setMotor(pose,amount=0){
    this.motorFaceTargets={};
    for(const key of ['smile','brow','eyes'])if(typeof pose?.[key]==='number'&&Number.isFinite(pose[key]))this.motorFaceTargets[key]={value:T.MathUtils.clamp(pose[key],0,1),amount:T.MathUtils.clamp(amount,0,1)};
  }
  update(volume,playing,dt){
    const open=super.update(volume,playing,dt),blend=1-Math.exp(-Math.min(Math.max(dt||0,0),.1)*12);
    for(const key of ['smile','brow','eyes']){
      const old=this.motorFace[key]||(this.motorFace[key]={value:0,amount:0}),target=this.motorFaceTargets[key];
      old.value+=((target?.value??old.value)-old.value)*blend;old.amount+=((target?.amount||0)-old.amount)*blend;
    }
    const mix=(key,base)=>T.MathUtils.lerp(base,this.motorFace[key].value,this.motorFace[key].amount);
    this.smileUniform.value=mix('smile',this.smileUniform.value);
    for(const target of this.smileTargets)target.mesh.morphTargetInfluences[target.index]=this.smileUniform.value;
    for(const target of this.targets){
      target.mesh.morphTargetInfluences[target.brow]=mix('brow',target.mesh.morphTargetInfluences[target.brow]);
      target.mesh.morphTargetInfluences[target.wide]=mix('eyes',this.weights.surprised)*(1-this.eyeClose);
    }
    return open;
  }
}
