// The existing desktop owns chat, history, mic, audio queue, settings and IPC.
// This bridge supplies only the 3D renderer and its audio-driven animation.
import {desktopCommand} from './desktop-space.mjs?v=6';
import {BODY_COMMANDS} from './room-orientation.mjs';
import {performanceCommand} from './performance-context.mjs?v=2';
export function createNativeBridge(){
  const state={model:'draco',ui:'original-desktop',ready:false,frames:0,drawCalls:0,socket:'connecting',audioStarted:0,audioEnded:0,audioErrors:0,lastError:'',mouthOpen:0,mouthPeak:0};
  const seenBody=new Set();let lastManual=-Infinity;
  const bridge={state,options:{mode:'window',scrollToResize:true,forceIgnoreMouse:false},audio:null,payload:null,renderer:null,pendingCommand:null,
    audioModel:{startRandomMotion(){}},
    operatorFeedback(text){return this.renderer?.operatorFeedback?.(text)||false;},
    command(text){
      const action=performanceCommand(text);
      if(action){lastManual=Date.now();if(this.renderer?.performAction)return this.renderer.performAction(action);this.pendingAction=action;return true;}
      const command=desktopCommand(text);if(!command)return false;lastManual=Date.now();if(this.renderer?.perform)return this.renderer.perform(command);this.pendingCommand=command;return true;
    },
    performBody(body){
      if(!body||typeof body.id!=='string'||body.id.length>80||!BODY_COMMANDS.includes(body.command)||seenBody.has(body.id))return false;
      seenBody.add(body.id);if(seenBody.size>128)seenBody.delete(seenBody.values().next().value);
      state.lastBodyCommand=body.command;
      // User input wins over an AI intent in the following spoken reply.
      state.lastBodyAccepted=!!(this.options.mode==='window'&&Date.now()-lastManual>8000&&this.renderer?.performBody?.(body.command));
      return state.lastBodyAccepted;
    },
    update(options){
      Object.assign(this.options,options);state.socket=String(options.socket||state.socket).toLowerCase();
      if(options.aiState&&options.aiState!=='thinking-speaking')this.speechSession=false;
      this.renderer?.refresh();
    },
    async prepareAudio(audio){
      if(this.audio!==audio)return false;
      this.speechSession=true;
      try{return this.renderer?.prepareSpeech?await this.renderer.prepareSpeech(audio):true;}
      catch(error){state.lastError=String(error.message||error);return false;}
    },
    attachAudio(audio,payload){
      this.audio=audio;this.payload=payload;
      audio.addEventListener('playing',()=>{if(this.audio===audio){state.audioStarted++;state.lastError='';this.performBody(payload?.body);}},{once:true});
      audio.addEventListener('ended',()=>{state.audioEnded++;if(this.audio===audio){this.audio=null;this.payload=null;}},{once:true});
      audio.addEventListener('error',()=>{if(this.audio===audio&&audio.getAttribute('src')){state.audioErrors++;state.lastError='Không phát được âm thanh VieNeu.';}},{once:true});
    }
  };
  return bridge;
}
