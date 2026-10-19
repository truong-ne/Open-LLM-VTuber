import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {PerformanceBodyActor as BodyActor,PERFORMANCE_ACTIONS as ACTIONS} from '../web_tool/mao-5070/draco/performance-motion.mjs';
import {thighRayExit} from '../web_tool/mao-5070/draco/skirt-clearance.mjs';
import {DesktopSpace,FloorFeet,locomotionFrame} from '../web_tool/mao-5070/draco/desktop-space.mjs';
import {ROOM} from '../web_tool/mao-5070/draco/desktop-room.mjs';
import {createNativeMeshFixture} from './helpers/draco_mesh_fixture.mjs';
import {skirtCoverageProbe} from './helpers/draco_skirt_coverage.mjs';

// The tilted cylinder section extends farther than the old horizontal circle.
const a=new T.Vector3(.06,0,0),b=new T.Vector3(.22,-.50,.20),ray=new T.Vector3(),closest=new T.Vector3();
for(const y of [-.02,-.1,-.2])for(let i=0;i<64;i++){
  const angle=i/64*Math.PI*2,dx=Math.sin(angle),dz=Math.cos(angle),r=thighRayExit(y,dx,dz,a,b,.12);
  if(!r)continue;
  ray.set(dx*r,y,dz*r);const axis=b.clone().sub(a),t=T.MathUtils.clamp(closest.subVectors(ray,a).dot(axis)/axis.lengthSq(),0,1);closest.copy(a).addScaledVector(axis,t);
  assert.ok(Math.abs(ray.distanceTo(closest)-.12)<1e-8,'capsule exit is not on the actual thigh envelope');
}

const report={};
for(const command of ['left','right','walk','spin']){
  const {asset,root}=createNativeMeshFixture(),actor=new BodyActor(asset),space=new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32}),feet=new FloorFeet(actor.feet);
  assert.equal(asset.getObjectByName('mao_skirt_lining'),undefined,'a rigid flat underskirt must not cover the pleats');
  const probe=skirtCoverageProbe(actor,{scaled:true,levels:[-.2087,-.1987,-.1887,-.1787,-.1587,-.1387,-.1187,-.0987,-.0787,-.0587]});
  for(let i=0;i<180;i++)actor.update(1/120);space.perform(command);
  let maxOutside=0,maxCorrection=0,worst;
  for(let frame=0;frame<60*(command==='walk'?24:9);frame++){
    if(frame%120===0)actor.play(['hipSway','refuse',...ACTIONS.filter(a=>!['hipSway','refuse'].includes(a))][(frame/120)%ACTIONS.length]);
    // The display root must be reset before simulation, as in native-avatar.
    root.position.set(0,0,0);root.rotation.y=0;root.updateMatrixWorld(true);
    space.update(1/60);actor.setLocomotion(locomotionFrame(space,feet,1/60));actor.update(1/60);
    maxCorrection=Math.max(maxCorrection,actor.skirtClearance.maxCorrection);
    root.position.set(space.x,0,space.z);root.rotation.y=space.yaw;root.updateMatrixWorld(true);
    if(frame%12===0){
      // Runtime clearance must not let the original weighted hem fold upward.
      const center=actor.joints.pelvis.getWorldPosition(new T.Vector3()),inverse=actor.joints.pelvis.getWorldQuaternion(new T.Quaternion()).multiply(actor.rest.get(actor.joints.pelvis).worldInverse).invert(),point=new T.Vector3();
      const target=actor.skirtClearance.targets[0];target.mesh.skeleton.update();
      for(let i=0;i<target.restY.length;i++)if(target.restY[i]<-.17*actor.dynamics.unit){
        target.mesh.getVertexPosition(i,point).applyMatrix4(target.mesh.matrixWorld).sub(center).applyQuaternion(inverse);
        assert.ok(point.y<=target.restY[i]+.0031*actor.dynamics.unit,'the animated hem folded above its fitted rest height');
      }
      const result=probe();if(result.maxOutside>maxOutside){maxOutside=result.maxOutside;worst={frame,phase:space.phase,action:actor.action,...result};}
      for(const target of actor.skirtClearance.targets)assert.ok(target.delta.array.every(Number.isFinite));
    }
  }
  report[command]={maxOutside,maxCorrection,worst};
  assert.ok(maxOutside<.001,`${command}: a rendered thigh escapes the hem: ${JSON.stringify(report[command])}`);
  assert.ok(maxCorrection<.16*actor.dynamics.unit,`skirt deformation exceeded its fitted travel envelope: ${maxCorrection}`);
}
console.log(JSON.stringify({nativeScale:true,nearHemCoverage:true,...report}));
