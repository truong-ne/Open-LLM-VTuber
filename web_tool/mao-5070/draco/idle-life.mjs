// Procedural "alive" idle for Mao. Pure maths, no three.js: every output is a
// small, bounded offset (radians, or a unit weight) that the body/face rigs add
// on top of their own pose. Nothing here loops: each channel picks its own
// random targets and durations, so the pattern never repeats mechanically.
//
// Principles (see doc/mao_idle_animation.vi.md):
//  - breathing: slow, inhale shorter than exhale, an occasional deeper sigh
//  - weight shift: hips slide, shoulders counter-tilt (contrapposto), head stays level
//  - gaze: eyes jump first (saccade), the head follows ~150 ms later, then eyes recentre
//  - micro sway: sum of slow, unsynchronised wanderers instead of a single sine
//  - head events: now and then a small tilt, nod or short shake
//  - speaking: beat nods on loudness onsets, fewer glances away
//  - listening: slow nods and a gentle head tilt
//  - blinks: random interval, sometimes double, often paired with a big gaze shift
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const lerp=(a,b,t)=>a+(b-a)*t;
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};

export function makeRandom(seed=1){
  let s=(seed>>>0)||1;
  return()=>{s=(s+0x6D2B79F5)>>>0;let t=s;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return((t^t>>>14)>>>0)/4294967296;};
}

// Every number a designer may want to adjust. Angles are radians.
export const IDLE_TUNING={
  breathHz:.26,            // breaths per second (15 per minute)
  breathChest:.011,        // chest pitch at full inhale
  breathShoulder:.008,     // shoulder lift at full inhale
  sighEvery:[28,55],       // seconds between deeper breaths
  shiftEvery:[7,15],       // seconds between weight shifts
  shiftTime:[1.6,2.6],     // duration of one weight shift
  shiftHip:.014,           // sideways hip travel (rig units)
  swayBody:1.5,            // scale of the slow body wander
  swayHead:1,              // scale of the micro head wander
  gazeHold:[2.2,5.2],      // seconds between gaze targets while facing the audience
  glanceYaw:[.12,.32],     // size of a glance away
  headShare:.68,           // share of a gaze shift taken by the head (eyes take the rest)
  eventEvery:[8,20],       // seconds between head tilt / nod / shake
  beatNod:.045,            // speech beat nod
  listenTilt:.045,
  blinkEvery:[2.6,6.4],
  doubleBlink:.16
};

// A smoothed random walk: picks a new random target every `period` seconds
// (+-40%) and follows it with a critically damped spring, so it eases in and out.
class Wander{
  constructor(rand,period,range=1){this.rand=rand;this.period=period;this.range=range;this.x=0;this.v=0;this.target=0;this.left=rand()*period;}
  step(dt){
    this.left-=dt;
    if(this.left<=0){this.target=(this.rand()+this.rand()-1)*this.range;this.left=this.period*(.6+.8*this.rand());}
    const w=Math.PI*1.6/this.period;
    this.v+=(w*w*(this.target-this.x)-2*w*this.v)*dt;this.x+=this.v*dt;return this.x;
  }
}

// Face/posture moods layered on the base expression. smile (-0.45..1), brow (-1..1; up is +),
// lid = how far the eyelids hang (0..0.6), pitch/roll = small head bias in radians.
export const MOODS={
  calm:{smile:.10,brow:0,lid:.03,pitch:0,roll:0},
  happy:{smile:.65,brow:.20,lid:.04,pitch:-.01,roll:.02},
  sad:{smile:-.35,brow:.35,lid:.26,pitch:.07,roll:.03},
  worried:{smile:-.15,brow:.50,lid:.04,pitch:.02,roll:.03},
  annoyed:{smile:-.25,brow:-.70,lid:.20,pitch:.02,roll:0},
  curious:{smile:.20,brow:.50,lid:0,pitch:-.01,roll:.05},
  sleepy:{smile:.15,brow:-.15,lid:.45,pitch:.04,roll:.02},
  smug:{smile:.45,brow:-.10,lid:.20,pitch:-.03,roll:-.02}
};

