import {localAvatar} from './vendor/dicebear-avataaars.mjs';
export function countdown(end, now = Date.now() / 1000) {
  return Math.max(0, Math.ceil((Number(end) || 0) - now));
}
export function clockLabel(seconds) {
  const n = Math.max(0, Math.floor(seconds));
  return `${Math.floor(n / 3600)}:${String(Math.floor(n % 3600 / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
}
export function seatRows(state) {
  return Array.from({length: 40}, (_, i) => (state?.classroom?.daily_seats ?? state?.classroom?.seats)?.[i] || null);
}
const avatarCache=new Map();
export function avatarFallback(){
  return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="47" fill="#d9e6ca"/><circle cx="35" cy="42" r="5" fill="#576a50"/><circle cx="65" cy="42" r="5" fill="#576a50"/><path d="M30 61 Q50 79 70 61" fill="none" stroke="#576a50" stroke-width="5" stroke-linecap="round"/></svg>');
}
export function avatarUrl(seed){
  const key=String(seed||'mao-avatar').slice(0,128);
  if(avatarCache.has(key))return avatarCache.get(key);
  let url;try{url=localAvatar(key);}catch{url=avatarFallback();}
  if(avatarCache.size>=512)avatarCache.delete(avatarCache.keys().next().value);
  avatarCache.set(key,url);return url;
}
