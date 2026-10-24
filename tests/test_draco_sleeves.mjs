import test from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {narrowSleeves} from '../web_tool/mao-5070/draco/garment-rig.mjs';
import {createDracoRig} from './helpers/draco_fixture.mjs';

// A robe mesh with points around the left forearm (weighted to a bone under the elbow) and
// one on the body. Distances are measured from the forearm axis in the bind pose.
function setup(){
  const root=createDracoRig(),bones=[];root.traverse(b=>{if(b.isBone)bones.push(b);});
  const at=name=>root.getObjectByName(name).getWorldPosition(new T.Vector3());
  const elbow=at('draco_elbowL'),wrist=at('draco_wristL'),axis=wrist.clone().sub(elbow),length=axis.length();axis.normalize();
  const side=new T.Vector3().crossVectors(axis,new T.Vector3(0,0,1)).normalize();
  const around=(t,r)=>elbow.clone().addScaledVector(axis,t*length).addScaledVector(side,r*length);
  const sleeveBone=bones.indexOf(root.getObjectByName('draco_bone_0123')),chest=bones.indexOf(root.getObjectByName('draco_chest'));
  const points=[around(.9,.1),around(.9,1),around(.9,.6),around(.5,1)],body=at('draco_chest');
  const geometry=new T.BufferGeometry();
  geometry.setAttribute('position',new T.Float32BufferAttribute([...points,body].flatMap(p=>p.toArray()),3));
  geometry.setAttribute('skinIndex',new T.Uint16BufferAttribute([sleeveBone,0,0,0,sleeveBone,0,0,0,sleeveBone,chest,0,0,sleeveBone,0,0,0,chest,0,0,0],4));
  geometry.setAttribute('skinWeight',new T.Float32BufferAttribute([1,0,0,0,1,0,0,0,.3,.7,0,0,1,0,0,0,1,0,0,0],4));
  const skeleton=new T.Skeleton(bones);skeleton.calculateInverses();
  const material=new T.MeshBasicMaterial();material.name='V8_Robe_Seams_Fabric_Lining';
  // Like the real robe: the mesh node is turned (its world matrix is not its bind matrix).
  const holder=new T.Group();holder.rotation.x=-Math.PI/2;root.add(holder);
  const mesh=new T.SkinnedMesh(geometry,material);holder.add(mesh);root.updateMatrixWorld(true);mesh.bind(skeleton,new T.Matrix4());
  const radius=k=>{const v=new T.Vector3().fromBufferAttribute(geometry.attributes.position,k).sub(elbow);return v.addScaledVector(axis,-v.dot(axis)).length()/length;};
  const along=k=>new T.Vector3().fromBufferAttribute(geometry.attributes.position,k).sub(elbow).dot(axis)/length;
  return {root,mesh,radius,along,body};
}

test('the bell of the sleeve is pulled toward the forearm, the arm-hugging part and the body are not',()=>{
  const {root,mesh,radius,along,body}=setup();
  const before=[0,1,2,3].map(radius);
  narrowSleeves(root);
  assert.ok(Math.abs(radius(0)-before[0])<1e-6,'cloth close to the arm keeps its place');
  assert.ok(Math.abs(radius(1)-(.18+(1-.18)*.4))<1e-4,`the wide opening narrows (${radius(1).toFixed(3)})`);
  assert.ok(radius(3)<before[3]*.6,'the whole bell narrows, not only its rim');
  assert.ok(radius(2)<before[2]&&radius(2)>.18+(before[2]-.18)*.4,'a vertex only partly on the sleeve moves partly');
  assert.ok(Math.abs(along(1)-.9)<1e-5,'the sleeve keeps its length');
  assert.ok(new T.Vector3().fromBufferAttribute(mesh.geometry.attributes.position,4).distanceTo(body)<1e-7,'the body is untouched');
  const once=[0,1,2,3].map(radius);
  narrowSleeves(root);
  assert.deepEqual([0,1,2,3].map(radius),once,'running it again changes nothing');
});
