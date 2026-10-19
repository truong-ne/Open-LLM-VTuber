import * as T from '../3d/vendor/three.module.js';
import {drawTvScreen,SCREEN_WIDTH,SCREEN_HEIGHT} from './tv-screen.mjs?v=4';

export const TV_SPEC=Object.freeze({width:3.4,height:1.9125,x:-.55,y:1.65,z:-3.8});
export function buildTvStudio(group){
  const ownedTextures=[];
  let ready=typeof document==='undefined';
  const backdropMaterial=new T.MeshBasicMaterial({color:0xffffff,toneMapped:false});
  if(typeof document!=='undefined'){
    const art=new T.TextureLoader().load(new URL('./assets/mao-anime-game-room-v3.png',import.meta.url).href,()=>{ready=true;},undefined,error=>{ready=true;backdropMaterial.map=null;backdropMaterial.color.setHex(0x102c42);backdropMaterial.needsUpdate=true;console.warn('Mao game backdrop:',error);});
    art.colorSpace=T.SRGBColorSpace;backdropMaterial.map=art;ownedTextures.push(art);
  }else backdropMaterial.color.setHex(0x102c42);
  const backdrop=new T.Mesh(new T.PlaneGeometry(6.2,3.489),backdropMaterial);backdrop.name='mao-generated-game-backdrop';backdrop.position.set(-.1,1.45,-4.94);group.add(backdrop);
  const {width:w,height:h,x,y,z}=TV_SPEC;
  // The word game is a frameless graphic on the anime room wall. Keep the
  // live canvas, without physical TV hardware or a presenter pedestal.
  let canvas=null;
  if(typeof document!=='undefined'){canvas=document.createElement('canvas');canvas.width=SCREEN_WIDTH;canvas.height=SCREEN_HEIGHT;drawTvScreen(canvas,null);}
  const texture=canvas?new T.CanvasTexture(canvas):new T.DataTexture(new Uint8Array([8,20,35,255]),1,1);
  texture.colorSpace=T.SRGBColorSpace;texture.minFilter=T.LinearFilter;texture.magFilter=T.LinearFilter;texture.generateMipmaps=false;texture.needsUpdate=true;ownedTextures.push(texture);
  const screen=new T.Mesh(new T.PlaneGeometry(w,h),new T.MeshBasicMaterial({map:texture,toneMapped:false}));screen.name='mao-studio-tv';screen.position.set(x,y,z+.012);group.add(screen);
  let lastRevision=-1,source;
  return {theme:'mao-tv-studio',obstacles:[],screen,get ready(){return ready;},
    update(dt,camera){if(!group.visible)return;
      if(camera){const height=2*(camera.position.z-backdrop.position.z)*Math.tan(T.MathUtils.degToRad(camera.fov/2))/camera.zoom;backdrop.scale.setScalar(Math.max(height/3.489,height*camera.aspect/6.2)*1.01);}
      const controller=globalThis.window?.maoWordGame;if(controller?.canvas&&(source!==controller.canvas||lastRevision!==controller.textureRevision)){source=controller.canvas;lastRevision=controller.textureRevision;texture.image=source;texture.needsUpdate=true;}},
    dispose(){for(const value of ownedTextures)value.dispose();}
  };
}
