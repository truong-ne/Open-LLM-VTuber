import * as T from '../3d/vendor/three.module.js';
import {FaceRig} from './face-rig.mjs?v=2';

export const FACE_PRESETS={neutral:'Tự nhiên',smile:'Cười nhẹ',squint:'Mắt ><',flat:'Mắt --',surprised:'Ngơ ngác'};
const FACE='V13_Face_Reference_Lashes_Paint',LASH='V13_Reference_Upper_Lash_Curved_Mask.001',DETAIL='CEL5_Material.001',IRIS='V13_Jade_Iris_Original_Detail.001';
const CY=1.4255,MY=1.378535,clamp=T.MathUtils.clamp;
const ease=(a,b,x)=>1-T.MathUtils.smoothstep(Math.abs(x),a,b);
export function eyelidDelta(x,y,z,open=false){
  if(z<.04)return [0,0,0];
  const cx=x<0?-.0323:.0323,dx=x-cx,dy=y-CY;
  const w=ease(.020,.036,dx)*ease(.014,.027,dy);
  const line=CY-.001+.0015*(dx/.022)**2;
  return [0,open?dy*.20*w:(line-y)*w,0];
}
function appendTarget(mesh,name,delta){
  const old=mesh.morphTargetInfluences?.slice()||[],names={...mesh.morphTargetDictionary};
  const targets=mesh.geometry.morphAttributes.position||(mesh.geometry.morphAttributes.position=[]),index=targets.length;
  targets.push(new T.Float32BufferAttribute(delta,3));mesh.geometry.morphTargetsRelative=true;mesh.updateMorphTargets();
  mesh.morphTargetDictionary={...names,[name]:index};old.forEach((value,i)=>{mesh.morphTargetInfluences[i]=value;});return index;
}

