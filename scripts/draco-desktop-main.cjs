'use strict';
// Loaded by the existing Electron app only for the local Draco launch profile.
exports.loadDraco = window => {
  if (process.env.MAO_DESKTOP_MODEL !== 'draco') return false;
  const fs=require('fs'),path=require('path'),{ipcMain,screen}=require('electron');
  const root=process.env.MAO_WORKSPACE;
  if(!root)throw new Error('MAO_WORKSPACE is required for Draco desktop');
  const statusPath=path.join(root,'private','draco-desktop-status.json');
  const write=data=>fs.writeFileSync(statusPath,JSON.stringify({...data,updatedAt:Date.now()},null,2));
  write({model:'draco',ready:false,socket:'starting'});
  ipcMain.on('mao-draco-status',(event,data)=>{
    if(event.sender!==window.webContents||!data||data.model!=='draco')return;
    const safe={};
    for(const key of ['model','ui','ready','frames','drawCalls','socket','audioStarted','audioEnded','audioErrors','action','lastError','visible','queued','playback','mouthOpen','mouthPeak','faceMeshes','zoom','petX','petY','focus','petChatVisible','scrollToResize','forceIgnoreMouse','spaceX','spaceZ','spaceYaw','audienceYaw','facingError','completedSpins','mode','floorVisible','viewportWidth','viewportHeight','background','roomVisible','roomWidth','roomDepth','roomCamera','roomTheme','bodyHeading','bodyDirection','bodyPhase','bodyTargetX','bodyTargetZ','bodyStopped','lastBodyCommand','lastBodyAccepted','faceExpression','performanceVersion','facePresetCount','bodyAction','speechFocused','motorActive','motorRevision','motorSaved','motorFeedback','motorRejected','lastMotorAccepted']){
      const value=data[key];if(['string','number','boolean'].includes(typeof value))safe[key]=typeof value==='string'?value.slice(0,350):value;
    }
    write(safe);
  });
  // Hit test in the app's own main process: Windows forwards mouse-move while
  // click-through is active, but DOM pointer-enter alone cannot reliably turn
  // wheel/click input back on. Keep the rest of the desktop click-through.
  let hit={active:false,mode:'window',dragging:false,rectangles:[]};
  ipcMain.on('mao-draco-hit-regions',(event,data)=>{
    if(event.sender!==window.webContents||!data)return;
    hit={active:data.active!==false,mode:data.mode==='pet'?'pet':'window',forceIgnore:data.forceIgnore===true,dragging:data.dragging===true,rectangles:(Array.isArray(data.rectangles)?data.rectangles:[]).slice(0,8).filter(r=>['x','y','width','height'].every(k=>Number.isFinite(r[k]))&&r.width>0&&r.height>0)};
  });
  const hitTimer=setInterval(()=>{
    if(!hit.active||window.isDestroyed()||!window.isVisible())return;
    const p=screen.getCursorScreenPoint(),bounds=window.getContentBounds(),x=p.x-bounds.x,y=p.y-bounds.y;
    const ignore=hit.mode==='pet'&&(hit.forceIgnore||!hit.dragging&&!hit.rectangles.some(r=>x>=r.x&&y>=r.y&&x<=r.x+r.width&&y<=r.y+r.height));
    window.setIgnoreMouseEvents(ignore,{forward:true});
  },50);hitTimer.unref();window.once('closed',()=>clearInterval(hitTimer));
  window.webContents.on('render-process-gone',(_event,details)=>write({model:'draco',ready:false,lastError:details.reason}));
  window.webContents.on('did-fail-load',(_event,code,description)=>write({model:'draco',ready:false,lastError:`${code}: ${description}`}));
  window.setTitle('Mao VTuber');
  window.webContents.on('console-message',(_event,level,message)=>{
    if(level>=2)fs.appendFileSync(path.join(root,'logs','draco-desktop.log'),`${new Date().toISOString()} ${message.slice(0,1000)}\n`);
  });
  window.loadFile(path.join(__dirname,'../renderer/draco-shell.html'),{query:{'mao-mode':process.env.MAO_DESKTOP_START_MODE==='window'?'window':'pet'}});
  return true;
};
