import {screenPhase} from './tv-screen.mjs?v=4';

// Finished snapshots remain on the backend after the result card expires.
// Use its display deadline, rather than treating every 'finished' as active.
export function sceneForGame(state,now=Date.now(),offset=0){
  return screenPhase(state,now,offset)==='idle'?'lounge':'studio';
}
