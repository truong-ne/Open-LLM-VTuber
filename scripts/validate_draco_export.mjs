import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {ACTIONS} from '../web_tool/mao-5070/draco/actions.mjs';

// Inspect the actual downloaded GLB, including its separate garment skeleton.
const path='web_tool/mao-5070/draco/draco-body-motion.glb',buffer=fs.readFileSync(path);
let doc,bin;
for(let offset=12;offset<buffer.length;){
  const size=buffer.readUInt32LE(offset),type=buffer.readUInt32LE(offset+4);offset+=8;
  if(type===0x4e4f534a)doc=JSON.parse(buffer.subarray(offset,offset+size));
  if(type===0x004e4942)bin=buffer.subarray(offset,offset+size);offset+=size;
}
const widths={SCALAR:1,VEC3:3,VEC4:4};
function floats(index){
  const a=doc.accessors[index],view=doc.bufferViews[a.bufferView],width=widths[a.type];
  assert.equal(a.componentType,5126);assert.ok(width);
  const result=new Float32Array(a.count*width),start=(view.byteOffset||0)+(a.byteOffset||0);
  for(let row=0;row<a.count;row++)for(let k=0;k<width;k++)result[row*width+k]=bin.readFloatLE(start+row*(view.byteStride||width*4)+k*4);
  return result;
}
const nodes=doc.nodes.map((n,i)=>{
  const o=new T.Object3D();o.name=n.name||`node${i}`;
  if(n.matrix)new T.Matrix4().fromArray(n.matrix).decompose(o.position,o.quaternion,o.scale);
  else{if(n.translation)o.position.fromArray(n.translation);if(n.rotation)o.quaternion.fromArray(n.rotation);if(n.scale)o.scale.fromArray(n.scale);}
  return o;
});
doc.nodes.forEach((n,i)=>(n.children||[]).forEach(c=>nodes[i].add(nodes[c])));
const root=new T.Group();nodes.filter(n=>!n.parent).forEach(n=>root.add(n));root.updateMatrixWorld(true);
const names=doc.animations.map(a=>a.name);assert.deepEqual(names,ACTIONS);
assert.equal(doc.nodes.filter(n=>n.name?.startsWith('draco_cloth_roll_')).length,8);
const report={bytes:buffer.length,clips:names,loopSeamError:0,version:doc.nodes.find(n=>n.extras?.motionVersion)?.extras.motionVersion};
assert.equal(report.version,'story-actions-v4-hand-poses');
for(const material of ['V8_Robe_Seams_Fabric_Lining','V8_Hands_Soft_Skin_Anatomy']){
  const meshNode=doc.nodes.find(n=>n.mesh!==undefined&&doc.meshes[n.mesh].primitives.some(p=>doc.materials[p.material]?.name===material));
  const jointNames=doc.skins[meshNode.skin].joints.map(i=>doc.nodes[i].name);
  const cloth=jointNames.filter(n=>n.startsWith('draco_cloth_roll_'));
  assert.equal(cloth.length,material.includes('Robe')?8:0);
}
const clips=doc.animations.map(a=>new T.AnimationClip(a.name,-1,a.channels.map(c=>{
  const sampler=a.samplers[c.sampler],times=floats(sampler.input),values=floats(sampler.output),width=values.length/times.length;
  for(let k=0;k<width;k++)report.loopSeamError=Math.max(report.loopSeamError,Math.abs(values[k]-values[values.length-width+k]));
  const C=c.target.path==='rotation'?T.QuaternionKeyframeTrack:T.VectorKeyframeTrack;
  const property={rotation:'quaternion',translation:'position',scale:'scale'}[c.target.path];
  return new C(`${nodes[c.target.node].uuid}.${property}`,times,values);
})));
assert.ok(report.loopSeamError<1e-6);
const chest=root.getObjectByName('draco_chest'),restChest=chest.getWorldQuaternion(new T.Quaternion());
const mixer=new T.AnimationMixer(root);
function play(name,time){mixer.stopAllAction();mixer.clipAction(clips.find(c=>c.name===name)).play();mixer.setTime(time);root.updateMatrixWorld(true);}
play('bow',2.5);
const up=new T.Vector3(0,1,0).applyQuaternion(chest.getWorldQuaternion(new T.Quaternion()).multiply(restChest.clone().invert()));
report.bowTrunkDegrees=T.MathUtils.radToDeg(Math.atan2(up.z,up.y));assert.ok(report.bowTrunkDegrees>29&&report.bowTrunkDegrees<31);
play('greet',2);report.replayGreetingHandHeight=root.getObjectByName('draco_wristL').getWorldPosition(new T.Vector3()).y;assert.ok(report.replayGreetingHandHeight>1.4);
play('laugh',2.4);
const p=name=>root.getObjectByName(name).getWorldPosition(new T.Vector3());
report.laughThumbY=p('draco_fingerR0_0').sub(p('draco_wristR')).y;assert.ok(report.laughThumbY>.01);
fs.writeFileSync('web_tool/mao-5070/draco/export-validation.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
