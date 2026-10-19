// Offline QA of the same skinned geometry used by the preview.
import fs from 'node:fs';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {createNativeMeshFixture} from '../tests/helpers/draco_mesh_fixture.mjs';
import {PerformanceBodyActor} from '../web_tool/mao-5070/draco/performance-motion.mjs';
import {PerformanceFaceRig,FACE_PRESETS} from '../web_tool/mao-5070/draco/performance-face.mjs';
import {AdaptiveBodyActor} from '../web_tool/mao-5070/draco/motor-body.mjs';
import {AdaptiveFaceRig} from '../web_tool/mao-5070/draco/motor-face.mjs';
const motor=process.argv.includes('--motor');
const {asset,root}=createNativeMeshFixture(),actor=new (motor?AdaptiveBodyActor:PerformanceBodyActor)(asset);
for(let i=0;i<180;i++)actor.update(1/120);
const face=new (motor?AdaptiveFaceRig:PerformanceFaceRig)(asset),meshes=[];asset.traverse(m=>{if(m.isMesh)meshes.push(m);});
const chunks=[];let offset=0;
const put=array=>{const result={offset,count:array.length};chunks.push(Buffer.from(array.buffer,array.byteOffset,array.byteLength));offset+=array.byteLength;return result;};
const meta={meshes:meshes.map(m=>({name:m.material.name,color:m.material.color.getHex(),colors:put(new Float32Array(m.geometry.attributes.color?.array||[])),uv:put(new Float32Array(m.geometry.attributes.uv?.array||[])),index:put(new Uint32Array(m.geometry.index.array))})),frames:[]};
function capture(label,crop='face'){
  asset.updateMatrixWorld(true);const p=new T.Vector3();
  const frame={label,crop,open:face.open,smile:face.smileUniform.value,center:actor.joints.head.getWorldPosition(new T.Vector3()).toArray(),meshes:meshes.map(m=>{
    m.skeleton.update();const position=new Float32Array(m.geometry.attributes.position.count*3),local=new Float32Array(position.length);
    for(let i=0;i<position.length/3;i++){
      // getVertexPosition applies both morph targets and skinning.
      m.getVertexPosition(i,p).applyMatrix4(m.matrixWorld).toArray(position,i*3);
      p.fromBufferAttribute(m.geometry.attributes.position,i);
      for(let k=0;k<(m.morphTargetInfluences?.length||0);k++)p.addScaledVector(new T.Vector3().fromBufferAttribute(m.geometry.morphAttributes.position[k],i),m.morphTargetInfluences[k]);
      p.toArray(local,i*3);
    }
    return {position:put(position),local:put(local),visible:m.visible,opacity:m.material.opacity};
  })};meta.frames.push(frame);
}
actor.play('idle');
if(motor){
  for(const [label,pose] of [
    ['explain',{right:.72,left:.15,tilt:-4,smile:.4,brow:.2,duration:6}],
    ['curious',{left:.65,right:.2,height:-.04,tilt:8,nod:-3,brow:.7,eyes:.6,duration:6}],
    ['extreme-bounded',{left:1,right:1,height:.1,tilt:-12,nod:12,lean:4,smile:.9,duration:6}]
  ]){
    actor.setMotor(pose);face.setExpression('neutral');face.nextBlink=Infinity;
    for(let i=0;i<240;i++){actor.update(1/120);face.setMotor(pose,actor.motorAmount);face.update(0,false,1/120);}
    capture(label,'body');capture(label,'face');
  }
}else{
for(const name of Object.keys(FACE_PRESETS)){
  face.setExpression(name);face.nextBlink=Infinity;
  for(let i=0;i<120;i++){actor.update(1/120);face.update(0,false,1/120);}
  capture(name);
}
for(const name of ['squint','flat','surprised']){
  face.setExpression(name);
  for(let i=0;i<120;i++){actor.update(1/120);face.update(0,false,1/120);}
  root.rotation.y=.55;root.updateMatrixWorld(true);capture(name+' / 32 deg','face-side');
  root.rotation.y=0;root.updateMatrixWorld(true);
}
for(const action of ['hipSway','refuse']){
  actor.play(action);face.setExpression(action==='hipSway'?'smile':'flat');
  for(let i=0;i<480;i++){
    actor.update(1/120);face.update(0,false,1/120);
    if([150,220,290].includes(i))capture(`${action}-${i}`,'body');
  }
}
}
fs.writeFileSync('private/draco-expression-qa.bin',Buffer.concat(chunks));
fs.writeFileSync('private/draco-expression-qa.json',JSON.stringify(meta));
console.log(JSON.stringify({frames:meta.frames.length,meshes:meshes.length,bytes:offset}));
