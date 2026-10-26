import * as T from '../3d/vendor/three.module.js';
import {GLTFLoader} from '../3d/vendor/loaders/GLTFLoader.js';
import {PERFORMANCE_ACTIONS} from './performance-motion.mjs?v=4';
import {AdaptiveBodyActor as BodyActor} from './motor-body.mjs?v=5';
import {MotorPolicy} from './motor-policy.mjs';
import {FACE_PRESETS} from './performance-face.mjs?v=1';
import {AdaptiveFaceRig as FaceRig} from './motor-face.mjs';
import {selectPerformance,faceForAction} from './performance-context.mjs?v=2';
import {SpeechAttention} from './speech-attention.mjs?v=2';
import {attachPetPlacement} from './pet-placement.mjs?v=7';
import {configureAvatarCamera,availableAvatarHeight} from './room-view.mjs?v=10';
import {DesktopSpace,FloorFeet,locomotionFrame} from './desktop-space.mjs?v=6';
import {ROOM,createDesktopRoom,pickRoomFloor} from './desktop-room.mjs?v=12';
import {sceneForGame} from './game-scene.mjs?v=4';
import {headingDegrees,cardinal} from './room-orientation.mjs?v=4';
import {mountCommentPanel} from './comment-panel.mjs?v=3';
import {createSceneTransition} from './scene-transition.mjs?v=2';
import {mountSingingPlayer} from './singing-player.mjs';
import {validateDance} from './dance-body.mjs?v=2';

// Each song may name a choreography (knowledge/mao_songs.vi.json "dance"). The
// module loads once; until it is ready, or when it is missing, Mao keeps the
// default hip sway.
const dances=new Map();
function danceFor(name){
  if(!/^[a-z0-9-]{1,64}$/.test(name||''))return null;
  if(!dances.has(name)){
    dances.set(name,null);
    import(`./dances/${name}.mjs?v=1`).then(module=>dances.set(name,validateDance(module.default))).catch(()=>dances.set(name,false));
  }
  return dances.get(name)||null;
}

