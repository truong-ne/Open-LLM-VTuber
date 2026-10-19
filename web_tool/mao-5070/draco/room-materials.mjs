import * as T from '../3d/vendor/three.module.js';

// World-space mineral veins keep adjoining slabs continuous. This extends the
// standard PBR shader, retaining its lights, roughness and instance colors.
export function stoneMaterial(color,{roughness=.32,metalness=.12}={}){
  const material=new T.MeshStandardMaterial({color,roughness,metalness});
  material.userData.finish='veined-stone';
  material.onBeforeCompile=shader=>{
    shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 vMaoStone;')
      .replace('#include <begin_vertex>',`#include <begin_vertex>
        vec4 maoStonePoint=vec4(transformed,1.0);
        #ifdef USE_INSTANCING
          maoStonePoint=instanceMatrix*maoStonePoint;
        #endif
        vMaoStone=(modelMatrix*maoStonePoint).xyz;`);
    shader.fragmentShader=shader.fragmentShader.replace('#include <common>',`#include <common>
      varying vec3 vMaoStone;
      float maoHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
      float maoNoise(vec2 p){
        vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
        return mix(mix(maoHash(i),maoHash(i+vec2(1.,0.)),f.x),mix(maoHash(i+vec2(0.,1.)),maoHash(i+vec2(1.,1.)),f.x),f.y);
      }`)
      .replace('#include <color_fragment>',`#include <color_fragment>
        vec2 mp=vec2(vMaoStone.x+vMaoStone.y*.4,vMaoStone.z+vMaoStone.y*1.3);
        float warp=maoNoise(mp*.85)*3.0+maoNoise(mp*2.7)*.7+maoNoise(mp*7.0)*.18;
        float vein=pow(1.0-abs(sin(mp.x*1.6+mp.y*.9+warp*3.0)),18.0);
        diffuseColor.rgb=diffuseColor.rgb*(.86+.14*maoNoise(mp*5.0))+vec3(.16,.13,.09)*vein*.65;`);
  };
  material.customProgramCacheKey=()=> 'mao-veined-stone-v1';
  return material;
}

export function softBoxGeometry(){
  const geometry=new T.BoxGeometry(1,1,1,6,6,6),p=geometry.attributes.position,n=geometry.attributes.normal;
  const core=new T.Vector3(),point=new T.Vector3(),normal=new T.Vector3(),radius=.16;
  for(let i=0;i<p.count;i++){
    point.fromBufferAttribute(p,i);core.copy(point).clampScalar(-.5+radius,.5-radius);
    normal.copy(point).sub(core).normalize();point.copy(core).addScaledVector(normal,radius);
    p.setXYZ(i,point.x,point.y,point.z);n.setXYZ(i,normal.x,normal.y,normal.z);
  }
  return geometry;
}
