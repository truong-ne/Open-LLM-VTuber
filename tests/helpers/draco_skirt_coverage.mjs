import * as T from '../../web_tool/mao-5070/3d/vendor/three.module.js';

// Check rendered skin against horizontal sections of the actual skinned skirt,
// in the pelvis frame. Bone-tail capsules alone cannot detect a triangle poke.
export function skirtCoverageProbe(actor,{includeLining=true,levels=[-.1787,-.1587,-.1387,-.1187,-.0987,-.0787,-.0587],scaled=false}={}){
  const skirts=[];let legs;actor.asset.traverse(m=>{if(['V10_Skirt_Gradient_And_AO_Paint',...(includeLining?['mao_skirt_lining']:[])].includes(m.material?.name))skirts.push(m);if(m.material?.name==='V16_Original_Leg_Texture_Local_Edge_Repair')legs=m;});
  const point=new T.Vector3(),center=new T.Vector3(),rotation=new T.Quaternion();
  const sections=(mesh)=>{
    mesh.skeleton.update();const vertices=[];
    for(let i=0;i<mesh.geometry.attributes.position.count;i++){mesh.getVertexPosition(i,point).applyMatrix4(mesh.matrixWorld).sub(center).applyQuaternion(rotation);vertices.push(point.clone());}
    const ids=mesh.geometry.index.array;
    const section=y=>{
      const lines=[];
      for(let i=0;i<ids.length;i+=3){const points=[];
        for(let j=0;j<3;j++){const a=vertices[ids[i+j]],b=vertices[ids[i+(j+1)%3]];if((a.y>y)===(b.y>y))continue;const t=(y-a.y)/(b.y-a.y);points.push({x:a.x+(b.x-a.x)*t,z:a.z+(b.z-a.z)*t});}
        if(points.length===2)lines.push(points);
      }
      return lines;
    };
    section.vertices=vertices;section.indices=ids;return section;
  };
  return ()=>{
    actor.asset.updateMatrixWorld(true);actor.joints.pelvis.getWorldPosition(center);
    rotation.copy(actor.joints.pelvis.getWorldQuaternion(new T.Quaternion())).multiply(actor.rest.get(actor.joints.pelvis).worldInverse).invert();
    const cloth=skirts.map(sections),skin=sections(legs);let maxOutside=0,outside=0,worstY=0,worstPoint;
    // Skin below the actual pleated hem is expected. The old flat underskirt
    // extended past the original hem just to satisfy a fixed-Y coverage test.
    // Test coverage above the local animated hem, and audit hem travel itself
    // separately so lifting the whole garment cannot hide a regression.
    for(const level of levels){const y=level*(scaled?actor.dynamics.unit:1);
      const boundary=cloth.flatMap(section=>section(y));
      for(const line of skin(y))for(const t of [0,.5]){
        const p={x:line[0].x*(1-t)+line[1].x*t,z:line[0].z*(1-t)+line[1].z*t},radius=Math.hypot(p.x,p.z);if(radius<1e-6)continue;
        const dx=p.x/radius,dz=p.z/radius;let outer=0;
        for(const [a,b] of boundary){
          const vx=b.x-a.x,vz=b.z-a.z,den=dx*vz-dz*vx;if(Math.abs(den)<1e-10)continue;
          const r=(a.x*vz-a.z*vx)/den,u=(a.x*dz-a.z*dx)/den;
          if(u>=0&&u<=1&&r>outer)outer=r;
        }
        const distance=radius-outer;
        if(distance>.0001){
          let localHem=Infinity;
          for(const section of cloth)for(let i=0;i<section.indices.length;i+=3)for(let j=0;j<3;j++){
            const a=section.vertices[section.indices[i+j]],b=section.vertices[section.indices[i+(j+1)%3]],sa=dx*a.z-dz*a.x,sb=dx*b.z-dz*b.x;
            if((sa>0)===(sb>0)||Math.abs(sa-sb)<1e-12)continue;
            const t=sa/(sa-sb),r=dx*(a.x+(b.x-a.x)*t)+dz*(a.z+(b.z-a.z)*t);
            if(r>0)localHem=Math.min(localHem,a.y+(b.y-a.y)*t);
          }
          if(y<=localHem+.001*(scaled?actor.dynamics.unit:1))continue;
          outside++;if(distance>maxOutside){maxOutside=distance;worstY=y;worstPoint={...p,boundary:boundary.length};}
        }
      }
    }
    return {maxOutside,outside,worstY,worstPoint};
  };
}
