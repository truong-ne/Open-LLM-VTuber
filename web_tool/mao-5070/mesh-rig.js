/* Mao 5070: texture meshes with skeletal skinning. Preview-only, no websocket. */
(() => {
  'use strict';
  const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
  const smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
  const mix=(a,b,t)=>a+(b-a)*t;
  const rotate=(p,c,angle)=>{const s=Math.sin(angle),q=Math.cos(angle),x=p[0]-c[0],y=p[1]-c[1];return [c[0]+x*q-y*s,c[1]+x*s+y*q];};
  const degrees=Math.PI/180;
  // Authored, nonuniform timing: anticipation, arrival, held pose, recovery.
  const track=(time,keys)=>{
    if(time<=keys[0][0])return keys[0][1];
    for(let i=1;i<keys.length;i++)if(time<keys[i][0]){
      const [a,x]=keys[i-1],[b,y]=keys[i];return mix(x,y,smooth((time-a)/(b-a)));
    }
    return keys.at(-1)[1];
  };
  const blinkCurve=t=>t<0||t>.30?0:t<.065?smooth(t/.065):t<.10?1:1-smooth((t-.10)/.20);
  // Integrate a circular bend through the joint instead of blending two rotated
  // positions. This preserves sleeve volume and avoids LBS folding at the elbow.
  function bend(point,pivot,angle,length){
    if(Math.abs(angle)<1e-6)return point;
    const u=point[0]-pivot[0],v=point[1]-pivot[1],start=-length/2;
    if(v<=start)return point;
    const s=Math.min(v-start,length),theta=angle*s/length,radius=length/angle;
    let cx=-radius*(1-Math.cos(theta)),cy=start+radius*Math.sin(theta);
    if(v>length/2){cx-=(v-length/2)*Math.sin(angle);cy+=(v-length/2)*Math.cos(angle);}
    return [pivot[0]+cx+u*Math.cos(theta),pivot[1]+cy+u*Math.sin(theta)];
  }
  const parts=[
    {name:'legL',rect:[512,512,512,512],anchor:[763,540],position:[365,625],scale:1.04,width:.76,cols:24,rows:64,knee:690,ankle:826},
    {name:'legR',rect:[1024,512,512,512],anchor:[1288,540],position:[435,625],scale:1.04,width:.76,cols:24,rows:64,knee:690,ankle:826},
    {name:'body',rect:[512,0,512,512],anchor:[768,20],position:[400,285],scale:.85,cols:60,rows:72},
    {name:'armL',rect:[0,512,512,512],anchor:[245,566],position:[323,333],scale:.63,cols:32,rows:72,elbow:[219,780],wrist:[202,873]},
    {name:'armR',rect:[1024,0,512,512],anchor:[1280,60],position:[477,333],scale:.63,cols:32,rows:72,elbow:[1300,260],wrist:[1352,373]},
    {name:'head',rect:[0,0,512,512],anchor:[289,438],position:[400,294],scale:.46,cols:112,rows:112},
  ];
  const toWorld=(part,p)=>[part.position[0]+(p[0]-part.anchor[0])*part.scale,part.position[1]+(p[1]-part.anchor[1])*part.scale];
  class Rig {
    constructor(){this.time=0;this.accumulator=0;this.springs={};this.p={};this.action='idle';this.started=0;this.intensity=1;this.gaze=[0,0];this.seed=5070;this.nextBlink=2.8;this.blinkAt=-10;this.doubleBlink=false;this.nextLook=1.4;this.look=[0,0];this.lastBeat=-10;this.beatSide=1;this.envelope=0;}
    random(){this.seed=(Math.imul(this.seed,1664525)+1013904223)>>>0;return this.seed/4294967296;}
    play(action){if(!['idle','talk','laugh','sad','greet','curious','shy','blink','explain','nod','weight','turn'].includes(action))return false;if(action==='blink'){this.blinkAt=this.time;this.doubleBlink=false;return true;}this.blendFrom=Object.fromEntries(Object.entries(this.springs).map(([key,s])=>[key,s.target]));this.action=action;this.started=this.time;return true;}
    spring(key,target,dt,f=2.5,damping=.8){const s=this.springs[key]||={x:0,v:0};if(this.blendFrom?.[key]!==undefined && this.time-this.started<.65 && !['mouth','mouthWide','lookX','lookY'].includes(key))target=mix(this.blendFrom[key],target,smooth((this.time-this.started)/.65));s.target=target;const w=2*Math.PI*f;s.v+=(w*w*(target-s.x)-2*damping*w*s.v)*dt;s.x+=s.v*dt;return s.x;}
    step(dt,rms){
      const t=this.time+=dt,a=t-this.started,action=this.action;
      const duration=action==='sad'?7:['weight','turn','explain'].includes(action)?6:action==='laugh'?5:4.8;
      const e=smooth(a/.55)*(1-smooth((a-duration+1.35)/1.35))*this.intensity;
      const active=name=>action===name?e:0;
      const p=this.p,voice=clamp(Number.isFinite(rms)?rms*4:0);
      const laugh=active('laugh'),sad=active('sad'),greet=active('greet'),curious=active('curious'),shy=active('shy');
      const explain=active('explain'),nod=active('nod');
      const explainL=action==='explain'?track(a,[[0,0],[.5,0],[1.3,.6],[2.1,1],[2.8,.55],[3.6,.8],[4.5,.45],[6,0]]):0;
      const explainR=action==='explain'?track(a,[[0,0],[.2,-.06],[.95,1],[1.7,.85],[2.5,.45],[3.2,.6],[4.1,1],[4.8,.6],[6,0]]):0;
      const weight=action==='weight'?track(a,[[0,0],[.4,-.1],[1.3,1],[2.5,1],[3.5,-.8],[4.4,-.8],[6,0]]):0;
      const turn=action==='turn'?track(a,[[0,0],[1,1],[2.3,1],[3.4,-1],[4.4,-1],[6,0]]):0;
      // The eyes lead a glance; the head and torso follow at different rates.
      if(t>=this.nextLook){this.look=[(this.random()-.5)*1.15,(this.random()-.5)*.55];this.nextLook=t+2.2+this.random()*3.8;}
      const lookX=clamp(this.gaze[0]+this.look[0],-1,1),lookY=clamp(this.gaze[1]+this.look[1],-1,1);
      p.lookX=this.spring('lookX',lookX,dt,5.5,1);p.lookY=this.spring('lookY',lookY,dt,5,1);
      // Audio accents trigger occasional gestures, not a hand twitch per syllable.
      const previous=this.envelope;this.envelope+=(voice-this.envelope)*(1-Math.exp(-dt*(voice>this.envelope?20:5)));
      if(voice>.2 && voice-previous>.075 && t-this.lastBeat>1.3){this.lastBeat=t;this.beatSide*=-1;}
      const beat=track(t-this.lastBeat,[[0,0],[.12,-.18],[.38,1],[.62,.75],[1.25,0]]);
      const speech=this.spring('speech',this.envelope,dt,2.1,1);
      const salute=action==='greet'?track(a,[[0,0],[.22,-.065],[.75,.96],[1.02,1],[3.05,1],[3.55,.7],[4.8,0]])*this.intensity:0;
      const wave=action==='greet'?track(a,[[0,0],[.85,0],[1.14,-1],[1.49,1],[1.87,-.85],[2.26,.8],[2.64,-.55],[3.03,.35],[3.4,0],[4.8,0]]):0;
      const chuckle=laugh*(Math.exp(-(((a-1.15)/.18)**2))+.7*Math.exp(-(((a-1.64)/.22)**2))+.4*Math.exp(-(((a-2.25)/.26)**2)));
      const idle=1-.65*Math.max(greet,laugh,sad);
      // Pelvis, ribcage and head have independent orientation in a shallow 3D
      // space. A planted-foot IK solve below makes the knees support the shift.
      const stance=idle*.22*Math.sin(t*.36)+salute*.65-shy*.65+weight+explain*.4;
      p.hipX=this.spring('hipX',stance*17,dt,1.4,.95);
      p.hipRoll=this.spring('hipRoll',stance*-2.4,dt,1.55,.95);
      p.crouch=this.spring('crouch',3+Math.abs(stance)*4+sad*5+chuckle*2,dt,1.7,1);
      p.hipYaw=this.spring('hipYaw',turn*6+stance*3,dt,1.2,1);
      p.bodyYaw=this.spring('bodyYaw',turn*13+salute*-7+explain*9+shy*5+lookX*2,dt,1.65,.95);
      p.faceYaw=this.spring('faceYaw',lookX*9+turn*12-curious*8-explain*5,dt,2.3,.95);
      p.pitch=this.spring('pitch',sad*8+shy*5+nod*track(a,[[0,0],[.4,-4],[.75,9],[1.2,-2],[1.6,5],[2.1,0],[4.8,0]]),dt,2.9,.95);
      p.shift=this.spring('shift',idle*(2.5*Math.sin(t*.49)+.8*Math.sin(t*.83))+salute*2,dt,1.2);
      p.spine=this.spring('spine',idle*(.75*Math.sin(t*.49)+.3*Math.sin(t*.91)) +salute*1.8-sad*1.1+beat*.5,dt,1.65);
      p.head=this.spring('head',.65*Math.sin(t*.73)-curious*6+shy*3+lookX*2.5-salute*2+beat*.7,dt,2.1,.9);
      p.nod=this.spring('nod',salute*-1+sad*4+shy*2+chuckle*2.6+beat*1.5+lookY+explainL*1.5-explainR,dt,2.8,.9);
      p.yaw=this.spring('yaw',lookX*3-curious*1.2,dt,1.8);
      p.breath=.003*Math.sin(t*1.35)+chuckle*.003;
      p.upperL=this.spring('upperL',idle*Math.sin(t*.63)+shy*-13+salute*2+explainL*11+weight*3-(this.beatSide<0?beat*7:0),dt,2.2);
      p.upperR=this.spring('upperR',-idle*Math.sin(t*.63+.7)-salute*25-explainR*15+weight*3-(this.beatSide>0?beat*7:0),dt,2.2);
      p.elbowL=this.spring('elbowL',shy*-112+curious*-42+explainL*-72-(this.beatSide<0?beat*35:0),dt,2.2);
      p.elbowR=this.spring('elbowR',salute*-125+wave*2-explainR*80-(this.beatSide>0?beat*32:0),dt,2.6);
      p.reachL=this.spring('reachL',explainL*32+shy*18+(this.beatSide<0?beat*15:0),dt,2,1);
      p.reachR=this.spring('reachR',explainR*42+salute*20+(this.beatSide>0?beat*18:0),dt,2,1);
      p.wristL=this.spring('wristL',-p.elbowL*.08+beat*2,dt,2.1);
      p.wristR=this.spring('wristR',wave*11-p.elbowR*.08,dt,2.5);
      // Root -> tip chains: inertia outlasts the initiating head/body gesture.
      p.hair=this.spring('hair',-p.head*.38-this.springs.head.v*.10+p.spine*.35,dt,1.8,.66);
      p.hairTip=this.spring('hairTip',p.hair-this.springs.hair.v*.08,dt,1.35,.7);
      p.fringe=this.spring('fringe',p.hair*.4-this.springs.nod.v*.055,dt,2.8,.7);
      p.ribbon=this.spring('ribbon',p.hairTip*.7-this.springs.head.v*.06,dt,1.6,.62);
      p.cloth=this.spring('cloth',-p.spine*1.4-this.springs.shift.v*.4,dt,1.5,.7);
      p.hem=this.spring('hem',p.cloth-this.springs.cloth.v*.08,dt,1.15,.68);
      p.cuffL=this.spring('cuffL',-this.springs.elbowL.v*.02,dt,2,.65);
      p.cuffR=this.spring('cuffR',-this.springs.elbowR.v*.02,dt,2,.65);
      p.mouth=this.spring('mouth',Math.max(voice,chuckle*.6),dt,8,1);
      p.mouthWide=this.spring('mouthWide',speech*.4+beat*.15,dt,4.5,1);
      p.brow=this.spring('brow',curious*.7+beat*.3+greet*.2,dt,2.5);
      p.smile=this.spring('smile',laugh*.9+greet*.25-sad*.9+shy*.3,dt,2.7);
      p.sad=this.spring('sad',sad,dt,2.7);
      if(t>=this.nextBlink){this.blinkAt=t;this.doubleBlink=this.random()<.22;this.nextBlink=t+2.8+this.random()*3.6;}
      const phase=t-this.blinkAt;
      const eyelid=this.spring('eyelid',laugh*.78+sad*.12+shy*.1,dt,3.5,1);
      p.blink=Math.max(blinkCurve(phase),this.doubleBlink?blinkCurve(phase-.39):0,eyelid);
      p.blinkR=Math.max(blinkCurve(phase-.012),this.doubleBlink?blinkCurve(phase-.402):0,eyelid);
      for(const part of parts.slice(0,2))solveLeg(part,p);
      if(a>duration && action!=='idle')this.action='idle';
    }
    update(dt,rms=0){this.accumulator+=clamp(Number.isFinite(dt)?dt:0,0,.1);while(this.accumulator+1e-10>=1/240){this.step(1/240,rms);this.accumulator-=1/240;}return this.p;}
  }
  function bodySpace(point,p,depth=0){
    const w=1-smooth((point[1]-470)/160);
    const yaw=mix(p.hipYaw,p.bodyYaw,w)*degrees,x=point[0]-400;
    let q=[400+x*Math.cos(yaw)+depth*Math.sin(yaw),point[1]];
    const z=-x*Math.sin(yaw)+depth*Math.cos(yaw);
    q=rotate(q,[400,625],p.hipRoll*degrees*(1-w));
    q=rotate(q,[400,505],p.spine*degrees*w);
    return [q[0]+p.hipX+p.shift*w,q[1]+p.crouch,z];
  }
  function project(q){const k=1500/(1500-q[2]);return [400+(q[0]-400)*k,625+(q[1]-625)*k];}
  const torso=(point,p,depth=0)=>project(bodySpace(point,p,depth));
  function solveLeg(part,p){
    const side=part.name.at(-1),h=bodySpace(part.position,p);
    const foot=[part.position[0],part.position[1]+(part.ankle-part.anchor[1])*part.scale,0];
    const l1=(part.knee-part.anchor[1])*part.scale,l2=(part.ankle-part.knee)*part.scale;
    const d=foot.map((v,i)=>v-h[i]),distance=Math.hypot(...d),n=d.map(v=>v/distance);
    const reach=Math.min(distance,l1+l2-.001);
    const along=(l1*l1-l2*l2+reach*reach)/(2*reach),height=Math.sqrt(Math.max(0,l1*l1-along*along));
    // Knees point forward in depth, rather than bending sideways like rubber.
    const pole=[-n[0]*n[2],-n[1]*n[2],1-n[2]*n[2]],length=Math.hypot(...pole);
    const knee=h.map((v,i)=>v+n[i]*along+pole[i]/length*height);
    for(let i=0;i<3;i++){p[`hip${side}${i}`]=h[i];p[`knee${side}${i}`]=knee[i];}
  }
  function legCenter(part,y,p){
    const side=part.name.at(-1),h=[0,1,2].map(i=>p[`hip${side}${i}`]),k=[0,1,2].map(i=>p[`knee${side}${i}`]);
    const foot=[part.position[0],part.position[1]+(part.ankle-part.anchor[1])*part.scale,0];
    const lower=y>part.knee,span=lower?part.ankle-part.knee:part.knee-part.anchor[1];
    const t=clamp((y-(lower?part.knee:part.anchor[1]))/span),t2=t*t,t3=t2*t;
    const a=lower?k:h,b=lower?foot:k;
    const middle=foot.map((v,i)=>(v-h[i])/(part.ankle-part.anchor[1]));
    const ta=lower?middle:k.map((v,i)=>(v-h[i])/(part.knee-part.anchor[1]));
    const tb=lower?[0,part.scale,0]:middle;
    return a.map((v,i)=>(2*t3-3*t2+1)*v+(t3-2*t2+t)*ta[i]*span+(-2*t3+3*t2)*b[i]+(t3-t2)*tb[i]*span);
  }
  function headDeform(source,p){
    let [x,y]=source;
    // Local eye meshes collapse toward the sloped eyelash axis, keeping cheeks
    // and the hair outside the eyelid patch unchanged. No texture replacement.
    for(const eye of [[220,274,41,31],[338,259,43,32]]){
      const [cx,cy,rx,ry]=eye;
      const wx=1-smooth((Math.abs(x-cx)-rx*.65)/(rx*.35));
      const dy=y-(cy-(x-cx)*.13);
      const wy=1-smooth((Math.abs(dy)-ry*.4)/(ry*.6));
      const closed=cx>280?p.blinkR:p.blink;
      y-=dy*closed*.97*wx*wy;
      const pupil=(1-smooth(Math.abs(x-cx)/26))*(1-smooth(Math.abs(dy)/23));
      x+=p.lookX*3*pupil*(1-closed);y+=p.lookY*2*pupil*(1-closed);
    }
    const mx=288,my=341;
    const wx=1-smooth((Math.abs(x-mx)-31)/18);
    const wy=1-smooth((Math.abs(y-my)-13)/25);
    const openness=.09+.91*clamp(p.mouth);
    y=mix(y,my+(y-my)*openness,wx*wy);
    y+=p.smile*3.8*wx*wy*(1-2*clamp(Math.abs(x-mx)/37));
    x+=(x-mx)*p.mouthWide*.12*wx*wy;
    // Inner brows lift in the sad expression; change remains local to the face.
    const browY=1-smooth(Math.abs(y-226)/26);
    y-=p.sad*6*browY*(1-smooth(Math.abs(x-280)/80));
    y-=p.brow*3*browY*(1-smooth(Math.abs(x-280)/100));
    const edge=smooth((Math.abs(x-286)-100)/95)*(1-smooth((y-407)/40));
    const tip=smooth((y-230)/190);
    x+=(p.hair*(1-tip)+p.hairTip*tip)*2.2*edge*smooth((y-115)/230);
    y+=p.hair*.5*edge;
    const ribbon=smooth((x-388)/45)*smooth((y-170)/80)*(1-smooth((y-420)/35));
    x+=p.ribbon*1.5*ribbon;y+=p.ribbon*.5*ribbon;
    const bangs=(1-smooth((y-245)/40))*smooth((y-65)/120);
    x+=p.fringe*1.2*bangs;
    return [x,y];
  }
  function deform(part,x,y,p){
    const src=[x,y];
    if(part.name==='head'){
      const v=headDeform(src,p);
      let q=toWorld(part,v);
      // Curved face surface supplies parallax for nose/eyes versus silhouette.
      const localX=q[0]-400,localY=q[1]-220;
      const neck=1-smooth((q[1]-270)/24);
      const depth=(30*Math.exp(-((localX/64)**2)-((localY/80)**2))+10*Math.exp(-((localX/16)**2)-((localY/22)**2)))*neck;
      const yaw=p.faceYaw*degrees,pitch=p.pitch*degrees;
      const z=-localX*Math.sin(yaw)*neck+depth*Math.cos(yaw);
      q[0]=400+localX*mix(1,Math.cos(yaw),neck)+depth*Math.sin(yaw);
      q[1]=220+localY*mix(1,Math.cos(pitch),neck)-z*Math.sin(pitch);
      q=rotate(q,[400,294],p.head*degrees);
      q[0]+=p.yaw*smooth((294-q[1])/150);
      q[1]+=p.nod*smooth((294-q[1])/130);
      return torso(q,p,z*Math.cos(pitch)+localY*Math.sin(pitch)*neck);
    }
    let q=toWorld(part,src);
    if(part.name==='body'){
      const breath=1-smooth((y-240)/50);
      q[0]=400+(q[0]-400)*(1+p.breath*breath);
      q[1]-=p.breath*80*breath;
      const skirt=smooth((y-270)/225);
      q[0]+=p.hem*2*skirt;
      q[1]+=p.cloth*.6*skirt*Math.sin((x-768)/100);
      // Jacket flaps have their own response to the spine instead of moving
      // rigidly with the printed number on the bodice.
      const flap=smooth((Math.abs(x-768)-82)/45)*(1-smooth((y-280)/40))*smooth((y-130)/65);
      q[0]+=p.cloth*1.4*flap;
      const volume=20*Math.exp(-(((q[0]-400)/110)**2))*smooth((y-20)/90)*(1-smooth((y-250)/220));
      return torso(q,p,volume);
    }
    if(part.name.startsWith('arm')){
      const side=part.name.at(-1);
      let local=bend(src,part.wrist,p[`wrist${side}`]*degrees,70);
      local=bend(local,part.elbow,p[`elbow${side}`]*degrees,200);
      q=toWorld(part,local);
      q=rotate(q,part.position,p[`upper${side}`]*degrees);
      const cuff=Math.exp(-(((y-part.wrist[1])/26)**2));
      q[0]+=p[`cuff${side}`]*cuff;
      const reach=p[`reach${side}`]*smooth((y-part.anchor[1])/(part.wrist[1]-part.anchor[1]));
      return torso(q,p,reach);
    }
    const offset=(x-part.anchor[0])*part.scale*part.width;
    if(y>=part.ankle)return [part.position[0]+offset,q[1]];
    const center=legCenter(part,y,p);center[0]+=offset;
    if(y<part.anchor[1])center[1]+=(y-part.anchor[1])*part.scale;
    return project(center);
  }
  function mesh(part){
    const positions=[],uv=[],indices=[],lines=[];
    const [x,y,w,h]=part.rect;
    for(let row=0;row<=part.rows;row++)for(let col=0;col<=part.cols;col++){
      const sx=x+.5+(w-1)*col/part.cols,sy=y+.5+(h-1)*row/part.rows;
      positions.push(sx,sy);uv.push(sx/1536,sy/1024);
    }
    for(let row=0;row<part.rows;row++)for(let col=0;col<part.cols;col++){
      const a=row*(part.cols+1)+col,b=a+1,c=a+part.cols+1,d=c+1;
      indices.push(a,c,b,b,c,d);lines.push(a,b,a,c,b,c);
    }
    return {source:new Float32Array(positions),vertices:new Float32Array(positions.length),uv:new Float32Array(uv),indices:new Uint16Array(indices),lines:new Uint16Array(lines)};
  }
  window.MaoMesh={Rig,parts,deform,mesh};
})();
