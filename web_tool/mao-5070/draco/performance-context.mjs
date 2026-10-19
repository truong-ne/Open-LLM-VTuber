import {storyAction} from './actions.mjs';
import {PERFORMANCE_ACTIONS} from './performance-motion.mjs?v=1';

const faceMap={hipSway:'smile',refuse:'flat',laugh:'squint',chuckle:'squint',celebrate:'squint',surprise:'surprised',shy:'smile',reassure:'smile',sad:'flat',shrug:'flat',greet:'smile'};
export const faceForAction=action=>faceMap[action]||'neutral';
const fold=text=>String(text||'').toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');

export function performanceCommand(text){
  const t=fold(text).trim();
  // Direct user requests only; feedback, negation and questions are not poses.
  if(/[?？]/.test(t))return null;
  if(/^(?:mao[,!\s]+)?(?:(?:hay|thu|lam thu)\s+)?lam (?:dong tac|action)\s+(?:khong chiu dau|tu choi)(?:\s+(?:di|nhe|nha))*[.!\s]*$/.test(t))return 'refuse';
  if(/\b(?:khong|dung|chua|sao|manh qua|qua manh|qua cham)\b/.test(t))return null;
  if(/^(?:mao[,!\s]+)?(?:(?:hay|thu|lam thu|cho minh xem|cho toi xem)\s+)?lac hong(?:\s+(?:nhe|mot chut|1 chut|di|nhe nhe|nhe thoi|nhe nhe thoi|nha|nhe nhe di))*[.!\s]*$/.test(t))return 'hipSway';
  return null;
}

export function selectPerformance(text,expressions=[],motions=[]){
  const raw=String(text||''),t=fold(raw);
  const explicit=raw.match(/^\s*\[([a-z]+)\]/i),tag=explicit&&PERFORMANCE_ACTIONS.find(a=>a.toLowerCase()===explicit[1].toLowerCase());
  let action=tag||storyAction(raw);
  if(!tag){
    if(/^\s*(?:xin chao|chao\b|hi\b|hello\b)/.test(t))action='greet';
    else if(/\b(?:khong chiu dau|khong dong y dau|khong muon dau)\b/.test(t))action='refuse';
    else if(/^\s*(?:mao|minh)\s+(?:se|thu)\s+lac hong\b/.test(t))action='hipSway';
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
  return {action,face};
}

export function planPerformanceStory(text){
  return String(text).split(/\r?\n/).map(s=>s.trim()).filter(Boolean).slice(0,40).map(line=>({
    ...selectPerformance(line),text:line.replace(/^\s*\[[a-z]+\]\s*/i,'').slice(0,600),seconds:7.6
  }));
}
