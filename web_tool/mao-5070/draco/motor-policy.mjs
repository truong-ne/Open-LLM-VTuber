// This schema is deliberately independent of bone names and JavaScript source.
export const MOTOR_LIMITS={tilt:[-12,12],nod:[-10,12],lean:[-4,4],left:[0,1],right:[0,1],height:[-.10,.10],smile:[0,1],brow:[0,1],eyes:[0,1],duration:[2,7]};
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
export function validateMotor(value){
  if(!value||typeof value!=='object'||Array.isArray(value))return null;
  const entries=Object.entries(value);
  if(!entries.length||!entries.some(([key])=>key!=='duration'))return null;
  const result={};
  for(const [key,n] of entries){if(!Object.hasOwn(MOTOR_LIMITS,key)||typeof n!=='number'||!Number.isFinite(n))return null;result[key]=clamp(n,...MOTOR_LIMITS[key]);}
  return result;
}
const DEFAULT={gain:1,tempo:1,height:0,face:1};
const PROFILE_LIMITS={gain:[.35,1],tempo:[.65,1.35],height:[-.06,.06],face:[.4,1.2]};
function validProfile(p){return p&&Object.keys(p).length===4&&Object.entries(PROFILE_LIMITS).every(([k,[a,b]])=>typeof p[k]==='number'&&Number.isFinite(p[k])&&p[k]>=a&&p[k]<=b);}
export const MOTOR_STORAGE_KEY='mao.draco.motor-learning.v1';
export class MotorPolicy{
  constructor(storage=null){
    this.storage=storage;this.profile={...DEFAULT};this.history=[];this.revision=0;this.saved=!!storage;this.message='Chưa có chỉnh sửa cử động.';
    try{const p=JSON.parse(storage?.getItem(MOTOR_STORAGE_KEY)||'null');if(p?.version===1&&validProfile(p.profile)&&Number.isSafeInteger(p.revision)&&p.revision>=0){this.profile=p.profile;this.revision=p.revision;this.history=(Array.isArray(p.history)?p.history:[]).filter(validProfile).slice(-32);}}
    catch{this.saved=false;this.message='Không đọc được bộ nhớ cử động; đang dùng mặc định.';}
  }
  persist(){
    try{if(!this.storage)throw Error('storage unavailable');this.storage.setItem(MOTOR_STORAGE_KEY,JSON.stringify({version:1,profile:this.profile,revision:this.revision,history:this.history}));this.saved=true;}
    catch{this.saved=false;this.message+=' Chưa lưu được xuống bộ nhớ desktop.';}
  }
  // Called only from the desktop's outgoing *typed operator input*, never
  // model output, TikTok payloads, ASR transcripts or audience chat.
  feedback(text){
    if(typeof text!=='string'||text.length>180)return false;
    const n=text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/Đ/g,'D').toLowerCase().trim().replace(/[!.?]+$/,'');
    if(n==='/co-the xem'){this.message=`Cử động: lực ${this.profile.gain.toFixed(2)}, nhịp ${this.profile.tempo.toFixed(2)}, độ cao tay ${this.profile.height.toFixed(3)}; ${this.revision} lần chỉnh. ${this.saved?'Đã lưu.':'Chưa lưu được.'}`;return true;}
    let next={...this.profile},message;
    if(n==='/co-the hoan-tac'){
      if(!this.history.length){this.message='Chưa có chỉnh sửa để hoàn tác.';return true;}
      next=this.history.pop();message='Đã hoàn tác chỉnh sửa cử động gần nhất.';
    }else{
      if(n==='/co-the mac-dinh'){next={...DEFAULT};message='Đã đặt cử động về mặc định.';}
      else{
        // Exact short corrections avoid learning from a quoted story/question.
        const match=n.match(/^(?:mao[, ]+)?(cu dong nhe hon|cu dong manh hon|cu dong nhanh hon|cu dong cham hon|tay thap hon|tay cao hon|bieu cam ro hon|bieu cam nhe hon)$/);
        if(!match)return false;
        const changes={'cu dong nhe hon':['gain',-.12],'cu dong manh hon':['gain',.12],'cu dong nhanh hon':['tempo',.1],'cu dong cham hon':['tempo',-.1],'tay thap hon':['height',-.015],'tay cao hon':['height',.015],'bieu cam ro hon':['face',.1],'bieu cam nhe hon':['face',-.1]};
        const [key,delta]=changes[match[1]];next[key]=clamp(next[key]+delta,...PROFILE_LIMITS[key]);message='Đã ghi nhớ: '+text.trim();
      }
      this.history.push({...this.profile});this.history=this.history.slice(-32);
    }
    this.profile=next;this.revision++;this.message=message;this.persist();return true;
  }
  apply(raw){
    const pose=validateMotor(raw);if(!pose)return null;
    for(const key of ['tilt','nod','lean','left','right'])if(key in pose)pose[key]*=this.profile.gain;
    if('left' in pose||'right' in pose)pose.height=clamp((pose.height||0)+this.profile.height,...MOTOR_LIMITS.height);
    for(const key of ['smile','brow','eyes'])if(key in pose)pose[key]=clamp(pose[key]*this.profile.face,0,1);
    return pose;
  }
}
