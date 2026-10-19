import * as T from '../3d/vendor/three.module.js';

// A separate emerald concert set, preserving the familiar full-body camera.
export function buildConcertStage(group){
  const mesh=(name,geometry,material,x,y,z)=>{const m=new T.Mesh(geometry,material);m.name=name;m.position.set(x,y,z);group.add(m);return m;};
  const velvet=new T.MeshStandardMaterial({color:0x12382e,roughness:.9}),silver=new T.MeshStandardMaterial({color:0xbac6ac,metalness:.65,roughness:.3});
  mesh('concert-backdrop',new T.BoxGeometry(7.9,4,.12),velvet,0,1.8,-4.8);
  for(let i=-14;i<=14;i++)mesh('concert-velvet-fold',new T.CylinderGeometry(.13,.13,3.9,8),new T.MeshStandardMaterial({color:i%2?0x174536:0x0b2b24,roughness:.95}),i*.28,1.8,-4.62);
  for(const x of [-2.5,2.5])mesh('concert-silver-pillar',new T.BoxGeometry(.04,3,.06),silver,x,1.5,-4.3);
  const halo=mesh('concert-moon',new T.TorusGeometry(.82,.012,8,96),new T.MeshBasicMaterial({color:0xd8dfbf}),0,1.55,-4.15);
  const lights=[];
  for(const side of [-1,1])for(let i=0;i<9;i++){
    const material=new T.MeshBasicMaterial({color:i%3?0x95d8b7:0xe8dfb9,transparent:true,opacity:.5});
    const bar=mesh('concert-equalizer',new T.BoxGeometry(.045,.4,.025),material,side*(1.45+i*.11),.7,-4.2);lights.push(bar);
  }
  const floorGlow=mesh('concert-floor-ring',new T.RingGeometry(.72,.73,80),new T.MeshBasicMaterial({color:0xa8ddbd,transparent:true,opacity:.45,side:T.DoubleSide,depthWrite:false}),0,.002,-1.65);floorGlow.rotation.x=-Math.PI/2;
  let time=0;
  return {theme:'mao-concert',obstacles:[],
    update(dt){
      if(!group.visible)return;
      const singer=globalThis.window?.maoSinging,pose=singer?.pose;
      time=pose?.playing?pose.time:time+dt;
      const beat=time*(pose?.bpm||120)/60*Math.PI*2;
      for(let i=0;i<lights.length;i++){const amount=.25+.75*(.5+.5*Math.sin(beat+i*.7));lights[i].scale.y=amount*2;lights[i].material.opacity=.25+amount*.55;}
      halo.material.color.setHex(pose?.playing?0xdfe8c2:0xb6c9bc);
    }
  };
}
