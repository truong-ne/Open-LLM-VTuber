import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
import {FaceRig} from '../web_tool/mao-5070/draco/face-rig.mjs';
import {createMeshFixture} from './helpers/draco_mesh_fixture.mjs';
const asset=createMeshFixture(),source=new Map();asset.traverse(m=>{if(m.isMesh)source.set(m,m.geometry.attributes.position.array.slice());});
const rig=new FaceRig(asset);assert.equal(rig.meshes.length,8);assert.equal(rig.open,0);
const face=rig.meshes.find(m=>m.material.name==='V13_Face_Reference_Lashes_Paint');
const p=face.geometry.attributes.position,delta=face.geometry.morphAttributes.position[0],before=source.get(face);
let moved=0,peak=0;
for(let i=0;i<p.count;i++){
  const y=before[i*3+1],d=Math.abs(delta.getY(i));peak=Math.max(peak,d);if(d>.0001)moved++;
  if(y>1.41)assert.ok(d<1e-6,'speech moves the eyes/forehead');
  assert.ok(Math.abs(p.getY(i)-before[i*3+1])<1e-6,'neutral pose opens the jaw');
}
assert.ok(moved>10&&peak>.008&&peak<.015,'lip opening is missing or excessive');
for(let i=0;i<30;i++)rig.update(.8,true,1/60);assert.ok(rig.open>.9);assert.ok(rig.meshes.every(m=>m.morphTargetInfluences[0]===rig.open));assert.ok(rig.overlays.every(m=>m.visible));assert.ok(rig.sourceMouth.every(m=>!m.visible));
for(let i=0;i<90;i++)rig.update(0,false,1/60);assert.equal(rig.open,0,'mouth remains open after speech ends');assert.ok(rig.sourceMouth.every(m=>m.visible));assert.ok(rig.overlays.every(m=>!m.visible));
const cavity=asset.getObjectByName('mao_mouth_cavity'),head=cavity.skeleton.bones.find(b=>b.name==='draco_head');
asset.updateMatrixWorld(true);cavity.skeleton.update();const original=cavity.getVertexPosition(0,new T.Vector3());head.position.x+=.02;asset.updateMatrixWorld(true);cavity.skeleton.update();const shifted=cavity.getVertexPosition(0,new T.Vector3());assert.ok(shifted.distanceTo(original)>.005,'cavity is detached from the head skin');
assert.equal(face.material.toneMapped,false);const shader={uniforms:{},vertexShader:'#include <morphtarget_vertex>',fragmentShader:'#include <map_fragment>'};face.material.onBeforeCompile(shader);assert.ok(shader.fragmentShader.includes('discard'),'black atlas padding is still opaque');assert.equal(shader.uniforms.maoMouthOpen,rig.mouthUniform);
// Actual generated geometry, for an offline source-mesh render (no UI control).
if(process.argv.includes('--export-geometry')){
const output=[];asset.traverse(m=>{if(!m.isMesh)return;const name=m.material.name;if(!source.has(m)||['V13_Face_Reference_Lashes_Paint','CEL5','material','material_15','V13_Jade_Iris_Original_Detail.001'].includes(name)){output.push({name,color:m.material.color.getHex(),position:Array.from(m.geometry.attributes.position.array),delta:Array.from(m.geometry.morphAttributes.position?.[0]?.array||[]),index:Array.from(m.geometry.index.array),uv:Array.from(m.geometry.attributes.uv?.array||[])});}});
fs.writeFileSync('private/draco-face-rig-geometry.json',JSON.stringify(output));
}
console.log(JSON.stringify({mouthMeshes:rig.meshes.length,affectedSkinVertices:moved,maxJawDisplacement:peak,headSkinFollows:true,closesAfterSpeech:true}));
