import * as T from '../3d/vendor/three.module.js';

const MOUTH_Y=1.378535,MOUTH_Z=.078;
const FACE='V13_Face_Reference_Lashes_Paint';
const LIPS='CEL5',TEETH='material',TONGUE='material_15',IRIS='V13_Jade_Iris_Original_Detail.001';
const mouthNames=new Set([FACE,LIPS,TEETH,TONGUE]);
const clamp=v=>Math.max(0,Math.min(1,v));
export function mouthWeight(x,y,z){const t=clamp(1-Math.abs(y-MOUTH_Y)/.030);return z>.045?Math.exp(-Math.pow(x/.023,4))*t*t*(3-2*t):0;}
export function mouthDelta(x,y,z,teeth=false){
  const weight=mouthWeight(x,y,z),lower=clamp((MOUTH_Y+.0008-y)/.0035);
  const vertical=(.0017*(1-lower)-.014*lower)*weight*(teeth?.30:1);
  return [x*-.10*weight,vertical,.0012*weight*lower];
}
function finishMaterial(material,mouthUniform){
  // Source maps are painted/unlit. Filmic tone mapping washes out skin, hair
  // and the jade iris; preserve their authored sRGB colors instead.
  material.toneMapped=false;
  const name=material.name;
  const atlas=[FACE,LIPS,'V13_Reference_Upper_Lash_Curved_Mask.001','V8_Hair_Fine_Luminous_Strands'].includes(name);
  const iris=name===IRIS;
  const mouth=name===FACE||name===LIPS;
  if(atlas||iris){
    material.onBeforeCompile=shader=>{
      if(mouth){
        shader.uniforms.maoMouthOpen=mouthUniform;
        shader.vertexShader='varying vec3 maoFacePosition;\n'+shader.vertexShader.replace('#include <morphtarget_vertex>','#include <morphtarget_vertex>\nmaoFacePosition = transformed;');
        shader.fragmentShader='varying vec3 maoFacePosition; uniform float maoMouthOpen;\n'+shader.fragmentShader;
      }
      shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
        ${atlas?'if (max(diffuseColor.r,max(diffuseColor.g,diffuseColor.b)) < 0.0008) discard;':''}
        ${mouth?`if(maoMouthOpen > .02 && maoFacePosition.z > .06){vec2 mouthPoint=(maoFacePosition.xy-vec2(0.,${MOUTH_Y}-.0055*maoMouthOpen))/vec2(.0109,.0012+.007*maoMouthOpen); if(dot(mouthPoint,mouthPoint)<1.) discard;}`:''}
        ${iris?'float eyeLuma=dot(diffuseColor.rgb,vec3(.2126,.7152,.0722)); diffuseColor.rgb=pow(clamp(mix(vec3(eyeLuma),diffuseColor.rgb,1.06),0.0,1.0),vec3(1.18));':''}`);
    };
    material.customProgramCacheKey=()=>`mao-face-v2-${atlas}-${iris}-${mouth}`;
  }
  if(name===FACE){material.polygonOffset=true;material.polygonOffsetFactor=1;material.polygonOffsetUnits=1;}
  material.needsUpdate=true;
}

export class FaceRig{
  constructor(asset){
    this.meshes=[];this.open=0;this.peak=0;this.mouthUniform={value:0};this.sourceMouth=[];this.overlays=[];
    let face;
    asset.traverse(mesh=>{
      if(!mesh.isMesh)return;
      mesh.material=Array.isArray(mesh.material)?mesh.material.map(m=>m.clone()):mesh.material.clone();
      const materials=Array.isArray(mesh.material)?mesh.material:[mesh.material];materials.forEach(m=>finishMaterial(m,this.mouthUniform));
      const name=materials[0].name;
      if(name===FACE)face=mesh;
      if(name===IRIS){mesh.geometry=mesh.geometry.clone();const p=mesh.geometry.attributes.position;for(let i=0;i<p.count;i++)p.setZ(i,p.getZ(i)+.00065);mesh.geometry.computeBoundingSphere();}
      if(!mouthNames.has(name))return;
      if(name!==FACE)this.sourceMouth.push(mesh);
      mesh.geometry=mesh.geometry.clone();const p=mesh.geometry.attributes.position,delta=new Float32Array(p.count*3);
      for(let i=0;i<p.count;i++){
        const x=p.getX(i),y=p.getY(i),z=p.getZ(i),weight=mouthWeight(x,y,z);
        // Widen the lips slightly, with a smooth falloff into the cheeks.
        p.setX(i,x*(1+.20*weight));
        delta.set(mouthDelta(p.getX(i),y,z,name===TEETH),i*3);
      }
      this.addTarget(mesh,delta);mesh.geometry.computeBoundingSphere();
    });
    if(!face)throw new Error('Không tìm thấy mesh mặt Draco');
    const headIndex=face.skeleton.bones.findIndex(b=>b.name==='draco_head');if(headIndex<0)throw new Error('Không tìm thấy khớp đầu Draco');
    // A skinned mouth cavity sits behind the existing lips/teeth/tongue. It
    // follows the head through its real skin, including during bows and turns.
    const positions=[],deltas=[],indices=[],skin=[],weights=[],segments=40;
    for(let i=0;i<=segments;i++){
      const angle=(i-1)/segments*Math.PI*2,x=i===0?0:Math.cos(angle)*.0128,y=i===0?0:Math.sin(angle)*.002;
      positions.push(x,MOUTH_Y+y,MOUTH_Z-.001);
      deltas.push(0,-.0055+(i===0?0:Math.sin(angle)*.007),0);
      skin.push(headIndex,0,0,0);weights.push(1,0,0,0);
      if(i>1)indices.push(0,i-1,i);
    }
    indices.push(0,segments,1);
    const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(positions,3));geometry.setAttribute('skinIndex',new T.Uint16BufferAttribute(skin,4));geometry.setAttribute('skinWeight',new T.Float32BufferAttribute(weights,4));geometry.setIndex(indices);geometry.computeVertexNormals();
    const cavity=new T.SkinnedMesh(geometry,new T.MeshBasicMaterial({color:0x51202a,side:T.DoubleSide,toneMapped:false}));cavity.material.name='mao_mouth_inside';
    cavity.name='mao_mouth_cavity';cavity.position.copy(face.position);cavity.quaternion.copy(face.quaternion);cavity.scale.copy(face.scale);cavity.frustumCulled=false;face.parent.add(cavity);cavity.bind(face.skeleton,face.bindMatrix);this.addTarget(cavity,new Float32Array(deltas));
    const make=(name,position,delta,index,color)=>{
      const geo=new T.BufferGeometry(),joints=[],weights=[];
      for(let i=0;i<position.length/3;i++){joints.push(headIndex,0,0,0);weights.push(1,0,0,0);}
      geo.setAttribute('position',new T.Float32BufferAttribute(position,3));geo.setAttribute('skinIndex',new T.Uint16BufferAttribute(joints,4));geo.setAttribute('skinWeight',new T.Float32BufferAttribute(weights,4));geo.setIndex(index);geo.computeVertexNormals();
      const material=new T.MeshBasicMaterial({color,side:T.DoubleSide,toneMapped:false});material.name=name;
      const mesh=new T.SkinnedMesh(geo,material);mesh.name=name;mesh.position.copy(face.position);mesh.quaternion.copy(face.quaternion);mesh.scale.copy(face.scale);mesh.frustumCulled=false;face.parent.add(mesh);mesh.bind(face.skeleton,face.bindMatrix);this.addTarget(mesh,new Float32Array(delta));this.overlays.push(mesh);mesh.visible=false;
    };
    const rim=[],rimDelta=[],rimIndex=[];
    for(let i=0;i<40;i++)for(let ring=0;ring<2;ring++){
      const angle=i/40*Math.PI*2,rx=ring?.0123:.0109,ry=ring?.0025:.0012;
      rim.push(Math.cos(angle)*rx,MOUTH_Y+Math.sin(angle)*ry,.089);
      rimDelta.push(0,-.0055+Math.sin(angle)*.007,0);
      if(i<39){const a=i*2;rimIndex.push(a,a+2,a+1,a+1,a+2,a+3);}
    }
    rimIndex.push(78,0,79,79,0,1);make('mao_lip_rim',rim,rimDelta,rimIndex,0xd9a99b);
    const tooth=[],toothDelta=[],toothIndex=[];
    for(let i=0;i<=8;i++)for(let row=0;row<2;row++){
      const x=(i/8*2-1)*.0087;tooth.push(x,MOUTH_Y+.0012-.0015*(x/.0087)**2-row*.0012,.080);toothDelta.push(0,.0015,0);
      if(i<8){const a=i*2;toothIndex.push(a,a+2,a+1,a+1,a+2,a+3);}
    }
    make('mao_upper_teeth',tooth,toothDelta,toothIndex,0xfff5df);
    const tongue=[],tongueDelta=[],tongueIndex=[];
    for(let i=0;i<=32;i++){
      const angle=(i-1)/32*Math.PI*2; tongue.push(i?Math.cos(angle)*.006:0,MOUTH_Y-.0006+(i?Math.sin(angle)*.0016:0),.079);tongueDelta.push(0,-.009,0);if(i>1)tongueIndex.push(0,i-1,i);
    }
    tongueIndex.push(0,32,1);make('mao_tongue',tongue,tongueDelta,tongueIndex,0xce7480);
  }
  addTarget(mesh,delta){
    mesh.geometry.morphTargetsRelative=true;
    mesh.geometry.morphAttributes.position=[new T.Float32BufferAttribute(delta,3)];
    mesh.updateMorphTargets();mesh.morphTargetDictionary={mouthOpen:0};mesh.morphTargetInfluences[0]=0;this.meshes.push(mesh);
  }
  update(volume,playing,dt){
    const target=playing?clamp((volume-.045)/.70):0;
    const rate=target>this.open?28:16;this.open+=(target-this.open)*(1-Math.exp(-Math.max(0,dt)*rate));
    if(this.open<.001)this.open=0;this.peak=Math.max(this.peak,this.open);
    this.mouthUniform.value=this.open;
    for(const mesh of this.meshes)mesh.morphTargetInfluences[0]=this.open;
    for(const mesh of this.sourceMouth)mesh.visible=this.open<=.025;
    for(const mesh of this.overlays)mesh.visible=this.open>.025;
    return this.open;
  }
}
