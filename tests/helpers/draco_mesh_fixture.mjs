import fs from 'node:fs';
import * as T from '../../web_tool/mao-5070/3d/vendor/three.module.js';
const bytes=fs.readFileSync(new URL('../../web_tool/mao-5070/draco/character.glb',import.meta.url));
let doc,bin;
for(let offset=12;offset<bytes.length;){const size=bytes.readUInt32LE(offset),kind=bytes.readUInt32LE(offset+4);offset+=8;if(kind===0x4e4f534a)doc=JSON.parse(bytes.subarray(offset,offset+size));if(kind===0x004e4942)bin=bytes.subarray(offset,offset+size);offset+=size;}
const widths={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT4:16},types={5126:Float32Array,5123:Uint16Array,5121:Uint8Array,5125:Uint32Array};
function accessor(index){
  const a=doc.accessors[index],view=doc.bufferViews[a.bufferView],C=types[a.componentType],width=widths[a.type],length=C.BYTES_PER_ELEMENT,start=(view.byteOffset||0)+(a.byteOffset||0),out=new C(a.count*width);
  for(let i=0;i<a.count;i++){const row=bin.subarray(start+i*(view.byteStride||width*length),start+i*(view.byteStride||width*length)+width*length);const aligned=new Uint8Array(row).buffer;out.set(new C(aligned),i*width);}return out;
}
export function createMeshFixture(){
  const joints=new Set(doc.skins.flatMap(s=>s.joints));
  const nodes=doc.nodes.map((n,i)=>{
    let o;
    if(n.mesh!==undefined){
      const p=doc.meshes[n.mesh].primitives[0],geometry=new T.BufferGeometry();
      for(const [from,to] of Object.entries({POSITION:'position',NORMAL:'normal',TEXCOORD_0:'uv',JOINTS_0:'skinIndex',WEIGHTS_0:'skinWeight'}))if(p.attributes[from]!==undefined){const index=p.attributes[from];geometry.setAttribute(to,new T.BufferAttribute(accessor(index),widths[doc.accessors[index].type]));}
      geometry.setIndex(new T.BufferAttribute(accessor(p.indices),1));o=new T.SkinnedMesh(geometry,new T.MeshBasicMaterial());o.material.name=doc.materials[p.material].name;
    }else o=joints.has(i)?new T.Bone():new T.Object3D();
    o.name=n.name||`node${i}`;
    if(n.matrix)new T.Matrix4().fromArray(n.matrix).decompose(o.position,o.quaternion,o.scale);
    else{if(n.translation)o.position.fromArray(n.translation);if(n.rotation)o.quaternion.fromArray(n.rotation);if(n.scale)o.scale.fromArray(n.scale);}return o;
  });
  doc.nodes.forEach((n,i)=>(n.children||[]).forEach(c=>nodes[i].add(nodes[c])));
  const root=new T.Group();nodes.filter(n=>!n.parent).forEach(n=>root.add(n));root.updateMatrixWorld(true);
  const skins=doc.skins.map(s=>{const inv=accessor(s.inverseBindMatrices);return new T.Skeleton(s.joints.map(i=>nodes[i]),s.joints.map((_,i)=>new T.Matrix4().fromArray(inv,i*16)));});
  doc.nodes.forEach((n,i)=>{if(n.skin!==undefined)nodes[i].bind(skins[n.skin],new T.Matrix4());});
  return root;
}

// Match the native renderer's display scale and ankle-centered simulation frame.
export function createNativeMeshFixture(){
  const asset=createMeshFixture(),root=new T.Group(),wrapper=new T.Group();root.add(wrapper);wrapper.add(asset);asset.updateMatrixWorld(true);
  const bounds=new T.Box3().setFromObject(asset),center=bounds.getCenter(new T.Vector3()),scale=1.8/bounds.getSize(new T.Vector3()).y;
  wrapper.scale.setScalar(scale);wrapper.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale);wrapper.updateMatrixWorld(true);
  const ankle=asset.getObjectByName('draco_ankleL').getWorldPosition(new T.Vector3()).add(asset.getObjectByName('draco_ankleR').getWorldPosition(new T.Vector3())).multiplyScalar(.5);
  wrapper.position.x-=ankle.x;wrapper.position.z-=ankle.z;wrapper.updateMatrixWorld(true);
  return {asset,root};
}