export class PerformanceFaceRig extends FaceRig{
  constructor(asset){
    super(asset);this.time=0;this.expression='neutral';this.weights=Object.fromEntries(Object.keys(FACE_PRESETS).map(k=>[k,0]));this.nextBlink=2.4;this.blinkStart=-10;this.eyeClose=0;this.targets=[];this.inks=[];this.smileTargets=[];this.smileUniform={value:0};
    for(const mesh of this.meshes){
      const p=mesh.geometry.attributes.position,delta=new Float32Array(p.count*3);
      for(let i=0;i<p.count;i++){
        const x=p.getX(i),y=p.getY(i),z=p.getZ(i),w=ease(.017,.032,y-MY)*ease(.015,.030,x)*(z>.05?1:0);
        delta[i*3]=x*.18*w;delta[i*3+1]=.003*Math.min(1.4,Math.abs(x)/.012)**2*w;
      }
      this.smileTargets.push({mesh,index:appendTarget(mesh,'previewSmile',delta)});
      if(['V13_Face_Reference_Lashes_Paint','CEL5'].includes(mesh.material.name)){
        const previous=mesh.material.onBeforeCompile,key=mesh.material.customProgramCacheKey();
        mesh.material.onBeforeCompile=shader=>{
          previous(shader);shader.uniforms.previewSmile=this.smileUniform;
          shader.fragmentShader='uniform float previewSmile;\n'+shader.fragmentShader
            .replace('vec2(0.,1.378535-.0055*maoMouthOpen)','vec2(0.,1.378535-.0055*maoMouthOpen+previewSmile*.003*pow(clamp(abs(maoFacePosition.x)/.012,0.,1.4),2.))')
            .replace('vec2(.0109,.0012+.007*maoMouthOpen)','vec2(.0109*(1.+.18*previewSmile),.0012+.007*maoMouthOpen)');
        };
        mesh.material.customProgramCacheKey=()=>key+'-preview-smile';mesh.material.needsUpdate=true;
      }
    }
    asset.traverse(m=>{
      if(!m.isMesh)return;const name=m.material.name;
      if(name===FACE)this.face=m;if(name===LASH)this.lash=m;if(name===IRIS)this.iris=m;
      if(![FACE,LASH,DETAIL].includes(name))return;
      if(name!==FACE)m.geometry=m.geometry.clone();
      const p=m.geometry.attributes.position,closed=new Float32Array(p.count*3),wide=new Float32Array(p.count*3),brow=new Float32Array(p.count*3);
      for(let i=0;i<p.count;i++){
        const x=p.getX(i),y=p.getY(i),z=p.getZ(i);closed.set(eyelidDelta(x,y,z),i*3);wide.set(eyelidDelta(x,y,z,true),i*3);
        if(y>1.441&&y<1.466&&z>.04){const w=ease(.018,.034,Math.abs(x)-.0323)*ease(.009,.015,y-1.453);brow[i*3+1]=.004*w;}
      }
      this.targets.push({mesh:m,closed:appendTarget(m,'eyeClose',closed),wide:appendTarget(m,'eyeWide',wide),brow:appendTarget(m,'browRaise',brow),closedDelta:closed});
    });
    const irisPosition=this.iris.geometry.attributes.position,irisDelta=new Float32Array(irisPosition.count*3);
    for(let i=0;i<irisPosition.count;i++){
      const x=irisPosition.getX(i),cx=x<0?-.0323:.0323;
      irisDelta[i*3]=-(x-cx)*.25;irisDelta[i*3+1]=-(irisPosition.getY(i)-CY)*.25;
    }
    this.irisSurprise=appendTarget(this.iris,'previewSurprise',irisDelta);
    const face=this.face;this.headIndex=face.skeleton.bones.findIndex(b=>b.name==='draco_head');
    const positions=face.geometry.attributes.position,index=face.geometry.index.array,closed=this.targets.find(t=>t.mesh===face).closedDelta;
    // Sample the *closed* face surface so ink sits on the skin in side views.
    this.surfaceZ=(x,y)=>{
      let top=-Infinity;
      for(let j=0;j<index.length;j+=3){
        const ids=[index[j],index[j+1],index[j+2]],v=ids.map(i=>[positions.getX(i),positions.getY(i)+closed[i*3+1],positions.getZ(i)]);
        const [a,b,c]=v,den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(den)<1e-12)continue;
        const u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den,w=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den;
        if(u>=-1e-5&&w>=-1e-5&&u+w<=1.00001)top=Math.max(top,u*a[2]+w*b[2]+(1-u-w)*c[2]);
      }
      return top>.04?top:.077-Math.abs(x)*.15;
    };
    for(const [style,points] of Object.entries({
      squint:[[-.011,.006],[.009,0],[-.011,-.006]],
      flat:[[-.014,0],[0,-.0004],[.014,0]],
      blink:[[-.016,.002],[0,-.001],[.016,.002]]
    }))for(const side of [-1,1]){
      const path=new T.CurvePath();
      const vertices=points.map(([x,y])=>{const px=side*.0323+x*(style==='squint'?-side:1),py=CY+y;return new T.Vector3(px,py,this.surfaceZ(px,py)+.0012);});
      for(let i=1;i<vertices.length;i++)path.add(new T.LineCurve3(vertices[i-1],vertices[i]));
      const mesh=this.bind(new T.TubeGeometry(path,32,style==='squint'?.0015:.0011,6,false),new T.MeshBasicMaterial({color:0x4b3934,transparent:true,opacity:0,toneMapped:false,depthWrite:false}),`preview-eye-${style}-${side}`);
      this.inks.push({style,mesh});
    }
    this.gaze=['draco_bone_0019','draco_bone_0021'].map(name=>{
      const bone=asset.getObjectByName(name),world=bone.getWorldQuaternion(new T.Quaternion());return {bone,local:bone.quaternion.clone(),world,inverse:world.clone().invert()};
    });
    this.gazeDelta=new T.Quaternion();this.gazeEuler=new T.Euler();
  }
  bind(geometry,material,name){
    const count=geometry.attributes.position.count,skin=new Uint16Array(count*4),weight=new Float32Array(count*4);
    for(let i=0;i<count;i++){skin[i*4]=this.headIndex;weight[i*4]=1;}
    geometry.setAttribute('skinIndex',new T.Uint16BufferAttribute(skin,4));geometry.setAttribute('skinWeight',new T.Float32BufferAttribute(weight,4));
    const mesh=new T.SkinnedMesh(geometry,material),face=this.face;mesh.name=name;material.name=name;mesh.position.copy(face.position);mesh.quaternion.copy(face.quaternion);mesh.scale.copy(face.scale);mesh.frustumCulled=false;
    face.parent.add(mesh);mesh.updateMatrixWorld(true);mesh.bind(face.skeleton,face.bindMatrix);mesh.updateMatrixWorld(true);return mesh;
  }
  setExpression(name){if(!(name in FACE_PRESETS))return false;this.expression=name;return true;}
  update(volume,playing,dt){
    dt=clamp(Number.isFinite(dt)?dt:0,0,.1);this.time+=dt;
    for(const name of Object.keys(this.weights))this.weights[name]+=((name===this.expression?1:0)-this.weights[name])*(1-Math.exp(-dt*12));
    if(this.time>=this.nextBlink){this.blinkStart=this.time;this.nextBlink=this.time+3.0+.65*(1+Math.sin(this.time*1.7));}
    const blinkT=this.time-this.blinkStart,blink=blinkT<.075?T.MathUtils.smoothstep(blinkT,0,.075):1-T.MathUtils.smoothstep(blinkT,.09,.23);
    const w=this.weights,styled=clamp(w.squint+w.flat,0,1);this.eyeClose=clamp(styled+(1-styled)*blink,0,1);
    const smile=w.smile+w.squint,forced=Math.max(w.surprised*.38,smile*.22,w.flat*.09);
    const open=super.update(Math.max(Number.isFinite(volume)?volume:0,.045+.70*forced),playing||forced>.001,dt);
    this.smileUniform.value=clamp(smile,0,1);for(const target of this.smileTargets)target.mesh.morphTargetInfluences[target.index]=this.smileUniform.value;
    for(const target of this.targets){target.mesh.morphTargetInfluences[target.closed]=this.eyeClose;target.mesh.morphTargetInfluences[target.wide]=w.surprised*(1-this.eyeClose);target.mesh.morphTargetInfluences[target.brow]=w.surprised;}
    this.iris.visible=this.eyeClose<.88;this.lash.visible=this.eyeClose<.72;
    this.iris.morphTargetInfluences[this.irisSurprise]=w.surprised;
    for(const {style,mesh} of this.inks){const opacity=style==='blink'?(1-styled)*this.eyeClose:(w[style]*this.eyeClose);mesh.material.opacity=opacity;mesh.visible=opacity>.02;}
    for(const eye of this.gaze){
      const yaw=(Math.sin(this.time*.68)*.024+w.surprised*Math.sin(this.time*1.8)*.045)*(1-this.eyeClose);
      this.gazeDelta.setFromEuler(this.gazeEuler.set(w.surprised*-.025,yaw,0));eye.bone.quaternion.copy(eye.local).multiply(eye.inverse.clone().multiply(this.gazeDelta).multiply(eye.world));
    }
    return open;
  }
}
