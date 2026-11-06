import {storyAction} from './actions.mjs';
import {PERFORMANCE_ACTIONS} from './performance-motion.mjs?v=10';

const faceMap={hipSway:'smile',refuse:'flat',laugh:'squint',chuckle:'squint',celebrate:'squint',surprise:'surprised',shy:'smile',reassure:'smile',sad:'flat',shrug:'flat',greet:'smile'};
export const faceForAction=action=>faceMap[action]||'neutral';
const fold=text=>String(text||'').toLocaleLowerCase('vi').normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/đ/g,'d');

// Standing mood (face + posture) that best fits each gesture; words below can refine it.
const moodMap={sad:'sad',laugh:'happy',chuckle:'happy',celebrate:'happy',shy:'happy',reassure:'happy',greet:'happy',hipSway:'happy',think:'curious',surprise:'worried',shrug:'worried',refuse:'annoyed'};
export const LOOK_DIRECTIONS=['left','right','behind','around'];

export function performanceCommand(text){
  const t=fold(text).trim();
  // Direct user requests only; feedback, negation and questions are not poses.
  if(/[?？]/.test(t))return null;
  if(/^(?:mao[,!\s]+)?(?:(?:hay|thu|lam thu)\s+)?lam (?:dong tac|action)\s+(?:khong chiu dau|tu choi)(?:\s+(?:di|nhe|nha))*[.!\s]*$/.test(t))return 'refuse';
  if(/\b(?:khong|dung|chua|sao|manh qua|qua manh|qua cham)\b/.test(t))return null;
  if(/^(?:mao[,!\s]+)?(?:(?:hay|thu|lam thu|cho minh xem|cho toi xem)\s+)?lac hong(?:\s+(?:nhe|mot chut|1 chut|di|nhe nhe|nhe thoi|nhe nhe thoi|nha|nhe nhe di))*[.!\s]*$/.test(t))return 'hipSway';
  return null;
}

// What Mao is saying decides the gesture. Each rule reads Mao's own sentence (not the
// viewer's comment), so "Mao chỉ biết lắc hông thôi, xem nè!" sways the hips and
// "Không chịu đâu!" refuses, while feedback such as "lắc hông mạnh quá" stays a plain talk.
const NEGATED_SWAY=/\b(?:dung|khong|thoi|het|chua|ngung)\s+(?:\w+\s+)?(?:lac hong|uon eo|nhay)\b|\b(?:lac hong|nhay)\s+(?:\w+\s+)?(?:manh qua|qua manh|qua cham|nua)\b/;
const REFUSE=/\b(?:khong chiu dau|hong chiu|khong chiu|khong muon dau|khong thich dau|khong dong y dau|khong lam dau|dung ma|thoi khong|con lau|mo di|tu choi)\b|^\s*(?:khong|hong)\s+(?:dau|nha|nhe)\b|\bmao khong\s+(?:lam|nhay|hat|noi|chiu|muon)\b[^.!?]*\bdau\b/;
const NOT_REFUSE=/\bkhong sao dau|khong biet dau|khong co gi dau|khong phai lo|dung lo|dung buon/;
const DANCE=/\b(?:lac hong|uon eo)\b|\b(?:nhay|mua)\b[^.!?]{0,30}\b(?:nay|ne|nhe|nha|day|xem|thu|luon)\b/;
// Folding removes tones, so short words collide ("mà"/"ma", "đã"/"dạ", "thời gian"):
// every cue here is a phrase that stays unambiguous without diacritics.
const SCARED=/\b(?:so qua|so that|so ghe|so het hon|giat minh|hu hon|con ma|co ma|doa mao|dung doa|ui da)\b|^\s*a+\s*[!,]/;

