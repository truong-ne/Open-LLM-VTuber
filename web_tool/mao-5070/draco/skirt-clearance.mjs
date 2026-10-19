import * as T from '../3d/vendor/three.module.js';

// Last intersection of a horizontal ray from the pelvis axis with a full 3D
// capsule. A sloping thigh has an elliptical section, not a radius-sized circle
// at the point with the same Y (which underestimates a bent/splayed leg).
export function thighRayExit(y,dx,dz,a,b,radius){
  const bx=b.x-a.x,by=b.y-a.y,bz=b.z-a.z,ox=-a.x,oy=y-a.y,oz=-a.z;
  const bb=bx*bx+by*by+bz*bz,bd=bx*dx+bz*dz,bo=bx*ox+by*oy+bz*oz,od=dx*ox+dz*oz;
  const qa=bb-bd*bd,qb=bb*od-bo*bd,qc=bb*(ox*ox+oy*oy+oz*oz-radius*radius)-bo*bo;
  let exit=0;
  const h=qb*qb-qa*qc;
  if(qa>1e-12&&h>=0){
    const root=Math.sqrt(h);
    for(let i=0;i<2;i++){const t=(-qb+(i?root:-root))/qa,along=bo+t*bd;if(t>exit&&along>=0&&along<=bb)exit=t;}
  }
  for(let i=0;i<2;i++){const c=i?b:a;
    const x=-c.x,z=-c.z,v=y-c.y,projection=dx*x+dz*z,disc=projection*projection-(x*x+z*z+v*v-radius*radius);
    if(disc>=0)exit=Math.max(exit,-projection+Math.sqrt(disc));
  }
  return exit;
}

