import * as T from '../3d/vendor/three.module.js';
import {buildDiscoInterior} from './disco-interior.mjs?v=4';
import {buildTvStudio} from './tv-studio.mjs?v=7';
import {buildConcertStage} from './concert-stage.mjs';

export const ROOM=Object.freeze({width:8,depth:6,height:4.6,minX:-4,maxX:4,minZ:-5,maxZ:1,
  // Keep hair, sleeves and the skirt clear of furniture, not only the root.
  walk:Object.freeze({minX:-2.85,maxX:2.85,minZ:-3.5,maxZ:.3})});

export function createDesktopRoom({theme='lounge'}={}){
  const group=new T.Group();group.name='mao-desktop-room';
  const surface=(name,width,height,position,rotation,color)=>{
    const mesh=new T.Mesh(new T.PlaneGeometry(width,height),new T.MeshStandardMaterial({color,roughness:.65,metalness:.15}));
    mesh.name=name;mesh.position.set(...position);mesh.rotation.set(...rotation);group.add(mesh);return mesh;
  };
  // Extend the lounge floor towards the camera so an eye-level close shot
  // keeps real flooring beneath Mao instead of exposing the cutaway edge.
  const lounge=theme==='lounge'||theme==='concert';
  const floor=surface('room-floor',8,lounge?9:6,[0,-.004,lounge?-.5:-2],[-Math.PI/2,0,0],lounge?0x222326:0xb4a893);
  // Interior-facing sides disappear when viewed from outside: an orbitable
  // architectural cutaway without a roof or front wall hiding the character.
  const height=lounge?3.2:ROOM.height;
  surface('room-back-wall',8,height,[0,height/2,-5],[0,0,0],0x081522);
  surface('room-left-wall',6,height,[-4,height/2,-2],[0,Math.PI/2,0],0x0d2031);
  surface('room-right-wall',6,height,[4,height/2,-2],[0,-Math.PI/2,0],0x0d2031);
  const interior=theme==='lounge'?buildDiscoInterior(group):theme==='concert'?buildConcertStage(group):buildTvStudio(group);
  // The illustrated game room already contains its floor and walls. Retain
  // the invisible floor as a navigation surface, without covering the artwork.
  if(!lounge)for(const mesh of group.children)if(mesh.name==='room-floor'||mesh.name.endsWith('-wall'))mesh.visible=false;
  const shadow=new T.Mesh(new T.CircleGeometry(.23,32),new T.MeshBasicMaterial({color:0x050611,transparent:true,opacity:.38,depthWrite:false}));
  shadow.name='mao-foot-shadow';shadow.rotation.x=-Math.PI/2;shadow.scale.y=.65;shadow.position.y=.003;group.add(shadow);
  const marker=new T.Mesh(new T.RingGeometry(.11,.13,32),new T.MeshBasicMaterial({color:0xb9f4f2,transparent:true,opacity:.8,side:T.DoubleSide,depthWrite:false}));
  marker.name='room-destination';marker.rotation.x=-Math.PI/2;marker.position.y=.006;marker.visible=false;group.add(marker);
  group.visible=false;group.updateMatrixWorld(true);
  return {group,floor,shadow,marker,theme:interior.theme,obstacles:interior.obstacles,update:interior.update,get ready(){return interior.ready!==false;},
    setMode(mode){group.visible=mode==='window';},
    dispose(){
      interior.dispose?.();
      const geometries=new Set(),materials=new Set();
      group.traverse(object=>{if(object.geometry)geometries.add(object.geometry);for(const material of [].concat(object.material||[]))materials.add(material);if(object.isInstancedMesh)object.dispose();});
      for(const geometry of geometries)geometry.dispose();for(const material of materials)material.dispose();group.removeFromParent();
    }};
}

export function pickRoomFloor(camera,pointer,room){
  if(!room.group.visible)return null;
  const ray=new T.Raycaster();ray.setFromCamera(pointer,camera);
  const hit=ray.intersectObject(room.floor,false)[0];
  return hit?{x:T.MathUtils.clamp(hit.point.x,ROOM.walk.minX,ROOM.walk.maxX),z:T.MathUtils.clamp(hit.point.z,ROOM.walk.minZ,ROOM.walk.maxZ)}:null;
}