export function lookFor(text){
  const t=fold(text);
  if(/\b(?:sau lung|phia sau|dang sau|ben sau|o sau|sau mao)\b/.test(t))return 'behind';
  if(/\b(?:ben|phia|qua|sang|o)\s+trai\b/.test(t))return 'left';
  if(/\b(?:ben|phia|qua|sang|o)\s+phai\b/.test(t))return 'right';
  if(/\b(?:nhin quanh|dau dau|o dau (?:vay|the|ha)|ai vay|ai the|cai gi vay|tieng gi vay|tieng gi the)\b/.test(t))return 'around';
  return null;
}
function moodFor(t,action){
  if(/\b(?:buon ngu|ngap|met qua|ngu gat)\b/.test(t))return 'sleepy';
  if(/\b(?:hmph|doi roi|hon doi|gian roi|gian qua|buc minh|kho chiu)\b|^\s*hu\s*[!,.]/.test(t))return 'annoyed';
  if(/\b(?:hehe|gioi chua|tu hao|de qua|de ot|dinh cua chop)\b/.test(t))return 'smug';
  if(/\b(?:lo qua|lo lang|so qua|so that|hoi hop)\b/.test(t))return 'worried';
  if(/\b(?:to mo|hmm|thu vi|la nhi)\b|^\s*ua\b/.test(t))return 'curious';
  return moodMap[action]||'calm';
}

export function selectPerformance(text,expressions=[],motions=[]){
  const raw=String(text||''),t=fold(raw);
  const explicit=raw.match(/^\s*\[([a-z]+)\]/i),tag=explicit&&PERFORMANCE_ACTIONS.find(a=>a.toLowerCase()===explicit[1].toLowerCase());
  let action=tag||storyAction(raw);
  const look=lookFor(raw);
  // "buồn ngủ" (sleepy) is not "buồn" (sad).
  if(!tag&&action==='sad'&&/\bbuon ngu\b/.test(t)&&!/\b(?:buon qua|buon that|that vong|co don)\b/.test(t))action='talk';
  if(!tag){
    if(/^\s*(?:xin chao|chao\b|hi\b|hello\b|tam biet|bye\b|hen gap lai)/.test(t))action='greet';
    else if(SCARED.test(t)||/\blam mao so|mao so roi\b/.test(t))action='surprise';
    else if(action!=='reassure'&&!NOT_REFUSE.test(t)&&REFUSE.test(t))action='refuse';
    else if(!NEGATED_SWAY.test(t)&&DANCE.test(t))action='hipSway';
    else if(action==='talk'&&look==='around')action='turn';
    else if(action==='talk'&&/^\s*(?:dung roi|dung vay|u|vang|chuan roi|chinh xac|ok)\b/.test(t))action='nod';
  }
  // Existing desktop expression indices are shared by several emotions.
  // Content takes priority; use these only as a fallback for ordinary speech.
  let face=faceForAction(action);
  if(action==='talk'&&Array.isArray(expressions)){
    if(expressions.includes(1)){action='sad';face='flat';}
    else if(expressions.includes(2)){action='shrug';face='flat';}
    else if(expressions.includes(3))face='smile';
  }
  // Preserve the agent's gesture choice as metadata, independent of words
  // it happens to say. These tags are removed before subtitles and VieNeu.
  const chosen=Array.isArray(motions)&&motions.find(m=>['refuse','shake','squint','flat','surprised','tilt','shy','nod'].includes(m));
  if(chosen){
    const mapped={refuse:['refuse','flat'],shake:['refuse','flat'],squint:[action==='laugh'?'laugh':'chuckle','squint'],flat:['shrug','flat'],surprised:['surprise','surprised'],tilt:['think','surprised'],shy:['shy','smile'],nod:[action==='greet'?'greet':'nod','smile']}[chosen];
    [action,face]=mapped;
  }
  return {action,face,mood:moodFor(t,action),look};
}

export function planPerformanceStory(text){
  return String(text).split(/\r?\n/).map(s=>s.trim()).filter(Boolean).slice(0,40).map(line=>({
    ...selectPerformance(line),text:line.replace(/^\s*\[[a-z]+\]\s*/i,'').slice(0,600),seconds:7.6
  }));
}
