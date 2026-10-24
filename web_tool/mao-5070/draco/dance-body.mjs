import * as T from '../3d/vendor/three.module.js';
import {PerformanceBodyActor} from './performance-motion.mjs?v=4';

const rad=T.MathUtils.degToRad,clamp=T.MathUtils.clamp;
const SIDE={L:1,R:-1};
const FORWARD=new T.Vector3(0,0,1);
const STEP=1/120;
const smoothstep=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
// Rotation that turns the frame (direction, hinge) of a bone at rest into the target
// frame. Fixing the hinge as well as the direction pins the twist about the bone.
function frameOf(direction,hinge){
  const e1=direction.clone().normalize();
  let e2=hinge.clone().addScaledVector(e1,-hinge.dot(e1));
  if(e2.lengthSq()<1e-8)e2=new T.Vector3().crossVectors(e1,Math.abs(e1.x)<.9?new T.Vector3(1,0,0):new T.Vector3(0,0,1));
  e2.normalize();
  return new T.Quaternion().setFromRotationMatrix(new T.Matrix4().makeBasis(e1,e2,new T.Vector3().crossVectors(e1,e2)));
}
const turnBetween=(rest,target)=>frameOf(target.direction,target.hinge).multiply(frameOf(rest.direction,rest.hinge).invert());
// Unit-vector slerp that tolerates opposite vectors.
function slerpVector(a,b,t){
  if(a.dot(b)<-.9999){const q=new T.Quaternion().setFromAxisAngle(new T.Vector3().crossVectors(a,Math.abs(a.x)<.9?new T.Vector3(1,0,0):new T.Vector3(0,0,1)).normalize(),Math.PI*t);return a.clone().applyQuaternion(q);}
  return a.clone().applyQuaternion(new T.Quaternion().slerp(new T.Quaternion().setFromUnitVectors(a,b),t));
}
// Hands trail the forearm by about 70 ms (a loose wrist), never more than this many
// degrees from where the forearm would hold them.
const HAND={lag:14,limit:rad(35)};
const UNIT=[-1,1];
// Reaching a wide foot goal may lower the hips, but never by more than this
// fraction of the body height.
const MAX_REACH_DROP=.12;
const PITCH_SIGN=1;
// Fastest the elbow's hinge axis may turn (radians per second).
const HINGE_SPEED=rad(600);
// Mao's clothed torso in the bind pose (model space: x to her left, y up, z forward), as
// [height, half width, front reach, back reach], measured from the sweater, shirt, tie and
// skirt vertices that follow the trunk bones. Arms are kept outside it.
const TORSO=[[.84,.150,.150,-.110],[.90,.150,.130,-.090],[.96,.125,.122,-.075],[1.02,.105,.115,-.040],
  [1.08,.088,.115,-.025],[1.14,.095,.128,-.035],[1.20,.104,.128,-.045],[1.26,.090,.090,-.050],[1.32,.070,.060,-.040]];