export class IdleLife{
  constructor({seed=1,tuning={}}={}){
    this.tuning={...IDLE_TUNING,...tuning};this.rand=makeRandom(seed);this.time=0;
    const r=this.rand,wander=(period,range)=>new Wander(r,period,range);
    this.w={sx:wander(6.5,1),sy:wander(5.3,1),sz:wander(7.9,1),hx:wander(3.9,1),hy:wander(4.7,1),hz:wander(5.6,1),arm:wander(4.2,1)};
    this.phase=0;this.breath=0;this.sighIn=this.between(this.tuning.sighEvery);this.sighing=false;
    this.shift=0;this.shiftFrom=0;this.shiftTo=0;this.shiftT=1;this.shiftDur=2;this.shiftIn=this.between([3,6]);
    this.gaze={yaw:0,pitch:0,away:false,left:1.2};this.head={yaw:0,pitchY:0,vYaw:0,vPitch:0,pitch:0};
    this.eye={yaw:0,pitch:0};this.jitter={yaw:0,pitch:0,tYaw:0,tPitch:0,left:.6};
    this.shiftSerial=0;this.lastShift=0;this.shiftBlink=false;
    this.event=null;this.eventIn=this.between([4,9]);
    this.speaking=0;this.listening=0;this.fast=0;this.slow=0;this.beat=null;this.beatCool=0;this.listenIn=2;this.listenSide=1;this.tilt=0;
    Object.assign(this.w,{bw:wander(2.8,1),sm:wander(6.1,1),wl:wander(3.3,1),wr:wander(3.7,1),
      al:wander(4.6,1),ar:wander(5.2,1),el:wander(3.9,1),er:wander(4.4,1),fl:wander(3.1,1),fr:wander(3.5,1),
      yl:wander(5.8,1),yr:wander(6.6,1),sh:wander(4.9,1),tw:wander(7.3,1)});
    // Limbs: a soft arm re-position now and then, and a toe tap / pivot of the unloaded foot.
    this.armEvent=null;this.armIn=this.between([6,13]);this.tap=null;this.tapIn=this.between([5,12]);
    // Face mood (smile/brow/lid + a small head bias), eased toward a target.
    this.mood={...MOODS.calm};this.moodTarget={...MOODS.calm};this.browKick=0;this.thought=0;
    // Speech structure: hand beats, pauses (blink), onsets (thinking glance).
    this.hand=null;this.silent=0;this.loud=false;this.wasSpeaking=false;this.pauseSerial=0;this.pauseBlink=false;this.quiet=3;
    this.mix={body:1,look:1,breath:1,face:1};this.out=this.zero();
  }
  // Mood = a named preset blended with calm by `strength` (0..1); changes ease in over ~1 s.
  // setMood = the standing mood (operator/AI). gestureMood = a short emotional gesture that
  // temporarily takes over while it is strong, then hands back to the standing mood.
  setMood(name='calm',strength=1){this.baseMood=[MOODS[name]?name:'calm',clamp(Number.isFinite(strength)?strength:1,0,1)];this.applyMood();}
  gestureMood(name,strength){this.gesture=strength>.25&&MOODS[name]?[name,clamp(strength,0,1)]:null;this.applyMood();}
  applyMood(){
    const [name,s]=this.gesture||this.baseMood||['calm',1],m=MOODS[name];
    for(const k of Object.keys(MOODS.calm))this.moodTarget[k]=lerp(MOODS.calm[k],m[k],s);
  }
  // Turn to look somewhere on cue: 'left'/'right' (Mao's own sides), 'behind' (over the
  // shoulder, the trunk joins in), or 'around' (one side, then the other). Brows lift.
  lookToward(direction='around'){
    const r=this.rand,side=direction==='left'?1:direction==='right'?-1:(r()<.5?1:-1);
    const steps={left:[[.62,-.03,1.7]],right:[[-.62,-.03,1.7]],behind:[[side*1.35,-.02,1.6]],around:[[side*.6,-.04,1.0],[-side*.6,-.04,1.0]]}[direction];
    if(!steps)return false;
    this.lookSeq=[...steps,[0,.02,.6]].map(([yaw,pitch,hold])=>({yaw,pitch,hold}));this.lookLeft=0;
    this.browKick=Math.max(this.browKick,.45);this.thought=Math.max(this.thought,.6);this.event=null;
    return true;
  }
  get looking(){return !!this.lookSeq;}
  between([a,b]){return a+(b-a)*this.rand();}
  zero(){
    const v=()=>[0,0,0];
    return{waistX:0,waistY:0,waistZ:0,pelvis:v(),spine:v(),chest:v(),neck:v(),head:v(),clavicleL:v(),clavicleR:v(),upperL:v(),upperR:v(),elbowL:v(),elbowR:v(),wristL:v(),wristR:v(),eye:{yaw:0,pitch:0},face:{brow:0,lid:0,smile:0},finger:{L:0,R:0},foot:{L:{yaw:0,pitch:0},R:{yaw:0,pitch:0}}};
  }
  // Interval until the next blink; callers (the face rig) own the blink pose.
  blinkInterval(){const t=this.tuning;return this.rand()<t.doubleBlink?.6+.2*this.rand():this.between(t.blinkEvery)*(1-.18*this.speaking);}
  // `mix` fades each layer (body sway / look / breath) 0..1, e.g. while walking or dancing.
  update(dt,{speaking=false,listening=false,energy=0,mix={body:1,look:1,breath:1,face:1}}={}){
    // Missing or non-finite layer weights fall back to 1, so one bad caller cannot poison every pose.
    const layer=v=>Number.isFinite(v)?clamp(v,0,2):1;
    this.mix={body:layer(mix.body),look:layer(mix.look),breath:layer(mix.breath),face:layer(mix.face)};
    dt=clamp(Number.isFinite(dt)?dt:0,0,.1);if(dt<=0)return this.out;
    // Sub-step so the springs stay stable even on a slow renderer.
    const n=Math.max(1,Math.ceil(dt/(1/60)));for(let i=0;i<n;i++)this.advance(dt/n,speaking,listening,clamp(Number.isFinite(energy)?energy:0,0,1));
    return this.compose();
  }
  advance(dt,speaking,listening,energy){
    const t=this.tuning,r=this.rand;this.time+=dt;
    const k=1-Math.exp(-dt*3);this.speaking+=((speaking?1:0)-this.speaking)*k;this.listening+=((listening&&!speaking?1:0)-this.listening)*k;
    for(const w of Object.values(this.w))w.step(dt);
    // Breathing: faster while speaking, asymmetric (inhale 40%, exhale 60%).
    this.phase+=dt*t.breathHz*(1+.18*this.speaking)*(1+.10*this.w.sy.x);
    if(this.phase>=1){this.phase-=1;this.sighing=false;
      this.sighIn-=1/(t.breathHz||.26);if(this.sighIn<=0){this.sighing=true;this.sighIn=this.between(t.sighEvery);}}
    const p=this.phase;this.breath=(p<.4?smooth(p/.4):1-smooth((p-.4)/.6))*(this.sighing?1.9:1);
    // Weight shift: hold, then glide to a new side over ~2 s.
    this.shiftIn-=dt;
    if(this.shiftT>=1&&this.shiftIn<=0){
      const sides=[-1,0,1].filter(v=>Math.abs(v-this.shift)>.4);this.shiftFrom=this.shift;this.shiftTo=sides[Math.floor(r()*sides.length)]*(.7+.3*r());
      this.shiftDur=this.between(t.shiftTime);this.shiftT=0;this.shiftIn=this.between(t.shiftEvery);
    }
    if(this.shiftT<1){this.shiftT=Math.min(1,this.shiftT+dt/this.shiftDur);this.shift=lerp(this.shiftFrom,this.shiftTo,smooth(this.shiftT));}
    // Gaze: choose a target, eyes lead, head follows with a spring.
    const g=this.gaze;
    // A requested look (left / right / behind / around) takes over the gaze for its steps.
    if(this.lookSeq){
      this.lookLeft-=dt;
      if(this.lookLeft<=0){
        const step=this.lookSeq.shift();
        if(step){const before=g.yaw;g.yaw=step.yaw;g.pitch=step.pitch;g.away=step.yaw!==0;g.left=step.hold+1;this.lookLeft=step.hold;
          this.lastShift=Math.abs(step.yaw-before);this.shiftSerial++;this.shiftBlink=this.lastShift>.3;}
        else{this.lookSeq=null;g.away=false;g.left=.4+.6*r();}
      }
    }
    g.left-=dt;
    if(g.left<=0){
      const awayChance=lerp(.42,.16,this.speaking)*(1-.7*this.listening);
      const before=g.yaw,beforePitch=g.pitch;
      if(g.away||r()>awayChance){g.away=false;g.yaw=(r()*2-1)*.05;g.pitch=.02+(r()*2-1)*.03;g.left=this.between(t.gazeHold)*(1+.5*this.speaking);}
      else{g.away=true;const side=r()<.5?-1:1;g.yaw=side*this.between(t.glanceYaw);g.pitch=(r()*2-1)*.11-.01;g.left=.7+1.3*r();}
      this.lastShift=Math.hypot(g.yaw-before,g.pitch-beforePitch);this.shiftSerial++;this.shiftBlink=this.lastShift>.14&&r()<.35;
    }
    const h=this.head,wn=Math.PI*2*(this.lookSeq?2.1:1.35);
    const goalYaw=g.yaw*t.headShare,goalPitch=g.pitch*t.headShare;
    h.vYaw+=(wn*wn*(goalYaw-h.yaw)-2*wn*h.vYaw)*dt;h.yaw+=h.vYaw*dt;
    h.vPitch+=(wn*wn*(goalPitch-h.pitch)-2*wn*h.vPitch)*dt;h.pitch+=h.vPitch*dt;
    // Eyes: quick saccade toward whatever the head has not yet covered, plus micro-saccades.
    const j=this.jitter;j.left-=dt;
    if(j.left<=0){j.tYaw=(r()*2-1)*.012;j.tPitch=(r()*2-1)*.008;j.left=.35+1.05*r();}
    const jk=1-Math.exp(-dt*40);j.yaw+=(j.tYaw-j.yaw)*jk;j.pitch+=(j.tPitch-j.pitch)*jk;
    const ek=1-Math.exp(-dt*32);
    this.eye.yaw+=(clamp(g.yaw-h.yaw,-.14,.14)+j.yaw-this.eye.yaw)*ek;
    this.eye.pitch+=(clamp(g.pitch-h.pitch,-.09,.09)+j.pitch-this.eye.pitch)*ek;
    // Occasional head tilt / nod / shake while idle (rarer while talking).
    this.eventIn-=dt;
    if(!this.event&&this.eventIn<=0){
      const roll=r(),kind=roll<.42?'tilt':roll<.75?'nod':'shake';
      this.event={kind,t:0,dur:{tilt:1.9,nod:1.2,shake:1.0}[kind]*(.9+.2*r()),side:r()<.5?-1:1};
      this.eventIn=this.between(t.eventEvery)*(1+.6*this.speaking)*(1-.3*this.listening);
    }
    if(this.event){this.event.t+=dt;if(this.event.t>=this.event.dur)this.event=null;}
    // Speech beats: a loudness onset gives a small nod.
    this.fast+=(energy-this.fast)*(1-Math.exp(-dt*12));this.slow+=(energy-this.slow)*(1-Math.exp(-dt*2.5));
    this.beatCool-=dt;
    if(this.speaking>.5&&this.beatCool<=0&&this.fast-this.slow>.10){this.beat={t:0,amp:.55+.45*energy,yaw:(r()*2-1)*.012};this.beatCool=.5+.3*r();}
    if(this.beat){this.beat.t+=dt;if(this.beat.t>=.42)this.beat=null;}
    // Listening: slow nods every few seconds and a gentle tilt held toward one side.
    this.listenIn-=dt;
    if(this.listening>.5&&this.listenIn<=0){this.listenIn=this.between([2.8,6]);if(!this.event)this.event={kind:'nod',t:0,dur:1.3,side:1,soft:true};if(r()<.3)this.listenSide*=-1;}
    this.tilt+=((this.listening*this.listenSide*t.listenTilt)-this.tilt)*(1-Math.exp(-dt*1.6));
    // Hand beat: a stress pulse sometimes lifts one hand (rarely both) a little, then lets it fall.
    if(this.beat&&this.beat.t<dt*1.5){
      this.browKick=Math.max(this.browKick,.30+.2*this.beat.amp);
      if(!this.hand&&r()<.7){const both=r()<.18;this.hand={t:0,dur:.65+.25*r(),amp:(.6+.4*this.beat.amp)*(both?.7:1),L:both||r()<.38,R:both||r()>=.38};}
    }
    if(this.hand){this.hand.t+=dt;if(this.hand.t>=this.hand.dur)this.hand=null;}
    this.browKick*=Math.exp(-dt*4.5);
    // Pauses: a blink after a phrase. Onsets: sometimes a short thinking glance up and aside.
    this.quiet=energy<.05?this.quiet+dt:0;
    if(energy>.12)this.loud=true;
    if(energy<.04)this.silent+=dt;else this.silent=0;
    if(speaking&&this.loud&&this.silent>.3){this.loud=false;this.pauseSerial++;this.pauseBlink=r()<.6;}
    if(speaking&&!this.wasSpeaking&&r()<.5){
      const side=r()<.5?-1:1;g.away=true;g.yaw=side*(.16+.1*r());g.pitch=-.09-.04*r();g.left=.8+.7*r();this.lastShift=.3;this.shiftSerial++;this.shiftBlink=true;this.thought=1;
    }
    this.armIn-=dt;
    if(!this.armEvent&&this.armIn<=0){this.armEvent={side:r()<.5?'L':'R',t:0,dur:1.5+.9*r(),amp:.6+.4*r()};this.armIn=this.between([6,14]);}
    if(this.armEvent){this.armEvent.t+=dt;if(this.armEvent.t>=this.armEvent.dur)this.armEvent=null;}
    this.tapIn-=dt;
    if(!this.tap&&this.tapIn<=0){const loadedLeft=this.shift>0;this.tap={side:Math.abs(this.shift)<.3?(r()<.5?'L':'R'):(loadedLeft?'R':'L'),t:0,dur:.9+.4*r()};this.tapIn=this.between([6,15]);}
    if(this.tap){this.tap.t+=dt;if(this.tap.t>=this.tap.dur)this.tap=null;}
    this.wasSpeaking=speaking;this.thought*=Math.exp(-dt*1.2);
    const mk=1-Math.exp(-dt*1.3);for(const key of Object.keys(this.mood))this.mood[key]+=(this.moodTarget[key]-this.mood[key])*mk;
  }
  eventPose(){
    const e=this.event,o={pitch:0,yaw:0,roll:0};if(!e)return o;
    const p=e.t/e.dur,env=Math.sin(Math.PI*p);
    if(e.kind==='tilt')o.roll=e.side*.06*smooth(p/.3)*(1-smooth((p-.7)/.3));
    else if(e.kind==='nod')o.pitch=(e.soft?.04:.055)*Math.max(0,Math.sin(Math.PI*4*p))*env;
    else{o.yaw=e.side*.07*Math.sin(Math.PI*2*2.2*p)*env;o.roll=-o.yaw*.25;}
    return o;
  }
  compose(){
    const t=this.tuning,w=this.w,o=this.out,b=this.breath,s=this.shift;
    const ev=this.eventPose(),beat=this.beat?Math.pow(Math.sin(Math.PI*this.beat.t/.42),2):0;
    const sw=t.swayBody,hw=t.swayHead,{body:bm,look:lk,breath:br}=this.mix;
    o.waistX=(s*t.shiftHip+w.sx.x*.003*sw)*bm;o.waistY=b*.0010*br-Math.abs(s)*.0008*bm;o.waistZ=(-s*.012-w.sz.x*.005*sw)*bm;
    o.pelvis=[0,(s*.010+w.sy.x*.007*sw)*bm,(-s*.016+w.sz.x*.004*sw)*bm];
    o.spine=[-b*.005*br+w.sx.x*.004*sw*bm,w.sy.x*.011*sw*bm,(s*.014+w.sz.x*.006*sw)*bm];
    o.chest=[-b*t.breathChest*.9*br,-w.sy.x*.008*sw*bm,(s*.010+w.sz.x*.004*sw)*bm];
    const sh=t.breathShoulder;
    o.clavicleL=[0,0,b*sh*br-s*.008*bm+w.sh.x*.014*bm];o.clavicleR=[0,0,-b*sh*br-s*.008*bm-w.sh.x*.010*bm];
    o.pelvis[1]+=w.tw.x*.016*sw*bm;o.chest[1]-=w.tw.x*.010*sw*bm;
    // Arms hang loosely: each drifts on its own, swings against the hips, lifts with the breath,
    // and now and then re-positions (soft abduction + elbow bend).
    const ae=this.armEvent,pa=ae?Math.pow(Math.sin(Math.PI*ae.t/ae.dur),2)*ae.amp:0,aL=ae?.side==='L'?pa:0,aR=ae?.side==='R'?pa:0;
    o.upperL=[(b*.008*br+w.al.x*.06+w.arm.x*.012-aL*.07)*bm,0,(w.al.x*.05-s*.022+aL*.10)*bm];
    o.upperR=[(b*.008*br+w.ar.x*.06-w.arm.x*.012-aR*.07)*bm,0,(-w.ar.x*.05-s*.022-aR*.10)*bm];
    o.elbowL=[(w.el.x*.085-aL*.16)*bm,0,(w.el.x*.03)*bm];o.elbowR=[(w.er.x*.085-aR*.16)*bm,0,(-w.er.x*.03)*bm];
    o.finger={L:(w.fl.x*.06+aL*.05)*bm,R:(w.fr.x*.06+aR*.05)*bm};
    // Feet pivot and tap around the ankle (the ankle itself stays planted); the unloaded foot moves most.
    const unL=Math.max(0,-s),unR=Math.max(0,s),tp=this.tap,tg=tp?Math.max(0,Math.sin(Math.PI*4*tp.t/tp.dur))*Math.sin(Math.PI*tp.t/tp.dur):0;
    o.foot={L:{yaw:w.yl.x*(.03+.07*unL)*bm,pitch:(tp?.side==='L'?tg*.07:0)*bm},R:{yaw:w.yr.x*(.03+.07*unR)*bm,pitch:(tp?.side==='R'?tg*.07:0)*bm}};
    // Head: gaze + micro sway + events + beats + tilt, kept level against torso roll.
    // A requested look is deliberate: it is not faded by a gesture in progress.
    const lkGaze=this.lookSeq||Math.abs(this.head.yaw)>.3?Math.max(lk,.95):lk;
    const roll=(w.hz.x*.022*hw+ev.roll+this.tilt)*lk-(o.spine[2]+o.chest[2]+o.pelvis[2])*.55;
    const pitch=(this.head.pitch+w.hx.x*.016*hw+ev.pitch+beat*(this.tuning.beatNod*(this.beat?.amp||0)))*lk;
    let yaw=this.head.yaw*lkGaze+(w.hy.x*.020*hw+ev.yaw+(this.beat?.yaw||0)*beat)*lk;
    // Beyond ~26° the neck hands the rest of the turn to the trunk (chest leads, hips follow a little).
    const excess=Math.sign(yaw)*Math.max(0,Math.abs(yaw)-.45);yaw-=excess;
    o.spine[1]+=excess*.45;o.chest[1]+=excess*.40;o.pelvis[1]+=excess*.15;
    o.neck=[pitch*.3-b*.004,yaw*.3,roll*.3];o.head=[pitch*.7,yaw*.7,roll*.7];
    o.eye.yaw=this.eye.yaw;o.eye.pitch=this.eye.pitch;
    // Hand beats and loose wrists (talking hands are rarely still).
    const hd=this.hand,hg=hd?Math.pow(Math.sin(Math.PI*hd.t/hd.dur),1.5)*hd.amp:0,talk=this.speaking*bm;
    for(const [side,sign] of [['L',1],['R',-1]]){
      const on=hd&&hd[side]?hg:0,u=o['upper'+side],e=o['elbow'+side],wr=o['wrist'+side];
      u[0]+=-.15*on*talk;u[2]+=sign*.03*on*talk;e[0]+=-.30*on*talk;
      const drift=(side==='L'?w.wl.x:w.wr.x);
      wr[0]=-.11*on*talk+drift*.05*bm;wr[1]=drift*.04*bm;wr[2]=sign*drift*.03*bm;
    }
    // Face layer: mood + small drifts + brow flash on stress + Duchenne lids + lids follow gaze down.
    const fm=this.mix.face,m=this.mood,down=Math.max(0,this.eye.pitch+this.head.pitch);
    const smile=m.smile+w.sm.x*.05;
    o.face.smile=smile*fm;
    o.face.brow=(m.brow+w.bw.x*.16+this.browKick+this.thought*.25)*fm;
    o.face.lid=clamp(m.lid+down*1.6+Math.max(0,smile)*.14,0,.6)*fm;
    for(const [k,v] of [['pitch',0],['roll',1]])o.head[v===0?0:2]+=m[k]*lk*.7;
    return o;
  }
}
