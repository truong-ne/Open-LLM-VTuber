import fs from 'node:fs';
import * as T from '../../web_tool/mao-5070/3d/vendor/three.module.js';

const buffer=fs.readFileSync(new URL('../../web_tool/mao-5070/draco/character.glb',import.meta.url));
let document;
for(let offset=12;offset<buffer.length;){
  const length=buffer.readUInt32LE(offset),type=buffer.readUInt32LE(offset+4);offset+=8;
  if(type===0x4e4f534a)document=JSON.parse(buffer.subarray(offset,offset+length));offset+=length;
}
export const boneCount=document.skins[0].joints.length;
export function createDracoRig(){
  const ids=new Set(document.skins.flatMap(s=>s.joints));
  const nodes=document.nodes.map((n,i)=>{
    const b=ids.has(i)?new T.Bone():new T.Object3D();b.name=n.name||`node${i}`;
    if(n.matrix)new T.Matrix4().fromArray(n.matrix).decompose(b.position,b.quaternion,b.scale);
    else{if(n.translation)b.position.fromArray(n.translation);if(n.rotation)b.quaternion.fromArray(n.rotation);if(n.scale)b.scale.fromArray(n.scale);}
    return b;
  });
  document.nodes.forEach((n,i)=>(n.children||[]).forEach(c=>nodes[i].add(nodes[c])));
  const root=new T.Group();nodes.filter(n=>!n.parent).forEach(n=>root.add(n));root.updateMatrixWorld(true);return root;
}
