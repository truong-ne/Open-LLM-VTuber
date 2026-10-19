// Speech owns orientation and translation; keep turning through the existing
// gait/foot solver, rather than snapping the rendered character around.
export class SpeechAttention{
  constructor(){this.spaces=new Map();}
  locked(space){return this.spaces.has(space);}
  focus(space){
    if(this.locked(space))return;
    this.spaces.set(space,{stopped:space.nextRoam===Infinity,pending:null});
    space.perform('stop');
  }
  stopped(space){return this.spaces.get(space)?.stopped??(space.nextRoam===Infinity);}
  command(space,command){
    const held=this.spaces.get(space);if(!held)return space.perform(command);
    if(command==='stop'){held.stopped=true;held.pending=null;}else held.pending={command};
    return true;
  }
  bodyCommand(space,command){
    // Queue AI destinations until the whole spoken turn ends; manual intent
    // and an explicit stop always take priority over an AI suggestion.
    const held=this.spaces.get(space);
    if(this.stopped(space)||held?.pending||space.phase!=='idle')return false;
    return this.command(space,command);
  }
  moveTo(space,x,z){
    if(!Number.isFinite(x)||!Number.isFinite(z))return false;
    const held=this.spaces.get(space);if(!held)return space.moveTo(x,z);
    held.pending={x,z};return true;
  }
  release(){
    for(const [space,held] of this.spaces){
      if(held.pending){
        if(held.pending.command)space.perform(held.pending.command);else space.moveTo(held.pending.x,held.pending.z);
      }else space.nextRoam=held.stopped?Infinity:space.time+5;
    }
    this.spaces.clear();
  }
  update(space,held){if(held)this.focus(space);else this.release();}
  ready(space,feet){
    const error=Math.atan2(Math.sin(space.audienceYaw-space.yaw),Math.cos(space.audienceYaw-space.yaw));
    return this.locked(space)&&Math.abs(error)<.025&&space.pose.speed<.002&&Math.abs(space.pose.yawRate)<.03
      &&Object.values(feet.legs).every(leg=>!leg.swing&&!leg.landing);
  }
}
