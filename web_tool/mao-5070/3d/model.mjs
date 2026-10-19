import * as T from './vendor/three.module.js';

const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v);return v*v*(3-2*v);};
const vec=(x,y,z)=>new T.Vector3(x,y,z);

export function buildMao(){
  const group=new T.Group();group.name='Mao5070_3D_Prototype';
  const bones=[],joints={},meshes=[],hair=[];
  const mat=(color,roughness=.7,metalness=0)=>new T.MeshStandardMaterial({color,roughness,metalness});
  const materials={skin:mat('#ffe0ce'),ivory:mat('#fffbf0'),navy:mat('#242036'),purple:mat('#7643c1'),gold:mat('#d9b66b',.3,.65),hair:mat('#e6dfda',.55),hairLight:mat('#fff7ec'),tights:mat('#423b45'),boots:mat('#28232f',.32),eye:mat('#fffafc'),iris:mat('#9252dc',.35),ink:mat('#302333'),pink:mat('#c97884')};
  function bone(name,parent,x=0,y=0,z=0){const b=new T.Bone();b.name=name;b.position.set(x,y,z);(parent||group).add(b);bones.push(b);joints[name]=b;return b;}
  const root=bone('root',null),hips=bone('hips',root,0,1.04,0),spine=bone('spine',hips,0,.19,0),chest=bone('chest',spine,0,.20,0),neck=bone('neck',chest,0,.14,0),head=bone('head',neck,0,.13,0);
  for(const [side,sign] of [['L',-1],['R',1]]){
    const upper=bone(`upper${side}`,chest,sign*.225,.015,0);
    const elbow=bone(`elbow${side}`,upper,0,-.255,0);
    const wrist=bone(`wrist${side}`,elbow,0,-.245,0);
    for(let i=0;i<4;i++){
      let parent=bone(`finger${side}${i}a`,wrist,sign*(i-1.5)*.016,-.080,0);
      parent=bone(`finger${side}${i}b`,parent,0,-[.029,.037,.039,.032][i],0);
      bone(`finger${side}${i}c`,parent,0,-.025,0);
    }
    const thumb=bone(`thumb${side}a`,wrist,-sign*.027,-.025,0);
    const thumb2=bone(`thumb${side}b`,thumb,-sign*.023,-.027,0);
    bone(`thumb${side}c`,thumb2,-sign*.009,-.021,0);
    const thigh=bone(`thigh${side}`,hips,sign*.095,-.025,0);
    const knee=bone(`knee${side}`,thigh,0,-.425,0);
    bone(`ankle${side}`,knee,0,-.435,0);
  }
  group.updateMatrixWorld(true);
  const skeleton=new T.Skeleton(bones);skeleton.calculateInverses();
  const bi=b=>bones.indexOf(typeof b==='string'?joints[b]:b);
  function mesh(geometry,material,parent=group,name='detail'){
    const m=new T.Mesh(geometry,material);m.name=name;m.castShadow=true;m.receiveShadow=true;parent.add(m);meshes.push(m);return m;
  }
  function ellipsoid(parent,center,radius,material,name='detail'){
    const m=mesh(new T.SphereGeometry(1,24,16),material,parent,name);m.position.set(...center);m.scale.set(...radius);return m;
  }
  function curve(parent,points,radius,material,name='trim'){
    const c=new T.CatmullRomCurve3(points.map(p=>vec(...p)));
    return mesh(new T.TubeGeometry(c,32,radius,7,false),material,parent,name);
  }
  function skinned(geometry,material,weights,name){
    const indices=[],values=[],v=new T.Vector3();
    for(let i=0;i<geometry.attributes.position.count;i++){
      v.fromBufferAttribute(geometry.attributes.position,i);const w=weights(v);
      indices.push(...w.map(x=>bi(x[0])),...Array(4-w.length).fill(0));
      values.push(...w.map(x=>x[1]),...Array(4-w.length).fill(0));
    }
    geometry.setAttribute('skinIndex',new T.Uint16BufferAttribute(indices,4));
    geometry.setAttribute('skinWeight',new T.Float32BufferAttribute(values,4));
    const m=new T.SkinnedMesh(geometry,material);m.name=name;m.castShadow=true;m.receiveShadow=true;group.add(m);m.bind(skeleton);meshes.push(m);return m;
  }
  function loft(rings,segments=48,pleats=0){
    const p=[],uv=[],ind=[];
    rings.forEach(([y,rx,rz,cx=0,cz=0],j)=>{for(let i=0;i<=segments;i++){const a=i/segments*Math.PI*2,fold=1+pleats*Math.cos(a*16);p.push(cx+Math.cos(a)*rx*fold,y,cz+Math.sin(a)*rz*fold);uv.push(i/segments,j/(rings.length-1));}});
    for(let j=0;j<rings.length-1;j++)for(let i=0;i<segments;i++){const a=j*(segments+1)+i,b=a+segments+1;if(rings.at(-1)[0]>rings[0][0])ind.push(a,b,a+1,a+1,b,b+1);else ind.push(a,a+1,b,a+1,b+1,b);}
    const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(p,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(ind);g.computeVertexNormals();return g;
  }
  function interpolateRings(keys,steps=30){const rows=[];for(let i=0;i<=steps;i++){const t=i/steps*(keys.length-1),k=Math.min(keys.length-2,Math.floor(t)),f=t-k;rows.push(keys[k].map((v,j)=>{const a=keys[Math.max(0,k-1)][j],b=v,c=keys[k+1][j],d=keys[Math.min(keys.length-1,k+2)][j];return .5*((2*b)+(-a+c)*f+(2*a-5*b+4*c-d)*f*f+(-a+3*b-3*c+d)*f*f*f);}));}return rows;}
  const torsoWeights=v=>{if(v.y<1.16)return [['hips',1]];if(v.y<1.32){const w=smooth((v.y-1.16)/.16);return [['hips',1-w],['spine',w]];}const w=smooth((v.y-1.32)/.13);return [['spine',1-w],['chest',w]];};
  skinned(loft(interpolateRings([[1.06,.185,.115],[1.18,.142,.10],[1.31,.17,.12],[1.40,.218,.145],[1.48,.215,.115]])),materials.ivory,torsoWeights,'ivory_bodice');
  // The shoulders and neck remain visible above the adult stage costume.
  ellipsoid(chest,[0,.045,0],[.228,.08,.105],materials.skin,'shoulders');
  ellipsoid(neck,[0,0,0],[.054,.105,.053],materials.skin,'neck');
  skinned(loft([[1.15,.151,.108],[1.115,.159,.113],[1.09,.174,.118]]),materials.navy,torsoWeights,'belt');
  const skirt=skinned(loft(interpolateRings([[1.095,.18,.12],[1.02,.22,.15],[.88,.29,.195],[.79,.323,.222]],24),64,.035),materials.navy,()=>[['hips',1]],'pleated_skirt');
  skinned(loft([[.82,.319,.22],[.775,.33,.23]],64,.045),materials.purple,()=>[['hips',1]],'purple_hem');
  for(let i=0;i<8;i++){
    const a=i/8*Math.PI*2;
    const strip=curve(hips,[[Math.cos(a)*.18,.05,Math.sin(a)*.12],[Math.cos(a)*.24,-.09,Math.sin(a)*.16],[Math.cos(a)*.322,-.25,Math.sin(a)*.222]],.0025,materials.gold,'skirt_piping');
    strip.renderOrder=1;
  }
  // Jacket straps and front split tails: real surfaces that turn with the torso.
  for(const sign of [-1,1]){
    curve(chest,[[sign*.11,.10,-.025],[sign*.15,.09,.09],[sign*.18,.015,.13],[sign*.17,-.13,.12]],.020,materials.navy,'jacket_strap');
    curve(chest,[[sign*.11,.105,-.027],[sign*.166,.073,.109],[sign*.196,-.03,.123]],.003,materials.gold);
    const panel=new T.Shape();panel.moveTo(sign*.17,-.12);panel.lineTo(sign*.23,-.30);panel.lineTo(sign*.12,-.35);panel.lineTo(sign*.135,-.15);
    const g=new T.ShapeGeometry(panel);const m=mesh(g,materials.navy,chest,'jacket_tail');m.position.z=.133;m.material.side=T.DoubleSide;
    ellipsoid(chest,[sign*.19,-.035,.137],[.011,.011,.006],materials.gold,'flower_clasp');
  }
  // Limb surfaces share the same skeleton as their clothing.
  for(const [side,sign] of [['L',-1],['R',1]]){
    const x=sign*.225,sy=1.445,ey=sy-.255,wy=ey-.245;
    ellipsoid(joints[`upper${side}`],[0,0,0],[.055,.055,.055],materials.skin,'shoulder_round');
    const armWeights=v=>{const a=smooth((ey+.045-v.y)/.09),b=smooth((wy+.025-v.y)/.05);if(b>0)return [[`elbow${side}`,1-b],[`wrist${side}`,b]];return [[`upper${side}`,1-a],[`elbow${side}`,a]];};
    skinned(loft(interpolateRings([[sy,.055,.055,x],[sy-.11,.046,.047,x],[ey,.038,.038,x],[wy,.026,.026,x]],32),24),materials.skin,armWeights,`arm_skin_${side}`);
    skinned(loft(interpolateRings([[sy-.08,.058,.058,x],[sy-.16,.076,.067,x],[ey,.082,.07,x],[wy+.07,.074,.062,x],[wy+.035,.048,.045,x]],36),32,.035),materials.navy,armWeights,`sleeve_${side}`);
    skinned(loft([[wy+.065,.060,.051,x],[wy+.015,.048,.045,x]],32),materials.ivory,armWeights,`cuff_${side}`);
    const wrist=joints[`wrist${side}`];
    ellipsoid(wrist,[0,-.042,0],[.035,.052,.019],materials.skin,`palm_${side}`);
    for(let i=0;i<4;i++)for(const [j,length] of [['a',[.029,.037,.039,.032][i]],['b',.025],['c',.020]]){
      const b=joints[`finger${side}${i}${j}`];ellipsoid(b,[0,-length*.5,0],[.0072,length*.64,.0078],materials.skin,`finger_mesh_${side}${i}${j}`);
      if(j==='c')ellipsoid(b,[0,-length*.64,-.006],[.005,.009,.0018],materials.purple,'nail');
    }
    for(const [j,dx,len] of [['a',-.023,.027],['b',-.009,.021],['c',-.003,.016]])ellipsoid(joints[`thumb${side}${j}`],[sign*dx*.5,-len*.5,0],[.010,len*.75,.009],materials.skin,`thumb_mesh_${side}${j}`);
    const hipY=1.015,ky=.59,ay=.155,lx=sign*.095;
    const legWeights=v=>{const a=smooth((ky+.05-v.y)/.1),b=smooth((ay+.035-v.y)/.07);if(b>0)return [[`knee${side}`,1-b],[`ankle${side}`,b]];return [[`thigh${side}`,1-a],[`knee${side}`,a]];};
    skinned(loft(interpolateRings([[hipY,.088,.09,lx],[.85,.075,.08,lx],[ky,.046,.049,lx],[.44,.059,.061,lx],[ay,.031,.035,lx]],42),32),materials.tights,legWeights,`leg_${side}`);
    const ankle=joints[`ankle${side}`];
    ellipsoid(ankle,[0,-.065,.045],[.046,.067,.105],materials.boots,`boot_${side}`);
    const shaft=mesh(new T.CylinderGeometry(.045,.041,.18,24),materials.boots,ankle,'boot_shaft');shaft.position.y=.035;
    const sole=mesh(new T.BoxGeometry(.083,.024,.155),materials.navy,ankle,'boot_sole');sole.position.set(0,-.127,.045);
    const heel=mesh(new T.BoxGeometry(.042,.065,.043),materials.boots,ankle,'heel');heel.position.set(0,-.095,-.035);
    const buckle=mesh(new T.TorusGeometry(.022,.003,6,16),materials.gold,ankle,'boot_buckle');buckle.position.set(sign*.035,.06,.024);buckle.rotation.y=sign*.6;
  }
  // Sculpted head volume, not a camera-facing image plane.
  const headGeo=new T.SphereGeometry(1,48,40),hp=headGeo.attributes.position;
  for(let i=0;i<hp.count;i++){const y=hp.getY(i),jaw=y<-.1?T.MathUtils.lerp(.52,1,smooth((y+1)/.9)):1;hp.setXYZ(i,hp.getX(i)*.151*jaw,y*.185,hp.getZ(i)*.133*(y<-.2?.85:1));}
  headGeo.computeVertexNormals();const skull=mesh(headGeo,materials.skin,head,'sculpted_head');skull.receiveShadow=false;
  for(const sign of [-1,1])ellipsoid(head,[sign*.145,-.018,0],[.024,.042,.018],materials.skin,'ear');
  const eyes=[];
  for(const sign of [-1,1]){
    const eye=new T.Group();eye.position.set(sign*.059,.018,.126);eye.rotation.y=sign*.22;head.add(eye);eyes.push(eye);
    const shape=new T.Shape();shape.moveTo(-.043,0);shape.quadraticCurveTo(0,.041,.043,0);shape.quadraticCurveTo(0,-.027,-.043,0);
    mesh(new T.ShapeGeometry(shape,24),materials.eye,eye,'eye_white');
    ellipsoid(eye,[0,.002,.004],[.020,.027,.005],materials.iris,'iris');
    ellipsoid(eye,[0,.002,.009],[.0085,.019,.003],materials.ink,'pupil');
    ellipsoid(eye,[-.007,.013,.013],[.005,.007,.002],materials.eye,'eye_glint');
    curve(eye,[[-.043,0,.004],[-.020,.021,.005],[.014,.022,.005],[.044,0,.004]],.0034,materials.ink,'upper_lash');
    curve(eye,[[sign*.027,.015,.005],[sign*.052,.019,.005]],.0028,materials.ink,'lash_tip');
    curve(head,[[sign*.025,.068,.119],[sign*.058,.076,.115],[sign*.095,.067,.095]],.003,materials.ink,'eyebrow');
  }
  ellipsoid(head,[0,-.029,.128],[.010,.025,.019],materials.skin,'nose');
  const mouth=new T.Group();mouth.position.set(0,-.080,.111);head.add(mouth);
  ellipsoid(mouth,[0,0,0],[.025,.013,.004],materials.ink,'mouth_inside');
  ellipsoid(mouth,[0,-.004,.003],[.016,.006,.002],materials.pink,'tongue');
  const smile=curve(head,[[-.026,-.077,.111],[0,-.087,.116],[.026,-.077,.111]],.002,materials.pink,'smile');
  let face;
  if(typeof document!=='undefined'){
    // Project the approved illustration onto a curved facial surface. The skull,
    // hair and whole body retain real depth, silhouette and back-side geometry.
    eyes.forEach(e=>e.visible=false);mouth.visible=false;smile.visible=false;
    head.children.filter(m=>['eyebrow','nose'].includes(m.name)).forEach(m=>m.visible=false);
    const positions=[],uv=[],indices=[],blinkPositions=[],mouthPositions=[],cols=64,rows=64;
    const projectFace=(sx,sy,blink,open)=>{
      let x=sx,y=sy;
      for(const [cx,cy] of [[220,274],[338,259]]){const wx=1-smooth((Math.abs(x-cx)-27)/14),dy=y-(cy-(x-cx)*.13),wy=1-smooth((Math.abs(dy)-12)/19);y-=dy*blink*.97*wx*wy;}
      const wx=1-smooth((Math.abs(x-288)-31)/18),wy=1-smooth((Math.abs(y-341)-13)/25);y=T.MathUtils.lerp(y,341+(y-341)*(.09+.91*open),wx*wy);
      const px=(x-288)*.00102,py=(294-y)*.00127,jaw=py<-.0185?T.MathUtils.lerp(.52,1,smooth((py/.185+1)/.9)):1;
      const pz=.133*(py<-.037?.85:1)*Math.sqrt(Math.max(.015,1-(px/(.151*jaw))**2-(py/.185)**2))+.003;
      return [px,py,pz];
    };
    for(let r=0;r<=rows;r++)for(let c=0;c<=cols;c++){
      const theta=c/cols*Math.PI*2,radius=r/rows,px=Math.cos(theta)*.128*radius,py=-.020+Math.sin(theta)*.138*radius;
      const sx=288+px/.00102,sy=294-py/.00127;
      positions.push(...projectFace(sx,sy,0,0));blinkPositions.push(...projectFace(sx,sy,1,0));mouthPositions.push(...projectFace(sx,sy,0,1));uv.push(sx/1536,1-sy/1024);
    }
    for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const a=r*(cols+1)+c,b=a+cols+1;indices.push(a,b,a+1,a+1,b,b+1);}
    const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(positions,3));g.setAttribute('uv',new T.Float32BufferAttribute(uv,2));g.setIndex(indices);g.morphAttributes.position=[new T.Float32BufferAttribute(blinkPositions,3),new T.Float32BufferAttribute(mouthPositions,3)];g.computeVertexNormals();
    const texture=new T.TextureLoader().load('../parts-atlas.png');texture.colorSpace=T.SRGBColorSpace;
    face=mesh(g,new T.MeshBasicMaterial({map:texture,side:T.DoubleSide}),head,'face_expression');face.castShadow=false;face.receiveShadow=false;face.updateMorphTargets();
  }
  // Scalp and individual curved locks give the bob a silhouette from every view.
  const capPos=[],capInd=[],capRows=18,capCols=64;
  for(let r=0;r<=capRows;r++)for(let c=0;c<=capCols;c++){
    const phi=c/capCols*Math.PI*2,front=Math.max(0,Math.sin(phi)),theta=r/capRows*(1.92-.84*front**3);
    capPos.push(Math.cos(phi)*Math.sin(theta)*.163,.02+Math.cos(theta)*.190,Math.sin(phi)*Math.sin(theta)*.148);
  }
  for(let r=0;r<capRows;r++)for(let c=0;c<capCols;c++){const a=r*(capCols+1)+c,b=a+capCols+1;capInd.push(a,a+1,b,a+1,b+1,b);}
  const cg=new T.BufferGeometry();cg.setAttribute('position',new T.Float32BufferAttribute(capPos,3));cg.setIndex(capInd);cg.computeVertexNormals();mesh(cg,materials.hair,head,'hair_cap');
  function lock(points,width,depth,index){
    const pivot=new T.Group();pivot.name=`hair_lock_${index}`;head.add(pivot);hair.push(pivot);
    const path=new T.CatmullRomCurve3(points.map(p=>vec(...p))),pos=[],ind=[];
    for(let r=0;r<=20;r++){const t=r/20,c=path.getPoint(t),tangent=path.getTangent(t),side=vec(0,0,1).cross(tangent).normalize(),normal=tangent.clone().cross(side).normalize(),w=width*Math.sin(Math.PI*(.12+t*.88))**.55;
      for(let j=0;j<=8;j++){const a=j/8*Math.PI*2,q=c.clone().addScaledVector(side,Math.cos(a)*w).addScaledVector(normal,Math.sin(a)*depth*Math.sin(Math.PI*(.1+t*.9)));pos.push(...q.toArray());}}
    for(let r=0;r<20;r++)for(let j=0;j<8;j++){const a=r*9+j,b=a+9;ind.push(a,a+1,b,a+1,b+1,b);}
    const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.setIndex(ind);g.computeVertexNormals();mesh(g,materials.hair,pivot,'hair_strand');
    curve(pivot,points.slice(0,3).map(p=>[p[0],p[1],p[2]+.003]),.0017,materials.hairLight,'hair_highlight');
  }
  let lockId=0;
  for(let i=0;i<16;i++){const a=i/16*Math.PI*2;if(Math.sin(a)>.7)continue;const x=Math.cos(a),z=Math.sin(a);lock([[x*.08,.17,z*.08],[x*.16,.08,z*.14],[x*.18,-.10,z*.15],[x*.16,-.19-(i%3)*.009,z*.12]],.032,.011,lockId++);}
  for(let i=0;i<7;i++){const x=(i-3)*.035;lock([[x*.45,.18,.07],[x*.8,.13,.134],[x,.07,.143],[x+.018,.022+Math.abs(i-3)*.014,.131]],.028,.007,lockId++);}
  const accessory=new T.Group();accessory.position.set(.151,.078,.043);head.add(accessory);
  for(let i=0;i<5;i++){const a=i/5*Math.PI*2;const petal=ellipsoid(accessory,[Math.cos(a)*.019,Math.sin(a)*.019,.009],[.013,.020,.006],materials.ivory,'flower_petal');petal.rotation.z=a-Math.PI/2;}
  ellipsoid(accessory,[0,0,.018],[.009,.009,.008],materials.gold,'flower_center');
  for(const sign of [-1,1]){const loop=ellipsoid(accessory,[sign*.027,-.014,-.008],[.028,.016,.009],materials.purple,'ribbon_loop');loop.rotation.z=sign*.5;curve(accessory,[[sign*.013,-.018,0],[sign*.022,-.055,.003],[sign*.031,-.092,.008]],.009,materials.purple,'ribbon_tail');}
  for(const sign of [-1,1]){curve(head,[[sign*.145,-.05,.015],[sign*.149,-.095,.020]],.0018,materials.gold,'earring');const jewel=mesh(new T.OctahedronGeometry(.012),materials.gold,head,'earring_jewel');jewel.position.set(sign*.149,-.108,.02);}
  // Number is a real texture on a curved strip, attached to the chest.
  if(typeof document!=='undefined'){
    const canvas=document.createElement('canvas');canvas.width=512;canvas.height=160;const c=canvas.getContext('2d');c.clearRect(0,0,512,160);c.fillStyle='#272337';c.font='900 132px Arial';c.textAlign='center';c.textBaseline='middle';c.fillText('5070',256,84);
    const texture=new T.CanvasTexture(canvas);texture.colorSpace=T.SRGBColorSpace;
    const g=new T.PlaneGeometry(.31,.095,24,1),p=g.attributes.position;
    for(let i=0;i<p.count;i++){const x=p.getX(i);p.setZ(i,.151*Math.sqrt(Math.max(0,1-(x/.24)**2)));}g.computeVertexNormals();
    const label=mesh(g,new T.MeshStandardMaterial({map:texture,transparent:true,depthWrite:false,roughness:.8}),chest,'5070_label');label.position.y=-.035;
  }
  group.updateMatrixWorld(true);
  head.traverse(m=>{if(m.isMesh){m.receiveShadow=false;m.castShadow=false;}});
  return {group,joints,skeleton,meshes,eyes,mouth,smile,hair,face,materials,skirt,root};
}
