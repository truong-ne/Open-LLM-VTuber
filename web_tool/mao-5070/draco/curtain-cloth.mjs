import * as T from '../3d/vendor/three.module.js';

export const CURTAIN_ART=new URL('./assets/mao-theatre-curtain-v2.png',import.meta.url).href;
const clamp=x=>Math.max(0,Math.min(1,x));

// The carrier leads and the heavy hem follows. Both leaves gather into their
// wings; they do not slide across the screen as two rigid rectangles.
export function curtainVertex(side,u,v,closed,phase='closing',time=0){
  const p=clamp(closed),motion=Math.sin(Math.PI*p),direction=phase==='opening'?-1:1;
  const lag=direction*.065*motion*(v-.5);
  const gather=clamp(p+lag),inward=side==='left'?u:1-u;
  const edge=1.035+.10*(1-p),span=1.045*gather;
  const ripple=Math.sin(u*Math.PI*14+time*3.2-v*.7)*.008*motion*Math.sin(Math.PI*inward);
  const x=(side==='left'?-edge+inward*span:edge-inward*span)+ripple;
  const y=(v-.5)*2.09+Math.sin(u*8+time*2.4)*.012*motion*(1-v)*inward;
  const z=Math.sin(u*Math.PI*14-v*.25)*.045*motion;
  const shade=1-motion*(.045+.04*Math.cos(u*Math.PI*14-v*.25));
  return {x,y,z,shade};
}

export function createCurtainCloth(canvas,{onReady=()=>{}}={}){
  let disposed=false,loaded=false;
  const renderer=new T.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio||1,1.5));renderer.outputColorSpace=T.SRGBColorSpace;renderer.setClearColor(0,0);
  const scene=new T.Scene(),camera=new T.OrthographicCamera(-1,1,1,-1,.1,10);camera.position.z=4;
  const texture=new T.TextureLoader().load(CURTAIN_ART,()=>{if(disposed)return;loaded=true;onReady(true);},undefined,()=>{if(!disposed)onReady(false);});
  texture.colorSpace=T.SRGBColorSpace;texture.minFilter=T.LinearFilter;texture.magFilter=T.LinearFilter;texture.generateMipmaps=false;
  const material=new T.MeshBasicMaterial({map:texture,vertexColors:true,side:T.DoubleSide,toneMapped:false,depthTest:false,depthWrite:false});
  const panels=['left','right'].map((side,index)=>{
    const geometry=new T.PlaneGeometry(1,2,48,16),uv=geometry.attributes.uv,base=new Float32Array(uv.array);
    geometry.setAttribute('color',new T.Float32BufferAttribute(new Float32Array(geometry.attributes.position.count*3).fill(1),3));
    for(let i=0;i<uv.count;i++)uv.setX(i,(index+base[i*2])*.5);
    const mesh=new T.Mesh(geometry,material);mesh.frustumCulled=false;mesh.renderOrder=index;scene.add(mesh);
    return {side,geometry,base};
  });
  let width=0,height=0,last='';
  return {
    get ready(){return loaded;},
    resize(w,h){if(w===width&&h===height)return;width=w;height=h;renderer.setSize(Math.max(1,w),Math.max(1,h),false);last='';},
    draw(closed,phase,now){
      if(!loaded||disposed||width<=0||height<=0)return;
      // Static closed frames need no continuous GPU work while assets prepare.
      const key=closed===1?'covered':`${closed}/${phase}/${now}`;if(last===key)return;last=key;
      for(const {side,geometry,base} of panels){
        const position=geometry.attributes.position,color=geometry.attributes.color;
        for(let i=0;i<position.count;i++){
          const p=curtainVertex(side,base[i*2],base[i*2+1],closed,phase,now/1000);
          position.setXYZ(i,p.x,p.y,p.z);color.setXYZ(i,p.shade,p.shade,p.shade);
        }
        position.needsUpdate=true;color.needsUpdate=true;
      }
      renderer.render(scene,camera);
    },
    dispose(){disposed=true;for(const p of panels)p.geometry.dispose();texture.dispose();material.dispose();renderer.dispose();}
  };
}
