import fs from 'node:fs';
import * as T from '../web_tool/mao-5070/3d/vendor/three.module.js';
const buffer=fs.readFileSync(process.argv[2]||'C:/Users/LeDinhTruong/Downloads/draco_malfoy.glb');
let document,bin;for(let offset=12;offset<buffer.length;){const length=buffer.readUInt32LE(offset),type=buffer.readUInt32LE(offset+4);offset+=8;if(type===0x4e4f534a)document=JSON.parse(buffer.subarray(offset,offset+length));if(type===0x004e4942)bin=buffer.subarray(offset,offset+length);offset+=length;}
const nodes=document.nodes.map((node,i)=>{const o=new T.Object3D();o.name=node.name||`node${i}`;if(node.matrix)o.matrix.fromArray(node.matrix).decompose(o.position,o.quaternion,o.scale);else{if(node.translation)o.position.fromArray(node.translation);if(node.rotation)o.quaternion.fromArray(node.rotation);if(node.scale)o.scale.fromArray(node.scale);}return o;});
document.nodes.forEach((node,i)=>(node.children||[]).forEach(c=>nodes[i].add(nodes[c])));nodes.filter(n=>!n.parent).forEach(n=>n.updateMatrixWorld(true));
const weight=new Map(),vertexCount=new Map();
const size={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16},bytes={5121:1,5123:2,5125:4,5126:4};
function accessor(index,row,col){const a=document.accessors[index],bv=document.bufferViews[a.bufferView],length=bytes[a.componentType],at=(bv.byteOffset||0)+(a.byteOffset||0)+row*(bv.byteStride||length*size[a.type])+col*length;return a.componentType===5126?bin.readFloatLE(at):a.componentType===5123?bin.readUInt16LE(at):a.componentType===5121?bin.readUInt8(at):bin.readUInt32LE(at);}
for(const node of document.nodes){if(node.mesh===undefined||node.skin===undefined)continue;const skin=document.skins[node.skin];for(const p of document.meshes[node.mesh].primitives){const joints=p.attributes.JOINTS_0,weights=p.attributes.WEIGHTS_0;if(joints===undefined)continue;for(let row=0;row<document.accessors[joints].count;row++)for(let c=0;c<4;c++){const joint=skin.joints[accessor(joints,row,c)],w=accessor(weights,row,c);weight.set(joint,(weight.get(joint)||0)+w);if(w>.05)vertexCount.set(joint,(vertexCount.get(joint)||0)+1);}}}
const jointIds=new Set(document.skins.flatMap(s=>s.joints)),report=[];
for(const id of jointIds){const node=nodes[id],p=node.getWorldPosition(new T.Vector3());report.push({id,name:node.name,parent:nodes.indexOf(node.parent),children:document.nodes[id].children||[],position:p.toArray().map(v=>+v.toFixed(5)),weight:+(weight.get(id)||0).toFixed(1),vertices:vertexCount.get(id)||0});}
fs.writeFileSync('private/draco-rig-audit.json',JSON.stringify(report,null,2));
console.log(JSON.stringify({roots:nodes.filter(n=>!n.parent).map(n=>({name:n.name,scale:n.scale.toArray()})),important:report.filter(n=>n.weight>250).sort((a,b)=>b.weight-a.weight).slice(0,75)},null,2));