// Cross-sections are superellipses, between an ellipse and a rectangle.
const TORSO_SHAPE=2.5;
// The chest bone carries the torso from this height up, the pelvis below it.
const CHEST_FROM=1.02;
// Clearance kept from the torso surface: the robe sleeve around the elbow and forearm,
// the wrist cuff, the hand.
const ARM_CLEARANCE={elbow:.025,forearm:.03,wrist:.025,palm:.015,fingers:.012};
function torsoSlice(y){
  if(y<TORSO[0][0]||y>TORSO.at(-1)[0])return null;
  let i=0;while(i<TORSO.length-2&&y>TORSO[i+1][0])i++;
  const [y0,...a]=TORSO[i],[y1,...b]=TORSO[i+1],t=(y-y0)/(y1-y0);
  const [half,front,back]=a.map((v,k)=>v+(b[k]-v)*t);
  return {half,front,back};
}
// Width of the soft band around the surface (model metres): a point approaching the
// torso starts to be eased outward this far before it would touch, so an arm settles onto
// the body instead of stopping dead against it.
const TORSO_SOFT=.02;
// Moves a model-space point out of the torso (grown by `margin`), straight away from the
// torso's centre line, and returns how far it was moved (0 when it was clear). The push is
// smooth: within TORSO_SOFT of the surface it grows gradually; anywhere deeper the point
// ends up on the surface. With `move` false it only reports how far the point is inside.
export function pushOutOfTorso(point,margin,move=true){
  const s=torsoSlice(point.y);if(!s)return 0;
  const a=s.half+margin,b=(s.front-s.back)/2+margin,centre=(s.front+s.back)/2;
  const x=point.x,z=point.z-centre,r=Math.hypot(x,z);
  if(r<1e-9){if(move)point.z=centre+b+TORSO_SOFT/4;return b;}
  // Radial size of the surface in this direction, then where the point is relative to it.
  const surface=r/(((Math.abs(x)/a)**TORSO_SHAPE+(Math.abs(z)/b)**TORSO_SHAPE)**(1/TORSO_SHAPE));
  if(!move)return Math.max(0,surface-r);
  const u=(r-surface)/TORSO_SOFT;
  if(u>=1)return 0;
  // Smooth (C1) map: u in [-1,1] -> surface + soft*(u+1)²/4, deeper -> the surface.
  const target=surface+TORSO_SOFT*(u>-1?(u+1)**2/4:0),scale=target/r;
  point.x=x*scale;point.z=centre+z*scale;
  return target-r;
}
// How deep a world point is inside Mao's torso (for checks and tests).
export function torsoDepth(actor,point,margin=0){return actor.bodyFrames().depth(point.clone(),margin,false);}

// Robe flaps and the wide sleeves (cuff chains) while dancing: stiffer, more damped, a
// narrower swing cone, and sleeves that weigh less, so a forearm held across the chest
// is not hidden behind a sleeve hanging from it like a curtain (idle values: coat
// 14/14/.18/1.6, cuff 20/14/.30/3.0 for stiffness/drag/limit/gravity, see secondary.mjs).
// Measured over the whole white-top dance, median swing relative to the parent bone drops from
// 363 to about 40 °/s for the sleeves and from 65 to 21 °/s for the flaps. Stiffness stays at
// or below 100: the cloth step pulls (stiffness/120)² of the gap per step, and near 1 it overshoots.
export const GARMENT={coat:{stiffness:40,drag:40,limit:.05,gravity:1.6},cuff:{stiffness:100,drag:80,limit:.04,gravity:1.5}};

// Choreography is data: one row per sample at `fps`, one number per column.
// Sides are the dancer's own right/left (R is on the viewer's left in a front
// view). Directions are in the body's frame: x toward the dancer's left, y up,
// z forward (toward the audience). Distances are fractions of the body height.
//   RuX RuY RuZ  direction of the right upper arm (shoulder → elbow); the
//   RfX RfY RfZ  right forearm (elbow → wrist); then Lu*, Lf* for the left arm.
//                Vectors, not angles, so an arm pointing at the camera has no
//                singular pose. They are normalised when sampled.
//   roll yaw     trunk lean toward the dancer's left / twist toward the left (degrees)
//   turn pitch   whole body turned toward the dancer's left / trunk leaning forward (degrees)
//   hip drop     pelvis shift toward the dancer's left / knees bent (hips lower)
//   Lx Rx        how far each foot stands from the body's centre line
//   Ly Ry Lz Rz  foot lift and forward reach (a lifted or crossing foot)
// name: [min, max, default]; a default of null means "leave the rig as it is".
const ARM_COLUMNS=['R','L'].flatMap(side=>['u','f'].flatMap(part=>['X','Y','Z'].map(axis=>side+part+axis)));
export const COLUMNS={
  ...Object.fromEntries(ARM_COLUMNS.map(name=>[name,[...UNIT]])),
  roll:[-30,30,0],yaw:[-45,45,0],turn:[-60,60,0],pitch:[-30,30,0],hip:[-.3,.3,0],drop:[-.1,.3,0],
  Lx:[-.5,.5,null],Ly:[-.1,.5,0],Lz:[-.5,.5,0],
  Rx:[-.5,.5,null],Ry:[-.1,.5,0],Rz:[-.5,.5,0]
};
const REQUIRED=ARM_COLUMNS;

