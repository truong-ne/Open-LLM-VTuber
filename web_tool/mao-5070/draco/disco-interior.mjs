import * as T from '../3d/vendor/three.module.js';
import {stoneMaterial,softBoxGeometry} from './room-materials.mjs';

// Real geometry, with instanced batches for repeated details. No external
// images, fonts, environment maps or postprocessing are needed.
export function buildDiscoInterior(group){
  const materials={
    shell:new T.MeshStandardMaterial({color:0x29282a,roughness:.6}),
    metal:new T.MeshStandardMaterial({color:0xae9a77,metalness:.65,roughness:.3}),
    black:new T.MeshStandardMaterial({color:0x17191c,roughness:.62}),
    velvet:new T.MeshStandardMaterial({color:0x143e38,roughness:.94}),
    cushion:new T.MeshStandardMaterial({color:0x29594c,roughness:.88}),
    gold:new T.MeshStandardMaterial({color:0xc7ad7e,metalness:.55,roughness:.33}),
    leaf:new T.MeshStandardMaterial({color:0x326b63,roughness:.8,side:T.DoubleSide}),
    white:new T.MeshStandardMaterial({color:0xe6dccb,metalness:.05,roughness:.4}),
    neon:new T.MeshBasicMaterial({color:0xffffff,toneMapped:false}),
    stone:stoneMaterial(0x343536),
    ivoryStone:stoneMaterial(0xc3b7a2),
    walnut:new T.MeshStandardMaterial({color:0x3e2b24,roughness:.48}),
  };
  const geometry={box:new T.BoxGeometry(1,1,1),cylinder:new T.CylinderGeometry(1,1,1,24),
    sphere:new T.SphereGeometry(1,16,10),ring:new T.TorusGeometry(1,.065,6,32),softBox:softBoxGeometry(),inlay:new T.TorusGeometry(1,.003,4,96)};
  const batches=new Map(),quaternion=new T.Quaternion(),position=new T.Vector3(),scale=new T.Vector3(),euler=new T.Euler();
  const add=(shape,material,xyz,size,rotation=[0,0,0],color=0xffffff)=>{
    const key=shape+'/'+material;let batch=batches.get(key);
    if(!batch){batch={shape,material,items:[]};batches.set(key,batch);}
    position.set(...xyz);scale.set(...size);quaternion.setFromEuler(euler.set(...rotation));
    batch.items.push({matrix:new T.Matrix4().compose(position,quaternion,scale),color});
  };
  const box=(material,xyz,size,color,rotation)=>add('box',material,xyz,size,rotation,color);
  const tube=(a,b,r,material='metal',color=0xffffff)=>{
    const start=new T.Vector3(...a),end=new T.Vector3(...b),delta=end.clone().sub(start);
    position.copy(start).add(end).multiplyScalar(.5);scale.set(r,delta.length(),r);quaternion.setFromUnitVectors(new T.Vector3(0,1,0),delta.normalize());
    const key='cylinder/'+material;let batch=batches.get(key);if(!batch){batch={shape:'cylinder',material,items:[]};batches.set(key,batch);}
    batch.items.push({matrix:new T.Matrix4().compose(position,quaternion,scale),color});
  };
  const opal=0xf6e9d0,champagne=0xdcbf88,amber=0xefc18a;
  const obstacles=[];
  const furniture=(name,minX,maxX,minZ,maxZ)=>obstacles.push({name,minX,maxX,minZ,maxZ});

  // Walnut pilasters, recessed champagne coves and layered wall mouldings.
  for(const y of [.10,2.98]){
    box('walnut',[0,y,-4.965],[8,.09,.065]);
    box('neon',[0,y+.05,-4.92],[7.85,.012,.014],champagne);
    for(const side of [-1,1]){
      box('walnut',[side*3.96,y,-2],[.08,.09,6]);
      box('gold',[side*3.91,y-.035,-2],[.012,.012,5.94]);
      box('neon',[side*3.91,y+.05,-2],[.012,.012,5.9],champagne);
    }
  }
  for(const x of [-3.55,-2.75,2.75,3.55]){
    box('walnut',[x,1.65,-4.95],[.57,2.02,.07]);
    for(let dx=-.24;dx<.25;dx+=.06)box('walnut',[x+dx,1.65,-4.89],[.025,1.94,.035]);
    for(const dx of [-.29,.29])box('gold',[x+dx,1.65,-4.91],[.009,2.04,.025]);
  }
  for(const side of [-1,1])for(const z of [-3.45,-1.85,-.25]){
    box('walnut',[side*3.95,1.73,z],[.06,1.75,.98]);
    for(const dz of [-.46,.46])box('gold',[side*3.905,1.73,z+dz],[.018,1.64,.009]);
    for(const y of [.91,2.55])box('gold',[side*3.905,y,z],[.018,.009,.93]);
    box('gold',[side*3.87,1.9,z],[.055,.64,.09]);
    box('neon',[side*3.83,1.9,z],[.025,.48,.035],opal);
  }

  // Large mineral slabs and restrained brass inlay replace luminous checker tiles.
  box('black',[0,-.039,-1.65],[5.02,.065,3.55]);
  for(let row=0;row<4;row++)for(let col=0;col<6;col++)
    box('stone',[(col-2.5)*.82,-.003,(row-1.5)*.87-1.65],[.816,.002,.866]);
  for(const inset of [0,.07]){
    for(const x of [-2.49+inset,2.49-inset])box('gold',[x,-.0005,-1.65],[.008,.002,3.51-inset*2]);
    for(const z of [-3.405+inset,.105-inset])box('gold',[0,-.0005,z],[4.99-inset*2,.002,.008]);
  }
  for(const radius of [1.18,1.22])add('inlay','gold',[0,.001,-1.65],[radius,radius,radius],[-Math.PI/2,0,0]);
  // Rear DJ stage, turntables, mixer and a hinged laptop.
  box('stone',[0,.085,-4.5],[5.45,.17,1]);
  box('neon',[0,.13,-3.992],[5.4,.025,.012],champagne);
  box('walnut',[0,.52,-4.52],[2.8,.7,.55]);
  box('ivoryStone',[0,.885,-4.52],[2.94,.06,.65]);
  box('stone',[0,.54,-4.23],[2.5,.48,.025]);
  for(let x=-1.2;x<1.21;x+=.12)box('gold',[x,.54,-4.205],[.009,.41,.012]);
  for(const y of [.31,.77])box('neon',[0,y,-4.21],[2.52,.014,.014],opal);
  for(const x of [-1.25,1.25])box('neon',[x,.54,-4.21],[.014,.47,.014],champagne);
  for(const x of [-.91,.91]){
    box('shell',[x,.94,-4.51],[.58,.05,.48]);
    add('cylinder','black',[x,.973,-4.51],[.2,.014,.2]);
    add('ring','metal',[x,.982,-4.51],[.15,.15,.15],[-Math.PI/2,0,0]);
    add('cylinder','neon',[x,.985,-4.51],[.045,.008,.045],[0,0,0],champagne);
    tube([x+.23,.99,-4.68],[x+.13,.99,-4.44],.008,'gold');
  }
  box('shell',[0,.935,-4.48],[.55,.04,.48]);
  for(let i=0;i<5;i++)for(let j=0;j<3;j++){
    add('cylinder','metal',[(i-2)*.095,.968,-4.59+j*.09],[.017,.028,.017]);
    box('neon',[(i-2)*.095,.967,-4.29],[.045,.005,.025],i%2?opal:champagne);
  }
  box('metal',[.12,.974,-4.66],[.48,.025,.29]);
  box('black',[.12,1.13,-4.79],[.48,.32,.025],undefined,[-.14,0,0]);
  box('neon',[.12,1.13,-4.77],[.40,.24,.006],0x526a91,[-.14,0,0]);
  furniture('DJ stage',-2.725,2.725,-5,-4);

  // Recessed speaker cones, tweeters, rings and protective cabinet rails.
  for(const side of [-1,1]){
    const x=side*3.12;
    box('black',[x,.91,-4.55],[.58,1.7,.53]);
    box('shell',[x,.91,-4.272],[.50,1.59,.02]);
    for(const [y,r] of [[.55,.205],[1.07,.205],[1.56,.10]]){
      add('cylinder','black',[x,y,-4.25],[r,.024,r],[Math.PI/2,0,0]);
      add('ring','metal',[x,y,-4.228],[r,r,r]);
      add('sphere','shell',[x,y,-4.223],[r*.36,r*.36,.035]);
    }
    box('neon',[x,.19,-4.226],[.24,.015,.01],opal);
    for(const dx of [-.255,.255])box('metal',[x+dx,.91,-4.21],[.012,1.6,.025]);
    furniture('Speaker',x-.29,x+.29,-4.815,-4.285);
  }

  // Velvet lounges, separate cushions, brass legs, side tables and plants.
  for(const side of [-1,1]){
    const x=side*3.68;
    box('walnut',[x,.29,-1.65],[.55,.32,2.36]);
    add('softBox','velvet',[side*3.935,.64,-1.65],[.12,.70,2.4]);
    for(const z of [-2.4,-1.65,-.9]){
      add('softBox','cushion',[x,.47,z],[.54,.17,.69]);
      add('softBox','velvet',[side*3.865,.72,z],[.15,.48,.68]);
      add('sphere','gold',[side*3.79,.72,z],[.015,.015,.015]);
    }
    for(const z of [-2.65,-.65])for(const dx of [-.18,.18])add('cylinder','gold',[x+dx,.11,z],[.025,.22,.025]);
    for(const z of [-2.88,-.42])add('softBox','velvet',[x,.53,z],[.55,.28,.12]);
    const z=.22;
    add('cylinder','gold',[x,.29,z],[.026,.58,.026]);
    add('cylinder','ivoryStone',[x,.59,z],[.23,.035,.23]);
    add('cylinder','gold',[x,.03,z],[.16,.035,.16]);
    for(const dx of [-.08,.08]){
      add('cylinder','white',[x+dx,.665,z],[.035,.11,.035]);
      add('cylinder','neon',[x+dx,.723,z],[.03,.002,.03],[0,0,0],side<0?champagne:opal);
    }
    add('cylinder','gold',[x,.78,z],[.018,.35,.018]);
    add('cylinder','gold',[x,.625,z],[.065,.02,.065]);
    add('sphere','white',[x,.99,z],[.115,.14,.115]);
    furniture('Lounge',side<0?-4:3.4,side<0?-3.4:4,-2.94,-.36);
    furniture('Table',x-.23,x+.23,-.01,.45);
    add('cylinder','gold',[x,.19,-3.63],[.19,.38,.19]);
    for(let i=0;i<7;i++){
      const a=i*Math.PI*2/7,tip=[x+Math.cos(a)*.25,.9+(i%3)*.13,-3.63+Math.sin(a)*.25];
      tube([x,.3,-3.63],tip,.008,'leaf');
      add('sphere','leaf',tip,[.065,.26,.025],[Math.sin(a)*.45,0,-Math.cos(a)*.45]);
    }
    furniture('Planter',x-.32,x+.32,-3.95,-3.31);
  }

  // Lighting integrates into a shallow rear cornice. The middle of the
  // room stays completely open: no central rail, hanging ball or cable.
  box('walnut',[0,3.08,-4.82],[7.9,.18,.26]);
  box('gold',[0,2.985,-4.68],[7.85,.012,.012]);
  box('neon',[0,3.16,-4.66],[7.82,.012,.014],champagne);
  box('stone',[0,2.18,-4.94],[4.25,1.72,.06]);
  for(const side of [-1,1])tube([side*2.04,1.47,-4.88],[side*2.04,2.44,-4.88],.011,'gold');
  for(let i=0;i<48;i++){
    const a=i/48*Math.PI,b=(i+1)/48*Math.PI;
    tube([2.04*Math.cos(a),2.44+.48*Math.sin(a),-4.88],[2.04*Math.cos(b),2.44+.48*Math.sin(b),-4.88],.011,'gold');
  }
  // Geometric neon lettering stays crisp without a font/bitmap dependency.
  box('stone',[0,2.29,-4.91],[3.8,.91,.055]);
  const glyph={M:[[[0,0],[0,1],[.5,.48],[1,1],[1,0]]],A:[[[0,0],[.5,1],[1,0]],[[.22,.4],[.78,.4]]],
    O:[[[.2,0],[0,.2],[0,.8],[.2,1],[.8,1],[1,.8],[1,.2],[.8,0],[.2,0]]],
    V:[[[0,1],[.5,0],[1,1]]],T:[[[0,1],[1,1]],[[.5,1],[.5,0]]],
    U:[[[0,1],[0,.2],[.2,0],[.8,0],[1,.2],[1,1]]],
    B:[[[0,0],[0,1],[.7,1],[1,.8],[.7,.5],[0,.5]],[[.7,.5],[1,.25],[.7,0],[0,0]]],
    E:[[[1,1],[0,1],[0,0],[1,0]],[[0,.5],[.8,.5]]],
    R:[[[0,0],[0,1],[.7,1],[1,.8],[.7,.5],[0,.5]],[[.5,.5],[1,0]]]};
  let cursor=-1.63;
  for(const char of 'MAO VTUBER'){
    if(char===' '){cursor+=.15;continue;}
    for(const stroke of glyph[char])for(let i=1;i<stroke.length;i++)
      tube([cursor+stroke[i-1][0]*.28,2.12+stroke[i-1][1]*.32,-4.86],[cursor+stroke[i][0]*.28,2.12+stroke[i][1]*.32,-4.86],.012,'neon',opal);
    cursor+=.36;
  }
  for(const y of [1.94,1.97])box('gold',[0,y,-4.86],[2.6,.005,.008]);
  for(const x of [-1.38,1.38])add('box','gold',[x,1.955,-4.86],[.04,.04,.008],[0,0,Math.PI/4]);

  for(const batch of batches.values()){
    const mesh=new T.InstancedMesh(geometry[batch.shape],materials[batch.material],batch.items.length);
    mesh.name='disco-'+batch.shape+'-'+batch.material;
    batch.items.forEach((item,index)=>{mesh.setMatrixAt(index,item.matrix);mesh.setColorAt(index,new T.Color(item.color));});
    mesh.computeBoundingSphere();group.add(mesh);
  }
  const lights=[],beamGeometry=new T.ConeGeometry(.6,1,24,1,true),spotGeometry=new T.CircleGeometry(1,32);
  const down=new T.Vector3(0,-1,0),aim=new T.Vector3(),destination=new T.Vector3();
  for(let i=0;i<4;i++){
    const x=[-2.65,-.95,.95,2.65][i],color=[champagne,opal,opal,amber][i];
    const pivot=new T.Group();pivot.name='disco-moving-head';pivot.position.set(x,2.91,-4.8);group.add(pivot);
    const housing=new T.Mesh(new T.CylinderGeometry(.085,.11,.17,16),materials.black);housing.position.y=-.07;pivot.add(housing);
    const lens=new T.Mesh(new T.CircleGeometry(.078,20),materials.neon.clone());lens.material.color.setHex(color);lens.rotation.x=Math.PI/2;lens.position.y=-.159;pivot.add(lens);
    const beam=new T.Mesh(beamGeometry,new T.MeshBasicMaterial({color,transparent:true,opacity:.012,depthWrite:false,side:T.DoubleSide,blending:T.AdditiveBlending,toneMapped:false}));beam.name='disco-light-beam';beam.position.y=-.5;beam.renderOrder=2;
    const beamRoot=new T.Group();beamRoot.add(beam);pivot.add(beamRoot);
    const pool=new T.Mesh(spotGeometry,new T.MeshBasicMaterial({color,transparent:true,opacity:.065,depthWrite:false,blending:T.AdditiveBlending,toneMapped:false}));pool.rotation.x=-Math.PI/2;pool.position.y=.001;group.add(pool);
    // Two actual unshadowed lights; the other beams are atmospheric geometry.
    let light;
    if(i===0||i===3){light=new T.SpotLight(color,6,7,.38,.95,2);light.position.copy(pivot.position);group.add(light,light.target);}
    lights.push({pivot,beamRoot,pool,light,phase:i*1.7});
  }
  let time=0;
  const update=dt=>{
    if(!group.visible)return;
    time+=Math.max(0,Math.min(dt,.1));
    for(const rig of lights){
      destination.set(Math.sin(time*.10+rig.phase)*2,.015,-1.65+Math.cos(time*.08+rig.phase)*1.10);
      aim.copy(destination).sub(rig.pivot.position);const length=aim.length();rig.pivot.quaternion.setFromUnitVectors(down,aim.normalize());
      rig.beamRoot.scale.y=length;rig.pool.position.x=destination.x;rig.pool.position.z=destination.z;rig.pool.scale.set(.65,.9,1);
      if(rig.light)rig.light.target.position.copy(destination);
    }
  };
  const visible=group.visible;group.visible=true;update(0);group.visible=visible;
  return {update,obstacles,theme:'luxury-lounge'};
}
