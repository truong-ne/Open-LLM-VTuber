import * as T from '../3d/vendor/three.module.js';

export const ROLL_IDS=[80,117,119,121,167,204,206,208];
export const clothBoneName=id=>`draco_cloth_roll_${String(id).padStart(4,'0')}`;

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