export function validateDance(def){
  const fail=reason=>{throw new Error(`Invalid dance: ${reason}`);};
  if(!def||typeof def!=='object')fail('not an object');
  if(!/^[a-z0-9-]{1,64}$/.test(def.id||''))fail('id');
  if(!Number.isFinite(def.bpm)||def.bpm<40||def.bpm>220)fail('bpm');
  if(!Number.isFinite(def.fps)||def.fps<1||def.fps>120)fail('fps');
  const {columns,frames}=def;
  if(!Array.isArray(columns)||new Set(columns).size!==columns.length||columns.some(name=>!Object.hasOwn(COLUMNS,name))||REQUIRED.some(name=>!columns.includes(name)))fail('columns');
  if(!Array.isArray(frames)||frames.length<2||frames.length>6000)fail('frames');
  const tracks={};
  for(const name of columns)tracks[name]=new Float64Array(frames.length);
  frames.forEach((row,r)=>{
    if(!Array.isArray(row)||row.length!==columns.length)fail(`frame ${r} length`);
    columns.forEach((name,c)=>{
      const value=row[c],[low,high]=COLUMNS[name];
      if(!Number.isFinite(value)||value<low||value>high)fail(`frame ${r} ${name}`);
      tracks[name][r]=value;
    });
  });
  for(const prefix of ARM_COLUMNS.map(name=>name.slice(0,2)).filter((p,i,all)=>all.indexOf(p)===i)){
    for(let r=0;r<frames.length;r++)if(Math.hypot(tracks[prefix+'X'][r],tracks[prefix+'Y'][r],tracks[prefix+'Z'][r])<.2)fail(`frame ${r} ${prefix} direction`);
  }
  const overlay={bounce:0,sway:0,...def.overlay};
  for(const key of ['bounce','sway'])if(!Number.isFinite(overlay[key])||Math.abs(overlay[key])>.1)fail(`overlay.${key}`);
  return Object.freeze({offset:0,loop:true,...def,overlay,tracks});
}

const catmull=(a,b,c,d,t)=>.5*(2*b+(c-a)*t+(2*a-5*b+4*c-d)*t*t+(3*b-a-3*c+d)*t*t*t);

// Pure function of choreography time, so scrubbing, replay and tests agree.
export function sampleDance(def,time){
  const count=def.frames.length,cycle=count/def.fps;
  let t=(Number.isFinite(time)?time:0)-def.offset;
  t=def.loop?((t%cycle)+cycle)%cycle:clamp(t,0,cycle-1/def.fps);
  const u=t*def.fps,i=Math.floor(u),f=u-i;
  const index=n=>def.loop?((n%count)+count)%count:clamp(n,0,count-1);
  const at=name=>{
    const [low,high,fallback]=COLUMNS[name],track=def.tracks[name];
    if(!track)return fallback;
    return clamp(catmull(track[index(i-1)],track[index(i)],track[index(i+1)],track[index(i+2)],f),low,high);
  };
  const direction=prefix=>{
    const x=at(prefix+'X'),y=at(prefix+'Y'),z=at(prefix+'Z'),length=Math.hypot(x,y,z)||1;
    return [x/length,y/length,z/length];
  };
  const foot=side=>({x:at(side+'x'),y:at(side+'y'),z:at(side+'z')});
  return {
    t,beat:t*def.bpm/60,overlay:def.overlay,
    arms:{R:{upper:direction('Ru'),fore:direction('Rf')},L:{upper:direction('Lu'),fore:direction('Lf')}},
    body:{roll:at('roll'),yaw:at('yaw'),turn:at('turn'),pitch:at('pitch'),hip:at('hip'),drop:at('drop')},
    feet:{L:foot('L'),R:foot('R')}
  };
}

