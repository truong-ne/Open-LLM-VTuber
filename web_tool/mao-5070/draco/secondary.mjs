import * as T from '../3d/vendor/three.module.js';

const clamp=T.MathUtils.clamp;
// Constrained spring tails, evaluated root-to-tip in world space. The source
// garment weights are preserved; this is a bone simulation, not a cloth mesh.
export class GarmentDynamics {
  constructor(actor){
    this.actor=actor;this.segments=[];this.enabled=true;this.colliders=[];
    this.scratch={};for(const key of ['head','direction','goal','velocity','tail','delta','constraint','actual','closest','scale','position'])this.scratch[key]=new T.Vector3();
    for(const key of ['base','limit','identity','world','parent'])this.scratch[key]=new T.Quaternion();
    this.headDelta=new T.Matrix4();
    this.unit=actor.rest.get(actor.joints.head).worldPosition.y-actor.feet.L.y;
    this.unit/=1.237;
    const profiles={
      hair:{stiffness:18,drag:12,gravity:.75,limit:.24,radius:.013},
      coat:{stiffness:14,drag:14,gravity:1.6,limit:.18,radius:.012},
      skirt:{stiffness:23,drag:16,gravity:.35,limit:.14,radius:.009},
      cuff:{stiffness:20,drag:14,gravity:3.0,limit:.30,radius:.007}
    };
    const chain=(root,count,type)=>{
      for(let i=0;i<count;i++){
        const b=actor.asset.getObjectByName(`draco_bone_${String(root+i).padStart(4,'0')}`);
        const child=actor.asset.getObjectByName(`draco_bone_${String(root+i+1).padStart(4,'0')}`);
        if(!b||child?.parent!==b)continue;
        const p=actor.rest.get(b).worldPosition,c=actor.rest.get(child).worldPosition;
        if(p.distanceTo(c)<.00001)continue;
        this.segments.push({b,child,type,...profiles[type],collisionLimit:profiles[type].limit,depth:i,
          headAnchored:type==='hair'&&p.distanceTo(c)<.05*this.unit,
          length:p.distanceTo(c),local:child.position.clone().normalize(),
          current:c.clone(),previous:c.clone(),initialized:false});
      }
    };
    // Include the last weighted row, which the earlier angular sway omitted.
    for(const root of [23,28,33,38,43,48,53,58,61,64,69])chain(root,4,'hair');
    for(let i=0;i<13;i++)chain(248+i*7,6,'coat');
    for(let i=0;i<20;i++)chain(397+i*6,4,'skirt');
    for(const root of [123,127,131,210,214,218])chain(root,3,'cuff');
    this.previousHeadInverse=actor.joints.head.matrixWorld.clone().invert();
    this.buildColliders();
    for(const s of this.segments){
      s.ignore=new Set();
      this.colliders.forEach((c,i)=>{
        if(s.current.distanceTo(this.closest(s.current,c,this.scratch.closest))<c.r+s.radius*this.unit)s.ignore.add(i);
      });
    }
    this.audit={contacts:0,maxStretch:0,maxPenetration:0,maxAngle:0};
  }
  closest(point,c,target=new T.Vector3()){
    const x=c.b.x-c.a.x,y=c.b.y-c.a.y,z=c.b.z-c.a.z;
    const t=clamp(((point.x-c.a.x)*x+(point.y-c.a.y)*y+(point.z-c.a.z)*z)/Math.max(x*x+y*y+z*z,1e-12),0,1);
    return target.set(c.a.x+x*t,c.a.y+y*t,c.a.z+z*t);
  }
  constrainTail(tail,head,direction,length,limit){
    const d=this.scratch.constraint.copy(tail).sub(head).normalize();
    const angle=Math.acos(clamp(direction.dot(d),-1,1));
    if(angle>limit){const q=this.scratch.limit.setFromUnitVectors(direction,d);q.slerp(this.scratch.identity,1-limit/angle);d.copy(direction).applyQuaternion(q);}
    tail.copy(head).addScaledVector(d,length);
  }
  buildColliders(){
    const j=this.actor.joints,pos=n=>j[n].getWorldPosition(new T.Vector3());
    const add=(a,b,r,types)=>this.colliders.push({a,b,r:r*this.unit,types});
    this.colliders=[];
    add(pos('pelvis'),pos('chest'),.087,['hair','coat','cuff']);
    add(pos('neck'),pos('head').add(new T.Vector3(0,.07*this.unit,0)),.060,['hair']);
    for(const side of ['L','R']){
      add(pos('thigh'+side),pos('knee'+side),.060,['coat','skirt']);
      add(pos('knee'+side),pos('ankle'+side),.037,['coat']);
    }
  }
  step(dt){
    if(!this.enabled){for(const s of this.segments)s.initialized=false;return;}
    this.actor.asset.updateMatrixWorld(true);this.buildColliders();
    const headDelta=this.headDelta.copy(this.actor.joints.head.matrixWorld).multiply(this.previousHeadInverse);
    this.previousHeadInverse.copy(this.actor.joints.head.matrixWorld).invert();
    this.audit={contacts:0,maxStretch:0,maxPenetration:0,maxAngle:0};
    for(const s of this.segments){
      s.collisionLimit=Math.max(s.limit,s.collisionLimit-dt*.25);
      // Bangs live in the head's center space. A deeper bow must not drag
      // these short strands through the scalp; long hair keeps world inertia.
      if(s.headAnchored&&s.initialized){s.current.applyMatrix4(headDelta);s.previous.applyMatrix4(headDelta);}
      s.b.updateWorldMatrix(true,false);
      const head=this.scratch.head,base=this.scratch.base;
      s.b.matrixWorld.decompose(head,base,this.scratch.scale);
      const direction=this.scratch.direction.copy(s.local).applyQuaternion(base).normalize();
      const goal=this.scratch.goal.copy(head).addScaledVector(direction,s.length);
      if(!s.initialized){s.current.copy(goal);s.previous.copy(goal);s.initialized=true;}
      const velocity=this.scratch.velocity.copy(s.current).sub(s.previous).multiplyScalar(Math.exp(-s.drag*dt));
      const tail=this.scratch.tail.copy(s.current).add(velocity)
        .addScaledVector(this.scratch.delta.copy(goal).sub(s.current),s.stiffness**2*dt*dt);
      tail.y-=s.gravity*this.unit*dt*dt;
      const motion=this.actor.locomotion;
      if(motion){
        // Inertial forces in the stable skeleton space. The display root moves
        // separately, avoiding double-transforming the garment simulation.
        const w=motion.yawRate||0,alpha=motion.yawAcceleration||0,a=motion.acceleration||{x:0,z:0};
        tail.x-=clamp(a.x+alpha*goal.z-w*w*goal.x,-1.5,1.5)*dt*dt*.55;
        tail.z-=clamp(a.z-alpha*goal.x-w*w*goal.z,-1.5,1.5)*dt*dt*.55;
      }
      // Length and angular limits preserve the cut of the original garment.
      this.constrainTail(tail,head,direction,s.length,s.collisionLimit);
      for(let iteration=0;iteration<3;iteration++){
        for(const [index,collider] of this.colliders.entries()){
          if(!collider.types.includes(s.type)||s.ignore.has(index))continue;
          const closest=this.closest(tail,collider,this.scratch.closest);
          const delta=this.scratch.delta.copy(tail).sub(closest),radius=collider.r+s.radius*this.unit;
          // Only embedded bind-pose sections are excluded, not an animated
          // target that enters the body during a bow or a weight shift.
          if(delta.lengthSq()<radius*radius){
            // A loose cuff may fold around the torso further than its normal
            // rest cone. Prefer body separation to forcing it back inside.
            if(s.type==='cuff')s.collisionLimit=.65;
            if(s.type==='skirt'&&this.actor.locomotion?.sidestep)s.collisionLimit=Math.max(s.collisionLimit,.42);
            if(s.type==='hair'&&this.actor.locomotion?.sidestep)s.collisionLimit=Math.max(s.collisionLimit,.48);
            if(s.type==='skirt'&&((this.actor.locomotion?.speed||0)>.002||Math.abs(this.actor.locomotion?.yawRate||0)>.01))s.collisionLimit=Math.max(s.collisionLimit,.42);
            if(delta.lengthSq()<1e-12)delta.copy(direction);
            tail.copy(closest).addScaledVector(delta.normalize(),radius);
            this.audit.contacts++;
          }
        }
        this.constrainTail(tail,head,direction,s.length,s.collisionLimit);
      }
      const actual=this.scratch.actual.copy(tail).sub(head).normalize();
      this.audit.maxAngle=Math.max(this.audit.maxAngle,Math.acos(clamp(direction.dot(actual),-1,1)));
      this.audit.maxStretch=Math.max(this.audit.maxStretch,Math.abs(tail.distanceTo(head)-s.length));
      this.colliders.forEach((c,i)=>{
        if(c.types.includes(s.type)&&!s.ignore.has(i)){
          const depth=Math.max(0,c.r+s.radius*this.unit-tail.distanceTo(this.closest(tail,c,this.scratch.closest)));
          if(depth>this.audit.maxPenetration){this.audit.maxPenetration=depth;this.audit.blocked={bone:s.b.name,type:s.type,collider:i};}
        }
      });
      const world=this.scratch.world.setFromUnitVectors(direction,actual).multiply(base);
      s.b.parent.matrixWorld.decompose(this.scratch.position,this.scratch.parent,this.scratch.scale);
      s.b.quaternion.copy(this.scratch.parent.invert()).multiply(world);
      s.b.updateWorldMatrix(false,false);
      s.previous.copy(s.current);s.current.copy(tail);
    }
  }
}
