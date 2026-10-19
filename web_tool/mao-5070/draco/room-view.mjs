import * as T from '../3d/vendor/three.module.js';
import {petCameraView} from './pet-placement.mjs';
import {ROOM} from './desktop-room.mjs';

// Include the walking limits, the character's silhouette during turns and
// the floor. Fit in the avatar pane, which can be narrower than the window
// because the original chat sidebar remains alongside it.
export const ROOM_BOUNDS=new T.Box3(new T.Vector3(ROOM.minX,-.04,ROOM.minZ),new T.Vector3(ROOM.maxX,ROOM.height,ROOM.maxZ));
const DEFAULT_DIRECTION=new T.Vector3(0,.075,1),ORIGIN=new T.Vector3(),cameraFrames=new WeakMap();

export function availableAvatarHeight(mode,pane,footer){
  if(mode==='pet'||!footer||footer.height<=0||footer.right<=pane.left||footer.left>=pane.right)return pane.height;
  return Math.max(1,Math.min(pane.height,footer.top-pane.top));
}

export function configureAvatarCamera(camera,{mode,view,width,height,roomView={}}){
  // A long-lens broadcast view makes the TV readable without flattening the
  // character or replacing the real 3D stage with a screenshot.
  if(mode==='window'&&roomView.studio){
    const previous=cameraFrames.get(camera);
    if(previous?.studio&&previous.width===width&&previous.height===height&&previous.zoom===view.zoom)return false;
    camera.fov=8;camera.clearViewOffset();camera.aspect=width/height;
    const distance=Math.max(1.77,2.9/camera.aspect)/Math.tan(T.MathUtils.degToRad(4));
    camera.position.set(-.1,1.45,-3+distance);camera.lookAt(-.1,1.45,-3);
    camera.far=distance+25;camera.zoom=view.zoom/1.15;camera.updateProjectionMatrix();camera.updateMatrixWorld(true);cameraFrames.set(camera,{studio:true,width,height,zoom:view.zoom});return true;
  }
  if(mode==='window'&&roomView.lounge&&roomView.kind!=='follow'){
    const previous=cameraFrames.get(camera);
    if(previous?.loungePortrait&&previous.width===width&&previous.height===height&&previous.zoom===view.zoom)return false;
    // Frame Mao from nearly eye level rather than fitting the room's outer
    // corners. The long lens keeps the back wall behind the full-body shot.
    camera.fov=12;camera.clearViewOffset();camera.aspect=width/height;
    const distance=Math.max(1.55,.85/camera.aspect)/Math.tan(T.MathUtils.degToRad(6));
    camera.position.set(0,1+distance*.02,-1.65+distance);
    camera.lookAt(0,1,-1.65);camera.far=distance+25;
    camera.zoom=view.zoom/1.15;camera.updateProjectionMatrix();camera.updateMatrixWorld(true);
    cameraFrames.set(camera,{loungePortrait:true,width,height,zoom:view.zoom});return true;
  }
  if(camera.fov===8||camera.fov===12){camera.fov=32;cameraFrames.delete(camera);}
  const pet=mode==='pet',follow=!pet&&roomView.kind==='follow',focus=roomView.focus;
  const direction=roomView.direction||DEFAULT_DIRECTION,fx=follow?(focus?.x||0):0,fz=follow?(focus?.z||0):0;
  const x=pet?view.x:0,y=pet?view.y:0,vw=pet?view.width:0,vh=pet?view.height:0;
  let frame=cameraFrames.get(camera);
  if(frame&&frame.mode===mode&&frame.follow===follow&&frame.lounge===roomView.lounge&&frame.width===width&&frame.height===height&&frame.zoom===view.zoom&&frame.fov===camera.fov&&frame.x===x&&frame.y===y&&frame.vw===vw&&frame.vh===vh&&frame.fx===fx&&frame.fz===fz&&(pet||frame.dx===direction.x&&frame.dy===direction.y&&frame.dz===direction.z))return false;
  if(!frame){frame={target:new T.Vector3(),point:new T.Vector3(),direction:new T.Vector3(),basis:new T.Quaternion(),matrix:new T.Matrix4(),bounds:new T.Box3()};cameraFrames.set(camera,frame);}
  Object.assign(frame,{mode,follow,lounge:roomView.lounge,width,height,zoom:view.zoom,fov:camera.fov,x,y,vw,vh,fx,fz,dx:direction.x,dy:direction.y,dz:direction.z});
  if(mode==='pet'){
    camera.far=30;
    const r=petCameraView(view,{width,height});
    camera.zoom=1;camera.setViewOffset(r.fullWidth,r.fullHeight,r.offsetX,r.offsetY,r.width,r.height);
    camera.position.set(0,.975,3.45*Math.max(1,.65/(view.width/view.height)));
    camera.lookAt(0,.94,0);
  }else{
    camera.clearViewOffset();camera.aspect=width/height;
    const target=follow?frame.target.set(fx,.9,fz):frame.target.set(0,2.2,-2.8);
    if(follow){frame.bounds.min.set(fx-.85,-.04,fz-.85);frame.bounds.max.set(fx+.85,1.94,fz+.85);}
    const bounds=follow?frame.bounds:ROOM_BOUNDS,aim=frame.direction.copy(direction).normalize();
    const basis=frame.basis.setFromRotationMatrix(frame.matrix.lookAt(aim,ORIGIN,camera.up)).invert();
    const tan=Math.tan(T.MathUtils.degToRad(camera.fov)/2);
    let distance=0;
    for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z]){
      const p=frame.point.set(x,y,z).sub(target).applyQuaternion(basis);
      distance=Math.max(distance,p.z+Math.abs(p.x)/(tan*camera.aspect),p.z+Math.abs(p.y)/tan);
    }
    camera.position.copy(target).addScaledVector(aim,distance*1.08);
    camera.lookAt(target);
    camera.far=Math.max(30,distance+20);
    // 1.15 is the original placement's default zoom. Keep free wheel zoom,
    // while its default now shows the complete room instead of just the body.
    camera.zoom=view.zoom/1.15;camera.updateProjectionMatrix();
  }
  camera.updateMatrixWorld(true);
  return true;
}