// Adds a choreography layer over the shared body solver: arms are aimed along the
// sampled directions, the trunk leans and the hips shift and drop, and the feet
// stand, lift and cross. Face, hair, cloth and skirt clearance keep running
// underneath; the layer fades out when the dance stops.
export class DanceBodyActor extends PerformanceBodyActor{
  constructor(asset){
    super(asset);
    this.dance=null;this.danceAmount=0;this.danceClock=0;this.dancePose=null;this.danceScale=new T.Vector3();this.danceScratch=new T.Vector3();
    // The elbow is a hinge. At rest it bends the forearm forward, about an axis across
    // the arm; the same axis, carried along with the arm, is used when it is straight.
    this.restHinge=Object.fromEntries(['L','R'].map(side=>[side,new T.Vector3().crossVectors(this.arms[side].upper,FORWARD).normalize()]));
    this.danceHinge={L:null,R:null};this.handLag={L:null,R:null};
    // Keep the arms outside the torso (see keepArmOutOfBody).
    this.armCollision=true;
  }
  get bodyHeight(){return this.dynamics.unit*1.45;}
  // `time` is where the music is (seconds). A live source such as audio.currentTime
  // is reported in coarse, uneven steps, so a live dance coasts on its own clock and
  // is only nudged toward the reported time; a jump of a quarter second or more
  // (a seek) resynchronises at once. Without `live` the time is followed exactly.
  setDance(def,time=0,bpm=def.bpm,{live=false}={}){
    const speed=Number.isFinite(bpm)&&bpm>0?clamp(bpm/def.bpm,.75,1.35):1;
    const target=Number.isFinite(time)?Math.max(0,time):0;
    const continuing=this.dance?.def===def;
    this.dance={def,time:target,speed,live};
    if(!continuing||!live)this.danceClock=target;
    if(!continuing&&!this.danceAmount){this.danceHinge={L:null,R:null};this.handLag={L:null,R:null};}
  }
  clearDance(){this.dance=null;}
  get dancing(){return this.danceAmount>0;}
  step(dt){
    this.danceAmount+=((this.dance?1:0)-this.danceAmount)*(1-Math.exp(-5*dt));
    if(!this.dance&&this.danceAmount<.002)this.danceAmount=0;
    if(this.dance){
      const {live,time}=this.dance;
      if(live){
        const error=time-this.danceClock;
        if(Math.abs(error)>.25)this.danceClock=time;
        else this.danceClock+=dt+error*(1-Math.exp(-5*dt));
      }else this.danceClock=time;
      this.dancePose=sampleDance(this.dance.def,this.danceClock*this.dance.speed);
    }
    super.step(dt);
  }
  reachArm(side,profile,amount){
    const k=this.danceAmount;
    if(!k||!this.dancePose)return super.reachArm(side,profile,amount);
    if(side==='L')this.applyDanceBody(this.dancePose,k);
    this.aimDanceArm(side,this.dancePose.arms[side],k);
  }
  applyDanceBody(pose,k){
    const bh=this.bodyHeight,waist=this.joints.waist,{hip,drop,roll,yaw,turn,pitch}=pose.body,{bounce,sway}=pose.overlay;
    const beat=.5-.5*Math.cos(pose.beat*Math.PI*2);
    waist.parent.getWorldScale(this.danceScale);
    waist.position.x+=(hip+sway*Math.sin(pose.beat*Math.PI))*bh*k/this.danceScale.x;
    waist.position.y-=(drop+bounce*beat)*bh*k/this.danceScale.y;
    // Raising an arm lifts the shoulder girdle a little; the left clavicle turns +z, the right -z.
    const lift=side=>{const x=clamp((pose.arms[side].upper[1]+.2)/.9,0,1);return rad(9)*x*x*(3-2*x);};
    // Positive roll leans toward the dancer's left (+x), which is a negative turn about z.
    // Turn swings the waist (pelvis and trunk) about the vertical; the feet keep
    // their own goals, so the legs follow by IK. Pitch tips the spine and chest forward
    // (+x turns the up axis toward +z) while the head keeps most of its gaze level.
    const lean=rad(PITCH_SIGN*pitch);
    const turns={waist:[0,rad(turn),0],spine:[lean*.5,rad(yaw)*.5,-rad(roll)*.5],chest:[lean*.5,rad(yaw)*.5,-rad(roll)*.5],head:[-lean*.35,0,rad(roll)*.25],
      clavicleL:[0,0,lift('L')],clavicleR:[0,0,-lift('R')]};
    const delta=new T.Quaternion(),euler=new T.Euler();
    for(const [name,xyz] of Object.entries(turns)){
      const bone=this.joints[name],rest=this.rest.get(bone);
      delta.setFromEuler(euler.set(xyz[0]*k,xyz[1]*k,xyz[2]*k));
      bone.quaternion.multiply(rest.worldInverse.clone().multiply(delta).multiply(rest.world));
    }
    this.asset.updateMatrixWorld(true);
  }
  // Maps world points into the torso's bind pose (model space) through the chest bone
  // for the upper torso and the pelvis below it, so the torso shape leans, twists and
  // turns with the body. Built from the current pose; `depth` optionally moves the point
  // back out in place.
  bodyFrames(){
    this.asset.updateMatrixWorld(true);
    if(!this.torsoRest){
      const inverse=this.asset.matrixWorld.clone().invert();
      this.torsoRest=['chest','pelvis'].map(name=>{
        const bone=this.joints[name],rest=this.rest.get(bone);
        return {bone,model:inverse.clone().multiply(new T.Matrix4().compose(rest.worldPosition,rest.world,bone.getWorldScale(new T.Vector3())))};
      });
    }
    const frames=this.torsoRest.map(({bone,model})=>{const toModel=model.clone().multiply(bone.matrixWorld.clone().invert());return {toModel,toWorld:toModel.clone().invert()};});
    return {depth(point,margin,move=true){
      for(const [i,frame] of frames.entries()){
        const local=point.clone().applyMatrix4(frame.toModel);
        if(i===0&&local.y<CHEST_FROM)continue;
        const depth=pushOutOfTorso(local,margin,move);
        if(depth>0&&move)point.copy(local.applyMatrix4(frame.toWorld));
        return depth;
      }
      return 0;
    }};
  }
  // Choreography measured from a video (or keyed by hand) can put a forearm across the
  // chest a little too deep, or a hand on the hip inside it. Before the arm is posed, its
  // elbow, forearm, wrist and hand are checked against the torso and any point inside is
  // moved out to the surface (plus clearance for sleeve and hand), and the upper arm and
  // forearm are re-aimed through the moved points. Directions are changed in place.
  keepArmOutOfBody(side,upperDirection,foreDirection){
    if(!this.armCollision)return false;
    const body=this.bodyFrames(),shoulder=this.joints['upper'+side].getWorldPosition(new T.Vector3());
    this.armLengths??={};
    if(!this.armLengths[side]){
      const at=bone=>this.rest.get(bone).worldPosition,u=this.joints['upper'+side],e=this.joints['elbow'+side],w=this.joints['wrist'+side];
      // Hand: wrist to the middle knuckle and on to the fingertips (about 1.8 times).
      const middle=this.fingers?.[side]?.[2]?.[0];
      this.armLengths[side]={upper:at(e).distanceTo(at(u)),fore:at(w).distanceTo(at(e)),hand:middle?at(middle).distanceTo(at(w))*1.8:at(w).distanceTo(at(e))*.7};
    }
    const lengths=this.armLengths[side];
    const elbow=new T.Vector3(),point=new T.Vector3();
    let moved=false;
    for(let pass=0;pass<3;pass++){
      elbow.copy(shoulder).addScaledVector(upperDirection,lengths.upper);
      if(body.depth(elbow,ARM_CLEARANCE.elbow)>0){upperDirection.copy(elbow).sub(shoulder).normalize();moved=true;}
      let changed=false;
      for(const [along,clearance] of [[lengths.fore*.5,ARM_CLEARANCE.forearm],[lengths.fore,ARM_CLEARANCE.wrist],[lengths.fore+lengths.hand*.5,ARM_CLEARANCE.palm],[lengths.fore+lengths.hand,ARM_CLEARANCE.fingers]]){
        point.copy(elbow).addScaledVector(foreDirection,along);
        if(body.depth(point,clearance)>0){foreDirection.copy(point).sub(elbow).normalize();changed=moved=true;}
      }
      if(!changed)break;
    }
    return moved;
  }
  // The upper arm and forearm are posed as a shoulder + hinge, not as two free
  // directions: the elbow axis is the one that bends the upper-arm direction into the
  // forearm direction, so the upper arm twists the way a real arm does and the forearm
  // never spins about itself. Aiming each bone by the shortest turn from rest instead
  // invents a twist that flips as the arm moves (the "stuck", snapping look).
  hingeFor(side,upperDirection,foreDirection){
    const arm=this.arms[side];
    const carried=this.restHinge[side].clone().applyQuaternion(new T.Quaternion().setFromUnitVectors(arm.upper,upperDirection));
    const bentAxis=new T.Vector3().crossVectors(upperDirection,foreDirection);
    const previous=this.danceHinge[side];
    let hinge=carried.normalize();
    if(bentAxis.lengthSq()>1e-10){
      // The bend axis has two signs. Keep the one that agrees with the last frame: a
      // nearly straight arm measured a hair "backwards" must read as a slight
      // overextension, not as a reason to twist the whole upper arm round.
      bentAxis.normalize();
      if(bentAxis.dot(previous||carried)<0)bentAxis.negate();
      // A nearly straight arm has no meaningful bend axis: blend toward it from 4° to 22°.
      const bendDegrees=T.MathUtils.radToDeg(Math.atan2(new T.Vector3().crossVectors(upperDirection,foreDirection).length(),upperDirection.dot(foreDirection)));
      hinge=slerpVector(hinge,bentAxis,smoothstep((bendDegrees-4)/18));
    }
    // Keep the axis continuous in time: a change of more than ~40 ms is eased in, and the
    // axis never turns faster than a forearm can roll (a fast throw through a straight
    // arm would otherwise spin it); the forearm's direction is unaffected.
    if(previous){
      hinge=slerpVector(previous,hinge,1-Math.exp(-25*STEP));
      const turn=previous.angleTo(hinge),most=HINGE_SPEED*STEP;
      if(turn>most)hinge=slerpVector(previous,hinge,most/turn);
    }
    hinge.addScaledVector(upperDirection,-hinge.dot(upperDirection)).normalize();
    this.danceHinge[side]=hinge.clone();
    return hinge;
  }
  aimDanceArm(side,{upper:upperVector,fore:foreVector},k){
    const arm=this.arms[side],upper=this.joints['upper'+side],elbow=this.joints['elbow'+side],wrist=this.joints['wrist'+side],chest=this.joints.chest;
    this.asset.updateMatrixWorld(true);
    const follow=chest.getWorldQuaternion(new T.Quaternion()).multiply(this.rest.get(chest).worldInverse);
    const upperDirection=new T.Vector3(...upperVector).applyQuaternion(follow).normalize();
    const foreDirection=new T.Vector3(...foreVector).applyQuaternion(follow).normalize();
    this.keepArmOutOfBody(side,upperDirection,foreDirection);
    const hinge=this.hingeFor(side,upperDirection,foreDirection);
    const restHinge=this.restHinge[side];
    const upperWorld=turnBetween({direction:arm.upper,hinge:restHinge},{direction:upperDirection,hinge})
      .multiply(this.rest.get(upper).world);
    const foreWorld=turnBetween({direction:arm.lower,hinge:restHinge},{direction:foreDirection,hinge})
      .multiply(this.rest.get(elbow).world);
    const before=[upper,elbow].map(b=>b.quaternion.clone());
    upper.quaternion.copy(upper.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(upperWorld);upper.updateWorldMatrix(false,true);
    elbow.quaternion.copy(elbow.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(foreWorld);elbow.updateWorldMatrix(false,true);
    [upper,elbow].forEach((bone,i)=>{const result=bone.quaternion.clone();bone.quaternion.copy(before[i]).slerp(result,clamp(k,0,1));});
    this.asset.updateMatrixWorld(true);
    this.followThroughHand(side,wrist,k);
  }
  // The hand trails the forearm (exponential lag): a loose wrist rather than a hand
  // welded to the forearm.
  followThroughHand(side,wrist,k){
    wrist.updateWorldMatrix(true,false);
    const held=wrist.getWorldQuaternion(new T.Quaternion());
    const state=this.handLag[side]||(this.handLag[side]=held.clone());
    state.slerp(held,1-Math.exp(-HAND.lag*STEP));
    const gap=state.angleTo(held);
    // Pull the trailing hand back to the limit along the same arc (no snap to the forearm).
    if(gap>HAND.limit)state.copy(held.clone().slerp(state,HAND.limit/gap));
    const shown=held.clone().slerp(state,clamp(k,0,1));
    wrist.quaternion.copy(wrist.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiply(shown);
    wrist.updateWorldMatrix(false,true);
  }
  // A wide or lifted foot goal can be farther than the legs reach: sink the hips
  // just enough (bent knees), up to a limit, so the foot lands where it should.
  lowerForReach(goals,bh){
    this.asset.updateMatrixWorld(true);
    let need=0;
    for(const side of ['L','R']){
      const hip=this.joints['thigh'+side].getWorldPosition(this.danceScratch),leg=this.legs[side],goal=goals[side];
      const reach=leg.a+leg.b-.002,horizontal=Math.hypot(hip.x-goal.x,hip.z-goal.z);
      need=Math.max(need,(hip.y-goal.y)-Math.sqrt(Math.max(0,reach*reach-horizontal*horizontal)));
    }
    const drop=clamp(need,0,MAX_REACH_DROP*bh);
    if(drop<1e-5)return;
    const waist=this.joints.waist;waist.parent.getWorldScale(this.danceScale);
    waist.position.y-=drop/this.danceScale.y;this.asset.updateMatrixWorld(true);
  }
  // Dancing turns, kicks and throws would fling the robe's flaps and loose cuffs wide
  // over the arms; while the dance layer is on they are held stiffer and damped
  // harder (blended by the dance amount, so idle motion keeps its looser cloth).
  settleGarment(k){
    this.danceGarment??=this.dynamics.segments.filter(s=>GARMENT[s.type])
      .map(segment=>({segment,stiffness:segment.stiffness,drag:segment.drag,limit:segment.limit,gravity:segment.gravity}));
    for(const base of this.danceGarment){
      const s=base.segment,to=GARMENT[s.type];
      // The performance layer may already have set coat values this frame; dance wins.
      const from=s.type==='coat'?{stiffness:s.stiffness,drag:s.drag,limit:s.limit,gravity:base.gravity}:base;
      s.stiffness=T.MathUtils.lerp(from.stiffness,to.stiffness,k);
      s.drag=T.MathUtils.lerp(from.drag,to.drag,k);
      s.limit=T.MathUtils.lerp(from.limit,to.limit,k);
      s.gravity=T.MathUtils.lerp(from.gravity,to.gravity,k);
    }
  }
  solveFeet(){
    const k=this.danceAmount,pose=this.dancePose;
    // The cloth step runs right after this; the performance layer sets coat values
    // inside super.solveFeet(), so the dance settling is applied last.
    try{this.solveDanceFeet(k,pose);}finally{this.settleGarment(k&&pose?k:0);}
  }
  solveDanceFeet(k,pose){
    if(!k||!pose)return super.solveFeet();
    const bh=this.bodyHeight,goals=this.locomotion?.feet||this.feet,saved={L:goals.L.clone(),R:goals.R.clone()};
    const centre=(goals.L.x+goals.R.x)/2;
    try{
      for(const side of ['L','R']){
        const foot=pose.feet[side],target=goals[side].clone();
        if(foot.x!==null)target.x=centre+SIDE[side]*foot.x*bh;
        target.y+=foot.y*bh;target.z+=foot.z*bh;
        goals[side].lerp(target,clamp(k,0,1));
      }
      this.lowerForReach(goals,bh);
      super.solveFeet();
    }finally{goals.L.copy(saved.L);goals.R.copy(saved.R);}
  }
}
