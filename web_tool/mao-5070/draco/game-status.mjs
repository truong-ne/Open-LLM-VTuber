// The backend's monotonic timer is exposed as a server-clock deadline.
export function cooldownSeconds(state,now=Date.now(),offset=0){
  const deadline=Number(state?.cooldown_ends_at);
  if(state?.phase!=='finished'||!Number.isFinite(deadline)||deadline<=0)return 0;
  return Math.max(0,Math.ceil((deadline*1000-now-offset)/1000));
}