// Preserve the pleats and hem while moving only fabric that enters the swept
// thigh envelope. Corrections are a runtime morph, before skeletal skinning;
// the source GLB and visible leg geometry remain intact.
export class SkirtClearance{
  constructor(actor){
    this.actor=actor;actor.asset.traverse(mesh=>{if(mesh.material?.name==='V10_Skirt_Gradient_And_AO_Paint')this.mesh=mesh;});
    this.maxCorrection=0;if(!this.mesh)return;
    const mesh=this.mesh,previous=actor.asset.getObjectByName('mao_skirt_lining');
    if(previous){previous.removeFromParent();previous.geometry.dispose();previous.material.dispose();}
    // Include clearance for skin thickness and the straight edges between
    // neighboring cloth vertices, not only the capsule centerline.
    this.radius=.102*actor.dynamics.unit;
    this.p=new T.Vector3();this.center=new T.Vector3();this.local=new T.Vector3();this.target=new T.Vector3();this.base=new T.Vector3();
    this.frame=new T.Quaternion();this.inverseFrame=new T.Quaternion();
    this.skin=new T.Matrix4();this.bone=new T.Matrix4();this.inverse=new T.Matrix4();
    this.legs=['L','R'].map(side=>({hip:actor.joints['thigh'+side],knee:actor.joints['knee'+side],a:new T.Vector3(),b:new T.Vector3(),radius:this.radius}));
    actor.joints.pelvis.getWorldPosition(this.center);mesh.skeleton.update();
    this.fitThighRadii();
    // Preserve the original pleated silhouette. A rigid pelvis-bound cone
    // pokes through the animated pleats and creates an artificial flat hem.
    this.targets=[mesh].map(mesh=>{
      const source=mesh.geometry;mesh.geometry=source.clone();if(mesh.userData.maoSkirtOwnedGeometry)source.dispose();mesh.userData.maoSkirtOwnedGeometry=true;
      const count=mesh.geometry.attributes.position.count,delta=new T.Float32BufferAttribute(new Float32Array(count*3),3),restY=new Float32Array(count);delta.setUsage(T.DynamicDrawUsage);
      mesh.geometry.morphTargetsRelative=true;mesh.geometry.morphAttributes.position=[delta];mesh.updateMorphTargets();mesh.morphTargetInfluences[0]=1;
      for(let i=0;i<count;i++){mesh.getVertexPosition(i,this.p).applyMatrix4(mesh.matrixWorld);restY[i]=this.p.y-this.center.y;}
      return {mesh,delta,restY};
    });
    this.delta=this.targets[0].delta;
  }
  fitThighRadii(){
    let skin;this.actor.asset.traverse(mesh=>{if(mesh.material?.name==='V16_Original_Leg_Texture_Local_Edge_Repair')skin=mesh;});
    if(!skin)return;skin.skeleton.update();
    for(const leg of this.legs){leg.hip.getWorldPosition(leg.a);leg.knee.getWorldPosition(leg.b);}
    const axis=new T.Vector3(),closest=new T.Vector3(),unit=this.actor.dynamics.unit;
    for(let i=0;i<skin.geometry.attributes.position.count;i++){
      skin.getVertexPosition(i,this.p).applyMatrix4(skin.matrixWorld);
      const y=(this.p.y-this.center.y)/unit;if(y<-.24||y>-.035)continue;
      let nearest,distance=Infinity;
      for(const leg of this.legs){
        axis.subVectors(leg.b,leg.a);const t=T.MathUtils.clamp(closest.subVectors(this.p,leg.a).dot(axis)/axis.lengthSq(),0,1);
        closest.copy(leg.a).addScaledVector(axis,t);const d=closest.distanceTo(this.p);if(d<distance){distance=d;nearest=leg;}
      }
      nearest.radius=Math.max(nearest.radius,distance+.012*unit);
    }
    this.radius=Math.max(...this.legs.map(leg=>leg.radius));
  }
  update(){
    if(!this.mesh)return;
    const {actor}=this;actor.joints.pelvis.getWorldPosition(this.center);
    actor.joints.pelvis.getWorldQuaternion(this.frame).multiply(actor.rest.get(actor.joints.pelvis).worldInverse);this.inverseFrame.copy(this.frame).invert();
    for(const leg of this.legs){leg.hip.getWorldPosition(leg.a).sub(this.center).applyQuaternion(this.inverseFrame);leg.knee.getWorldPosition(leg.b).sub(this.center).applyQuaternion(this.inverseFrame);}
    this.maxCorrection=0;
    for(const target of this.targets)this.updateMesh(target);
  }
  updateMesh({mesh,delta,restY}){
    const {actor}=this;mesh.skeleton.update();mesh.morphTargetInfluences[0]=0;
    const inset=mesh===this.mesh?0:.005*actor.dynamics.unit;
    const position=mesh.geometry.attributes.position,indices=mesh.geometry.attributes.skinIndex,weights=mesh.geometry.attributes.skinWeight;
    for(let i=0;i<position.count;i++){
      mesh.getVertexPosition(i,this.p).applyMatrix4(mesh.matrixWorld);
      this.local.copy(this.p).sub(this.center).applyQuaternion(this.inverseFrame);
      // Keep the lower pleats below their fitted hem. A rotating capsule can
      // otherwise lift a panel above the thigh even without a bone collision.
      const originalY=this.local.y;
      if(restY[i]<-.10*actor.dynamics.unit)this.local.y=Math.min(this.local.y,restY[i]+.003*actor.dynamics.unit);
      const vertical=this.local.y-originalY;
      const r=Math.hypot(this.local.x,this.local.z),blend=T.MathUtils.smoothstep(-this.local.y,.045*actor.dynamics.unit,.095*actor.dynamics.unit);
      let required=r;
      if(r>1e-6&&blend>0){
        const dx=this.local.x/r,dz=this.local.z/r;
        for(const leg of this.legs){
          required=Math.max(required,thighRayExit(this.local.y,dx,dz,leg.a,leg.b,leg.radius-inset));
        }
      }
      const correction=(required-r)*blend;this.maxCorrection=Math.max(this.maxCorrection,Math.hypot(correction,vertical));
      if(correction<1e-6&&Math.abs(vertical)<1e-6){delta.setXYZ(i,0,0,0);continue;}
      this.local.x*=1+correction/r;this.local.z*=1+correction/r;
      this.target.copy(this.local).applyQuaternion(this.frame).add(this.center);
      this.skin.elements.fill(0);
      for(let j=0;j<4;j++){
        const weight=weights.array[i*4+j];if(!weight)continue;
        this.bone.fromArray(mesh.skeleton.boneMatrices,indices.array[i*4+j]*16);
        for(let k=0;k<16;k++)this.skin.elements[k]+=this.bone.elements[k]*weight;
      }
      this.inverse.copy(mesh.matrixWorld).multiply(mesh.bindMatrixInverse).multiply(this.skin).multiply(mesh.bindMatrix).invert();
      this.target.applyMatrix4(this.inverse);this.base.fromBufferAttribute(position,i);this.target.sub(this.base);
      delta.setXYZ(i,this.target.x,this.target.y,this.target.z);
    }
    mesh.morphTargetInfluences[0]=1;delta.needsUpdate=true;
  }
}
