export function headingDegrees(yaw){return ((180-yaw*180/Math.PI)%360+360)%360;}
export function cardinal(yaw){return ['N','NE','E','SE','S','SW','W','NW'][Math.round(headingDegrees(yaw)/45)%8];}
export function compassAngles(yaw,cameraBearing){return {rose:cameraBearing*180/Math.PI,arrow:(cameraBearing+Math.PI-yaw)*180/Math.PI};}
export const BODY_COMMANDS=Object.freeze(['north','south','east','west','center','dj','lounge-west','lounge-east','spin']);
export function roomDestination(command,x,z){
  const fixed={center:[0,-1.65],dj:[0,-3.3],'lounge-west':[-2.7,-1.65],'lounge-east':[2.7,-1.65]};
  const delta={north:[0,-.8],south:[0,.8],east:[.8,0],west:[-.8,0]};
  if(fixed[command])return {x:fixed[command][0],z:fixed[command][1]};
  return delta[command]?{x:x+delta[command][0],z:z+delta[command][1]}:null;
}
