import * as T from '../3d/vendor/three.module.js';

export const ROLL_IDS=[80,117,119,121,167,204,206,208];
export const clothBoneName=id=>`draco_cloth_roll_${String(id).padStart(4,'0')}`;

// The robe's bell sleeves open to a full forearm length around the wrist; in a dance they
// hide the forearm and flap wide. Pull the part of the sleeve that hangs from each
// elbow toward the forearm axis: what lies within `keep` (fractions of the forearm length)
// of the axis is untouched, the rest of its distance is scaled by `scale`. Vertices only
// partly weighted to the forearm move partly, so the seam to the body stays closed. The
// robe is unlit, so normals need no rebuild. Runs once per mesh.
export function narrowSleeves(asset,{keep=.18,scale=.4}={}){
  const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
  asset.updateMatrixWorld(true);
  asset.traverse(mesh=>{
    if(!mesh.isSkinnedMesh||mesh.userData.sleevesNarrowed)return;
    const materials=Array.isArray(mesh.material)?mesh.material:[mesh.material];
    if(!materials.some(m=>m.name==='V8_Robe_Seams_Fabric_Lining'))return;
    const {bones,boneInverses}=mesh.skeleton,bindPosition=j=>new T.Vector3().setFromMatrixPosition(boneInverses[j].clone().invert());
    const below=(bone,name)=>{for(let b=bone;b;b=b.parent)if(b.name===name)return true;return false;};
    const sides=['L','R'].map(side=>{
      const elbow=bones.findIndex(b=>b.name==='draco_elbow'+side),wrist=bones.findIndex(b=>b.name==='draco_wrist'+side);
      if(elbow<0||wrist<0)return null;
      const a=bindPosition(elbow),axis=bindPosition(wrist).sub(a),length=axis.length();
      return {a,axis:axis.normalize(),length,joints:new Set(bones.map((b,j)=>below(b,'draco_elbow'+side)?j:-1).filter(j=>j>=0))};
    }).filter(Boolean);
    const position=mesh.geometry.attributes.position,index=mesh.geometry.attributes.skinIndex,weight=mesh.geometry.attributes.skinWeight;
    // Not mesh.bindMatrixInverse: in the default attached mode three.js resets it to the
    // inverse of the mesh's world matrix on every update, which here includes a rotation.
    const v=new T.Vector3(),offset=new T.Vector3(),toBind=mesh.bindMatrix,fromBind=mesh.bindMatrix.clone().invert();
    for(let k=0;k<position.count;k++){
      for(const side of sides){
        let w=0;for(let c=0;c<4;c++)if(side.joints.has(index.getComponent(k,c)))w+=weight.getComponent(k,c);
        if(w<.05)continue;
        v.fromBufferAttribute(position,k).applyMatrix4(toBind);
        const along=offset.copy(v).sub(side.a).dot(side.axis);
        offset.copy(v).sub(side.a).addScaledVector(side.axis,-along);
        const r=offset.length()/side.length;
        if(r<=keep)continue;
        const target=keep+(r-keep)*scale,f=1+(target/r-1)*smooth(w/.6);
        v.copy(side.a).addScaledVector(side.axis,along).addScaledVector(offset,f).applyMatrix4(fromBind);
        position.setXYZ(k,v.x,v.y,v.z);
      }
    }
    position.needsUpdate=true;mesh.geometry.computeBoundingBox();mesh.geometry.computeBoundingSphere();
    mesh.userData.sleevesNarrowed=true;
  });
}

// The robe is a separate material/mesh. Give its sleeve weights independent
// roll joints: the wrist may turn inside a loose sleeve without wringing it.
// Bind transforms, geometry, UVs and vertex weights remain unchanged.
export function prepareGarmentRig(asset){
  if(asset.getObjectByName(clothBoneName(80)))return;
  const replacements=new Map();
  for(const id of ROLL_IDS){
    const source=asset.getObjectByName(`draco_bone_${String(id).padStart(4,'0')}`);
    const proxy=new T.Bone();proxy.name=clothBoneName(id);
    proxy.position.copy(source.position);proxy.quaternion.copy(source.quaternion);proxy.scale.copy(source.scale);
    source.parent.add(proxy);replacements.set(source,proxy);
  }
  asset.updateMatrixWorld(true);
  asset.traverse(mesh=>{
    if(!mesh.isSkinnedMesh)return;
    const materials=Array.isArray(mesh.material)?mesh.material:[mesh.material];
    if(!materials.some(m=>m.name==='V8_Robe_Seams_Fabric_Lining'))return;
    const source=mesh.skeleton;
    mesh.bind(new T.Skeleton(source.bones.map(b=>replacements.get(b)||b),source.boneInverses.map(m=>m.clone())),mesh.bindMatrix);
    mesh.userData.looseSleeveRoll=true;
  });
}
