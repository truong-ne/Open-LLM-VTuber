export class DeliveryClient {
  constructor({send=()=>{},storage=null,uuid=()=>crypto.randomUUID()}={}){
    this.send=send;this.storage=storage;this.uuid=uuid;this.manifest=null;this.segments=new Map();
  }
  resume(){const token=this.storage?.getItem('mao.actor.v1');return token?{type:'resume-actor',token}:null;}
  receive(message){
    if(message.type==='actor-session'){
      if(message.force||!this.storage?.getItem('mao.actor.v1'))this.storage?.setItem('mao.actor.v1',message.token);
    }
    if(message.type==='audio'&&message.segment_id){
      const previous=this.segments.get(message.segment_id);
      if(!previous||previous.turn_id!==message.turn_id||previous.generation_epoch!==message.generation_epoch)
        this.segments.set(message.segment_id,{turn_id:message.turn_id,generation_epoch:message.generation_epoch,segment_id:message.segment_id,status:'sent'});
    }
    if(message.type==='backend-synth-complete'&&message.turn_id)this.manifest=message;
    if(message.type==='control'&&message.text==='conversation-chain-end'){
      this.manifest=null;this.segments.clear();
    }
  }
  mark(payload,status){
    const id=payload.segment_id??payload.delivery?.segment_id;
    const segment=this.segments.get(id);
    const ids=payload.delivery??payload;
    if(segment&&(ids.turn_id!==segment.turn_id||ids.generation_epoch!==segment.generation_epoch))return;
    if(!segment||['completed','failed','interrupted'].includes(segment.status))return;
    segment.status=status;this.send({type:'playback-segment',...segment});
  }
  attach(audio,payload){
    audio.addEventListener('playing',()=>this.mark(payload,'started'),{once:true});
    audio.addEventListener('ended',()=>this.mark(payload,'completed'),{once:true});
    audio.addEventListener('error',()=>this.mark(payload,'failed'),{once:true});
    if(typeof audio.play==='function'){
      const play=audio.play.bind(audio);
      audio.play=(...args)=>{try{return Promise.resolve(play(...args)).catch(error=>{this.mark(payload,'failed');throw error;});}catch(error){this.mark(payload,'failed');throw error;}};
    }
  }
  decorate(message){
    if(message.type==='text-input'||message.type==='mic-audio-end')message={...message,event_id:message.event_id||this.uuid()};
    if(message.type==='frontend-playback-complete'&&this.manifest){
      message={...message,turn_id:this.manifest.turn_id,generation_epoch:this.manifest.generation_epoch};
    }
    return message;
  }
}