export async function mountNativeAvatar(container,bridge){
  const {state}=bridge,ipc=window.electron?.ipcRenderer;
  const portrait=()=>bridge.options.presentation==='portrait';
  const gltf=await new GLTFLoader().loadAsync(new URL('character.glb',import.meta.url).href);
  if(!container.isConnected)return {dispose(){}};
  const canvas=document.createElement('canvas'),stage=document.createElement('div');
  canvas.id='mao-native-avatar';canvas.setAttribute('aria-label','Mao Draco 3D');
  Object.assign(canvas.style,{position:'absolute',inset:'0',width:'100%',height:'100%',pointerEvents:'none'});
  Object.assign(stage.style,{position:'absolute',inset:'0',cursor:'grab',touchAction:'none'});
  container.append(canvas,stage);
  const header=document.createElement('div');header.className='mao-studio-top';
  const mark=document.createElement('div');mark.className='mao-studio-mark';mark.textContent='Mao ';
  const brand=document.createElement('span');brand.textContent='VTuber';mark.append(brand);
  const connection=document.createElement('span');connection.className='mao-studio-live';
  header.append(mark,connection);container.append(header);
  const comments=portrait()?null:mountCommentPanel(container,{getMode:()=>bridge.options.mode,fetcher:bridge.commentFeedFetcher||fetch});
  let disposed=false,frame,last=performance.now(),lastAudio=null,mode,lastPublish=0,lastRegions=0;
  const renderer=new T.WebGLRenderer({canvas,alpha:true,antialias:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,portrait()?1:1.5));renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;
  const scene=new T.Scene(),camera=new T.PerspectiveCamera(32,1,.02,30);
  scene.add(new T.HemisphereLight(0xfff9ff,0x807587,2));
  const light=new T.DirectionalLight(0xfff6ed,2);light.position.set(-2,3,4);scene.add(light);
  const rim=new T.DirectionalLight(0xd3bef8,1.1);rim.position.set(2,2,-3);scene.add(rim);
  const attention=new SpeechAttention(),spaces={pet:new DesktopSpace(),window:new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32}),game:new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32}),concert:new DesktopSpace({bounds:ROOM.walk,roam:'room',speed:.32})};
  spaces.window.x=0;spaces.window.z=-1.65;spaces.window.nextRoam=Infinity;
  spaces.game.x=1.65;spaces.game.z=-2.5;spaces.game.nextRoam=Infinity;
  spaces.concert.x=0;spaces.concert.z=-1.65;spaces.concert.nextRoam=Infinity;
  let space=spaces[bridge.options.mode==='pet'?'pet':'window'],feet;
  const spaceRoot=new T.Group(),rooms={lounge:createDesktopRoom({theme:'lounge'}),studio:createDesktopRoom({theme:'studio'}),concert:createDesktopRoom({theme:'concert'})};
  let room=rooms.lounge,sceneKind='lounge',sceneMode;
  let transition,singing,presentedRound='',presenting=false,nextPresentationAttempt=0,wasSinging=false;
  scene.add(spaceRoot,...Object.values(rooms).map(value=>value.group));
  // Keep a slightly closer lounge view and the readable TV framing. Navigation
  // uses world coordinates and the actual camera bearing independently of UI.
  const roomView={kind:'room',studio:false,lounge:true,direction:new T.Vector3(0,.02,1)},fullRoomView={zoom:1.15},loungeView={zoom:1.32};
  if(portrait())loungeView.zoom=1.52;
  const windowView=()=>roomView.lounge?loungeView:fullRoomView;
  const options=()=>bridge.options;
  document.body.dataset.mode=options().mode;
  const placement=attachPetPlacement({stage,canZoom:()=>options().mode==='pet'&&options().scrollToResize,
    extraRegions:()=>[document.getElementById('mao-native-input-subtitle')],
    onRegions:data=>ipc?.send('mao-draco-hit-regions',{...data,forceIgnore:options().forceIgnoreMouse,dragging:data.dragging||!!bridge.subtitleDragging}),
    onChange:view=>{Object.assign(state,{zoom:view.zoom,petX:view.x,petY:view.y});}
  });
  let settingsScale=options().scale;
  const refresh=()=>{
    document.body.dataset.mode=options().mode;
    header.style.display=options().mode==='window'&&!portrait()?'flex':'none';
    layoutDirty=true;
    stage.style.pointerEvents=portrait()||options().mode==='pet'&&options().forceIgnoreMouse?'none':'auto';
    const pet=options().mode==='pet';syncScene();
    renderer.setClearColor(0x07111e,pet||portrait()?0:1);
    stage.style.cursor=pet?'grab':'default';
    if(Number.isFinite(options().scale)&&options().scale>0){
      const previous=settingsScale;settingsScale=options().scale;
      if(Number.isFinite(previous)&&previous>0&&previous!==settingsScale)placement.zoom(settingsScale/previous);
    }
    placement.refresh();
  };
  stage.oncontextmenu=event=>{if(options().mode==='pet'){event.preventDefault();window.api?.showContextMenu();}};
  stage.onpointerenter=()=>window.api?.updateComponentHover('live2d-model',true);
  stage.onpointerleave=()=>window.api?.updateComponentHover('live2d-model',false);
  const walkToFloor=event=>{
    if(options().mode!=='window'||singing?.state&&['waiting','loading','playing'].includes(singing.state.phase))return;
    const rect=canvas.getBoundingClientRect(),pointer=new T.Vector2((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
    const point=pickRoomFloor(camera,pointer,room);
    if(point){attention.moveTo(space,point.x,point.z);room.marker.position.set(point.x,.006,point.z);room.marker.visible=true;}
  };
  const asset=gltf.scene,wrapper=new T.Group();wrapper.add(asset);spaceRoot.add(wrapper);asset.updateMatrixWorld(true);
  const bounds=new T.Box3().setFromObject(asset),center=bounds.getCenter(new T.Vector3()),scale=1.8/bounds.getSize(new T.Vector3()).y;
  wrapper.scale.setScalar(scale);wrapper.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale);wrapper.updateMatrixWorld(true);
  const footCenter=asset.getObjectByName('draco_ankleL').getWorldPosition(new T.Vector3()).add(asset.getObjectByName('draco_ankleR').getWorldPosition(new T.Vector3())).multiplyScalar(.5);
  wrapper.position.x-=footCenter.x;wrapper.position.z-=footCenter.z;wrapper.updateMatrixWorld(true);
  asset.traverse(mesh=>{if(mesh.isMesh)mesh.frustumCulled=false;});
  let motorStorage;try{motorStorage=window.localStorage;}catch{}
  const motorPolicy=new MotorPolicy(motorStorage),actor=new BodyActor(asset,motorPolicy),face=new FaceRig(asset);state.faceMeshes=face.meshes.length;state.performanceVersion='adaptive-motor-v1';state.facePresetCount=Object.keys(FACE_PRESETS).length;
  const motorNotice=document.createElement('div');motorNotice.setAttribute('role','status');Object.assign(motorNotice.style,{position:'absolute',bottom:'90px',left:'12px',maxWidth:'360px',padding:'10px',borderRadius:'10px',background:'#241c32ee',color:'#fff',fontSize:'13px',pointerEvents:'none',zIndex:30,display:'none'});container.append(motorNotice);let noticeTimer;
  const operatorFeedback=text=>{if(!motorPolicy.feedback(text))return false;motorNotice.textContent=motorPolicy.message;motorNotice.style.display='block';clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>motorNotice.style.display='none',5500);return true;};
  let manualActionUntil=0,audioFace='neutral',faceUntil=0;
  const footSets={pet:new FloorFeet(actor.feet),window:new FloorFeet(actor.feet),game:new FloorFeet(actor.feet),concert:new FloorFeet(actor.feet)};
  feet=footSets[options().mode==='pet'?'pet':'window'];
  function applyScene(next){
    const pet=options().mode==='pet',key=pet?'pet':next==='studio'?'game':next==='concert'?'concert':'window';
    if(sceneKind===next&&sceneMode===options().mode&&space===spaces[key])return;
    sceneKind=next;sceneMode=options().mode;room=rooms[next];space=spaces[key];feet=footSets[key];
    for(const [name,value] of Object.entries(rooms)){value.setMode(!pet&&!portrait()&&name===next?'window':'pet');value.marker.visible=false;}
    roomView.studio=next==='studio';roomView.lounge=next!=='studio';
    state.background=pet?'none':next==='studio'?'tv-studio':next==='concert'?'concert':'disco';
  }
  async function presentGame(){
    if(document.visibilityState==='hidden')return;
    const game=window.maoWordGame?.state;
    if(game?.phase!=='waiting'||game.round_id===presentedRound||presenting||Date.now()<nextPresentationAttempt)return;
    if(options().mode!=='pet'&&(sceneKind!=='studio'||!transition?.ready))return;
    presenting=true;nextPresentationAttempt=Date.now()+1500;
    try{
      const response=await fetch('http://127.0.0.1:12393/api/vuatiengviet/presentation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({round_id:game.round_id}),signal:AbortSignal.timeout(3000)});
      if(response.ok&&(await response.json()).accepted)presentedRound=game.round_id;
    }catch{}finally{presenting=false;}
  }
  function syncScene(){
    const pet=options().mode==='pet',controller=window.maoWordGame;
    const next=portrait()?'lounge':['loading','playing'].includes(singing?.state?.phase)?'concert':sceneForGame(controller?.state,Date.now(),controller?.clockOffset||0);
    if(!transition||pet||sceneMode!==options().mode){applyScene(next);if(transition)transition.element.hidden=true;}
    else{transition.request(next);transition.update();}
    state.sceneTransition=pet?'idle':transition?.timeline.phase||'idle';
    presentGame();
  }
  const hitAvatar=event=>{
    const rect=canvas.getBoundingClientRect(),ray=new T.Raycaster();ray.setFromCamera(new T.Vector2((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1),camera);
    return ray.intersectObject(asset,true).length>0;
  };
  stage.ondblclick=event=>{
    if(options().mode==='window'&&!hitAvatar(event))walkToFloor(event);
  };
  for(let i=0;i<180;i++)actor.update(1/120);
  let tap;
  stage.addEventListener('pointerdown',event=>{if(event.button===0)tap={x:event.clientX,y:event.clientY,time:performance.now()};});
  stage.addEventListener('pointerup',event=>{
    if(!singing?.pose.playing&&tap&&performance.now()-tap.time<250&&Math.hypot(event.clientX-tap.x,event.clientY-tap.y)<5&&options().pointerInteractive!==false&&hitAvatar(event))actor.play('greet');
    tap=null;
  });
  function dispose(){
    if(disposed)return;disposed=true;cancelAnimationFrame(frame);placement.dispose();layoutObserver.disconnect();window.removeEventListener('resize',invalidateLayout);
    window.api?.updateComponentHover('live2d-model',false);
    ipc?.send('mao-draco-hit-regions',{active:false,mode:options().mode,rectangles:[]});
    asset.traverse(mesh=>{if(!mesh.isMesh)return;mesh.geometry.dispose();for(const material of [].concat(mesh.material)){for(const value of Object.values(material))if(value?.isTexture)value.dispose();material.dispose();}});
    for(const value of Object.values(rooms))value.dispose();
    renderer.dispose();comments?.dispose();transition?.dispose();singing?.dispose();if(window.maoSinging===singing)delete window.maoSinging;clearTimeout(noticeTimer);motorNotice.remove();header.remove();canvas.remove();stage.remove();
    if(bridge.renderer?.dispose===dispose){bridge.renderer=null;state.ready=false;}
  }
  let w=0,h=0,layoutDirty=true,observedFooter;
  const invalidateLayout=()=>{layoutDirty=true;},layoutObserver=new ResizeObserver(invalidateLayout);
  layoutObserver.observe(container);window.addEventListener('resize',invalidateLayout);
  if(!container.isConnected){dispose();return {dispose};}
  const performAction=action=>{
    if(['waiting','loading','playing'].includes(singing?.state?.phase))return false;
    if(!PERFORMANCE_ACTIONS.includes(action))return false;
    if(!attention.locked(space)){const resume=space.nextRoam!==Infinity;space.perform('stop');if(resume)space.nextRoam=space.time+9;}
    actor.clearMotor();actor.play(action);manualActionUntil=actor.time+7.05;return true;
  };
  const prepareSpeech=audio=>{
    attention.focus(space);
    return new Promise(resolve=>{
      const started=performance.now();
      const check=()=>{
        if(disposed||bridge.audio!==audio||!bridge.speechSession){resolve(false);return;}
        if(attention.ready(space,feet)){resolve(true);return;}
        if(performance.now()-started>8000){resolve(false);return;}
        setTimeout(check,25);
      };check();
    });
  };
  transition=createSceneTransition(container,{onCommit:applyScene,isReady:scene=>state.ready&&rooms[scene].ready});
  singing=mountSingingPlayer(container,{fetcher:bridge.singingFetcher||fetch,getMode:()=>options().mode,canPlay:()=>sceneKind==='concert'&&(options().mode==='pet'||transition.ready)});window.maoSinging=singing;
  const performing=()=>['waiting','loading','playing'].includes(singing?.state?.phase);
  bridge.renderer={refresh,dispose,prepareSpeech,operatorFeedback,perform:command=>!performing()&&attention.command(space,command),performAction,performBody:command=>!performing()&&mode==='window'&&attention.bodyCommand(space,command)};refresh();
  if(bridge.pendingCommand){space.perform(bridge.pendingCommand);bridge.pendingCommand=null;}
  if(bridge.pendingAction){performAction(bridge.pendingAction);bridge.pendingAction=null;}
  const tick=now=>{
    if(disposed)return;
    if(options().maxFps&&now-last<1000/options().maxFps){frame=requestAnimationFrame(tick);return;}
    const dt=Math.min((now-last)/1000,.1);last=now;
    if(mode!==options().mode){mode=options().mode;refresh();}
    syncScene();
    if(layoutDirty){
      layoutDirty=false;const footer=document.getElementById('mao-window-footer');
      if(footer!==observedFooter){if(observedFooter)layoutObserver.unobserve(observedFooter);observedFooter=footer;if(footer)layoutObserver.observe(footer);}
      const cw=container.clientWidth,ch=portrait()?container.clientHeight:availableAvatarHeight(mode,container.getBoundingClientRect(),footer?.getBoundingClientRect());
      if(cw!==w||ch!==h){w=cw;h=ch;canvas.style.height=`${h}px`;renderer.setSize(w,h,false);comments?.setViewport(w,h);transition.setViewport(w,h);}
    }
    if(w>0&&h>0&&document.visibilityState==='visible'){
      const view=placement.getState(),pet=mode==='pet';
      configureAvatarCamera(camera,{mode,view:pet?view:windowView(),width:w,height:h,roomView});
      // Pet uses a flat screen-facing presentation. In the room the audience
      // is the actual fitted camera, including perspective offset.
      space.setAudienceYaw(pet?0:Math.atan2(camera.position.x-space.x,camera.position.z-space.z));
      // Stay on the chosen spot in window mode. Explicit movement commands and
      // gestures still run, without restarting autonomous walks afterwards.
      if(!pet)space.nextRoam=Infinity;
      const songPose=singing.pose;
      attention.update(space,bridge.speechSession||songPose.playing);
      space.update(dt,{enabled:document.visibilityState==='visible',paused:placement.isDragging()||!!bridge.subtitleDragging});
      // Simulate bones/IK/cloth in one stable coordinate system, then place the
      // complete character on the floor for rendering. This keeps foot anchors
      // and garment constraints from fighting the animated display root.
      spaceRoot.position.set(0,0,0);spaceRoot.rotation.set(0,0,0);spaceRoot.updateMatrixWorld(true);
      actor.setLocomotion(locomotionFrame(space,feet,dt));
      const audio=bridge.audio,playing=songPose.playing||!!audio&&!audio.paused&&!audio.ended;
      actor.songPerformance=songPose.playing?songPose:null;
      const choreography=songPose.playing?danceFor(singing.state?.song?.dance):null;
      if(songPose.playing){
        actor.clearMotor();
        if(choreography){actor.setDance(choreography,songPose.time,songPose.bpm,{live:true});if(actor.action!=='idle')actor.play('idle');}
        else{actor.clearDance();if(actor.action!=='hipSway')actor.play('hipSway');actor.started=actor.time-2;}
        manualActionUntil=actor.time+.3;
      }else{actor.clearDance();if(wasSinging){actor.play('bow');manualActionUntil=actor.time+6.7;}}
      wasSinging=songPose.playing;
      if(playing&&!songPose.playing&&audio!==lastAudio){
        lastAudio=audio;const text=bridge.payload?.displayText?.text||'',performance=selectPerformance(text,bridge.payload?.expressions,bridge.payload?.motions);
        if(actor.time>=manualActionUntil&&(actor.action==='idle'||actor.action==='talk'||actor.time-actor.started>=2.4)){
          if(actor.action!==performance.action)actor.play(performance.action);
          audioFace=performance.face;faceUntil=actor.time+4;
          if(bridge.payload?.pose)state.lastMotorAccepted=actor.setMotor(bridge.payload.pose);
        }
      }
      const index=playing&&audio?Math.floor(audio.currentTime*1000/(bridge.payload?.sliceLength||20)):0;
      const volume=songPose.playing?songPose.volume:playing?(bridge.payload?.volumes?.[index]||0):0;
      if(playing&&actor.action==='idle'&&actor.time>=manualActionUntil)actor.play('talk');
      if(!playing&&!bridge.speechSession)actor.clearMotor();
      actor.update(dt,volume*.15);
      face.setExpression(songPose.playing?'smile':actor.action==='talk'&&playing&&actor.time<faceUntil?audioFace:faceForAction(actor.action));
      face.setMotor(actor.motorRaw?motorPolicy.apply(actor.motorRaw):null,actor.motorAmount);
      Object.assign(state,{motorActive:actor.motorActive,motorRevision:motorPolicy.revision,motorSaved:motorPolicy.saved,motorFeedback:motorPolicy.message,motorRejected:actor.motorRejected});
      state.mouthOpen=face.update(volume,playing,dt);state.mouthPeak=face.peak;state.faceExpression=face.expression;state.bodyAction=actor.action;state.speechFocused=attention.locked(space);
      spaceRoot.position.set(space.x,0,space.z);spaceRoot.rotation.y=space.yaw;spaceRoot.updateMatrixWorld(true);room.shadow.position.set(space.x,.003,space.z);
      if(room.marker.visible&&space.phase==='idle')room.marker.visible=false;
      room.update(dt,camera);renderer.render(scene,camera);Object.assign(state,{ready:true,frames:state.frames+1,drawCalls:renderer.info.render.calls,action:space.phase==='idle'?actor.action:space.phase,spaceX:space.x,spaceZ:space.z,spaceYaw:space.yaw,bodyHeading:headingDegrees(space.yaw),bodyDirection:cardinal(space.yaw),bodyPhase:space.phase,bodyTargetX:space.segment?.x??space.x,bodyTargetZ:space.segment?.z??space.z,bodyStopped:attention.stopped(space),audienceYaw:space.audienceYaw,facingError:Math.atan2(Math.sin(space.audienceYaw-space.yaw),Math.cos(space.audienceYaw-space.yaw)),completedSpins:space.completedSpins});
    }
    if(mode==='pet'&&document.visibilityState==='visible'&&now-lastRegions>60){placement.regions();lastRegions=now;}
    if(now-lastPublish>1500){
      connection.textContent=state.socket==='open'?'ĐÃ KẾT NỐI':'ĐANG KẾT NỐI';
      const subtitle=document.getElementById('mao-native-input-subtitle');
      ipc?.send('mao-draco-status',{...state,mode,zoom:mode==='window'?windowView().zoom:placement.getState().zoom,floorVisible:room.group.visible,roomVisible:room.group.visible,roomWidth:ROOM.width,roomDepth:ROOM.depth,roomCamera:'room',roomTheme:room.theme,viewportWidth:w,viewportHeight:h,visible:document.visibilityState==='visible',petChatVisible:!!subtitle,scrollToResize:options().scrollToResize,forceIgnoreMouse:options().forceIgnoreMouse,updatedAt:Date.now()});lastPublish=now;
    }
    frame=requestAnimationFrame(tick);
  };
  frame=requestAnimationFrame(tick);window.api?.setMode(new URLSearchParams(location.search).get('mao-mode')==='window'?'window':'pet');
  return {dispose};
}
