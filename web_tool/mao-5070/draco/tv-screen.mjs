// Mao's word-game board: emerald uniform, ivory letter cards and silver stars.
import {cooldownSeconds} from './game-status.mjs';
export const SCREEN_WIDTH=1920,SCREEN_HEIGHT=1080;
const C={paper:'#f3eedf',white:'#fffaf0',ink:'#183e34',muted:'#64796c',green:'#164c3c',deep:'#10392e',mint:'#bdd9be',silver:'#c7d3c8',line:'#c7d2bd',rose:'#d67d69'};
const SANS='"Segoe UI",sans-serif',SERIF='"Times New Roman",serif';
let sticker,stickerReady=false,artRevision=0;
export function tvArtRevision(){return artRevision;}
function loadSticker(){if(sticker||typeof Image==='undefined')return;sticker=new Image();sticker.crossOrigin='anonymous';sticker.onload=()=>{stickerReady=true;artRevision++;};sticker.onerror=()=>{artRevision++;};sticker.src=new URL('./assets/mao-ui-sticker-v3.png',import.meta.url).href;}
export function remainingSeconds(state,now=Date.now(),offset=0){return Math.max(0,Math.min(60,Math.ceil((state.ends_at*1000-now-offset)/1000)));}
export function screenPhase(state,now=Date.now(),offset=0){return !state||state.phase==='idle'||(state.phase==='finished'&&now+offset>=state.show_until*1000)?'idle':state.phase;}
function panel(c,x,y,w,h,r,fill,stroke){c.beginPath();c.roundRect(x,y,w,h,r);if(fill){c.fillStyle=fill;c.fill();}if(stroke){c.strokeStyle=stroke;c.lineWidth=2;c.stroke();}}
function text(c,value,x,y,size=38,color=C.ink,weight=500,align='left',maxWidth,family=SANS){c.font=`${weight} ${size}px ${family}`;c.fillStyle=color;c.textAlign=align;c.textBaseline='middle';c.fillText(String(value),x,y,maxWidth);}
function short(c,value,width,size=38,weight=500){c.font=`${weight} ${size}px ${SANS}`;let s=String(value);if(c.measureText(s).width<=width)return s;while(s.length&&c.measureText(s+'…').width>width)s=s.slice(0,-1);return s+'…';}
function wrap(c,value,x,y,width,size=52,maxLines=2){
  let lines=[];
  do{c.font=`500 ${size}px ${SANS}`;lines=[];let row='';for(const word of String(value).split(/\s+/)){const next=row?row+' '+word:word;if(row&&c.measureText(next).width>width){lines.push(row);row=word;}else row=next;}if(row)lines.push(row);if(lines.length<=maxLines||size<=42)break;size-=2;}while(true);
  lines.slice(0,maxLines).forEach((s,i)=>text(c,i===maxLines-1&&lines.length>maxLines?short(c,s+'…',width,size):s,x,y+i*size*1.22,size));
}
function star(c,x,y,size,color=C.silver){c.save();c.translate(x,y);c.fillStyle=color;c.beginPath();for(let i=0;i<8;i++){const a=i*Math.PI/4-Math.PI/2,r=i%2?size*.24:size;c.lineTo(Math.cos(a)*r,Math.sin(a)*r);}c.closePath();c.fill();c.restore();}
function chip(c,label,x,y,w,green=false){panel(c,x,y,w,54,27,green?C.green:'#e5eadb',green?C.mint:C.line);text(c,label,x+w/2,y+27,27,green?C.white:C.ink,650,'center',w-30);}
function background(c){
  c.fillStyle=C.paper;c.fillRect(0,0,1920,1080);panel(c,16,16,1888,1048,30,null,C.green);panel(c,26,26,1868,1028,24,null,C.line);
  // Uniform-inspired green/silver stripes and little hand-drawn sparkles.
  c.fillStyle=C.green;c.fillRect(42,42,9,996);c.fillStyle=C.silver;c.fillRect(55,42,3,996);
  for(const [x,y,s] of [[1818,380,13],[1408,656,17],[1864,732,9],[1338,190,12],[1256,89,9]])star(c,x,y,s);
}
function brand(c,offline){
  text(c,'Mao bày trò',84,85,48,C.green,'italic 600','left',undefined,SERIF);star(c,460,84,15,C.green);
  text(c,'MAO VTUBER',1816,83,29,C.muted,650,'right');
  if(offline)text(c,'Đang kết nối lại với Mao…',958,84,28,C.rose,500,'center');
  c.strokeStyle=C.line;c.lineWidth=2;c.beginPath();c.moveTo(82,139);c.quadraticCurveTo(960,153,1835,139);c.stroke();
}
function mascot(c,x=1420,y=334,w=390,h=385){
  if(stickerReady){const scale=Math.min(w/sticker.naturalWidth,h/sticker.naturalHeight),dw=sticker.naturalWidth*scale,dh=sticker.naturalHeight*scale;c.drawImage(sticker,x+(w-dw)/2,y+(h-dh)/2,dw,dh);}
  else{panel(c,x+30,y+65,w-60,h-100,130,'#dde7d4',C.silver);text(c,'Mao',x+w/2,y+h/2,78,C.green,'italic 600','center',undefined,SERIF);star(c,x+58,y+55,25,C.green);}
}
function footer(c,left='Bình luận đáp án · Viết không dấu cũng được nha!',right='Chơi cùng Mao ♡'){
  text(c,left,86,1025,29,C.muted);text(c,right,1830,1025,31,C.green,600,'right');
}
function tile(c,letter,x,y,size=116,index=0){
  c.save();c.translate(x+size/2,y+size*.59);c.rotate(index%2?.018:-.018);
  panel(c,-size/2+3,-size*.59+7,size,size*1.18,15,'#09271f55');panel(c,-size/2,-size*.59,size,size*1.18,15,C.white,C.silver);
  text(c,letter||'_',0,size*.03,size*.62,C.green,700,'center',size-14,SERIF);star(c,-size*.33,-size*.36,5,'#a9bda6');c.restore();
}
function slots(c,state){
  const sizes=state.slots||[],count=sizes.reduce((a,b)=>a+b,0),gap=12,wordGap=35,size=Math.min(126,(1195-(count-sizes.length)*gap-(sizes.length-1)*wordGap)/Math.max(1,count));
  const width=count*size+(count-sizes.length)*gap+(sizes.length-1)*wordGap;let x=718-width/2,index=0;
  sizes.forEach(n=>{for(let j=0;j<n;j++){tile(c,'',x,409,size,index++);x+=size+gap;}x+=wordGap-gap;});
}
function clock(c,seconds,waiting){
  const x=1737,y=223,r=76,color=seconds<=10&&!waiting?C.rose:C.green;
  panel(c,x-23,y-r-21,46,22,9,C.silver);c.lineWidth=6;c.strokeStyle=C.silver;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.stroke();
  c.lineWidth=7;c.strokeStyle=color;c.lineCap='round';c.beginPath();c.arc(x,y,r,-Math.PI/2,-Math.PI/2+Math.PI*2*(waiting?1:seconds/60));c.stroke();c.lineCap='butt';
  text(c,waiting?'—':seconds,x,y-7,64,color,700,'center',undefined,SERIF);text(c,'giây',x,y+43,25,C.muted,500,'center');
}
function playing(c,state,phase,now,offset){
  text(c,'Vua tiếng Việt',84,223,96,C.green,700,'left',1450,SERIF);
  text(c,`${state.category||'Chơi cùng Mao'}  ·  ${state.slots?.length||0} tiếng`,88,291,33,C.muted);
  chip(c,`${state.participants||0} bạn cùng chơi`,1323,264,296);clock(c,remainingSeconds(state,now,offset),phase==='waiting');
  panel(c,76,341,1295,392,28,C.green,C.silver);panel(c,86,351,1275,372,21,null,'#aec9b044');
  text(c,'Ghép lại thành từ gì nhỉ?',720,378,27,'#d8e4ce',500,'center');slots(c,state);
  text(c,'Chữ Mao đưa nè',720,596,26,'#ccddc9',500,'center');
  const letters=state.letters||[],width=Math.min(1180,letters.length*68),step=width/Math.max(1,letters.length);
  letters.forEach((letter,i)=>{panel(c,720-width/2+i*step,625,step-10,64,12,'#edf0df',C.silver);text(c,letter,720-width/2+i*step+(step-10)/2,657,37,C.green,700,'center');});
  mascot(c);panel(c,1404,708,420,48,24,'#e5eadb',C.line);text(c,'Mao đang hóng đáp án nè~',1614,732,27,C.green,500,'center',395);
  panel(c,76,790,1755,192,24,'#e0e5d4');panel(c,70,781,1761,192,24,C.white,C.line);
  const index=state.hint_index||0;panel(c,98,754,202,58,12,C.green);text(c,phase==='waiting'?'CHUẨN BỊ':`GỢI Ý ${index+1}`,199,784,29,C.white,700,'center');
  for(let i=0;i<3;i++)star(c,1690+i*45,816,12,i<=index?C.green:C.line);
  wrap(c,phase==='waiting'?'Mao nói nốt chút xíu nhé, bạn sẽ có đủ 60 giây để chơi!':state.hints?.at(-1)||'Gợi ý sắp tới rồi nè…',111,864,1638,52,2);
  footer(c);
}
function idle(c,state,now,offset){
  chip(c,'MỘT CHÚT TINH NGHỊCH CÙNG MAO',88,195,665);
  text(c,'Chơi với',87,358,114,C.green,600,'left',undefined,SERIF);text(c,'Mao nhé?',87,492,144,C.green,'italic 700','left',undefined,SERIF);
  text(c,'Ghép vài chữ. Đoán vài từ.',93,620,44,C.muted);text(c,'Biết đâu bạn đoán nhanh hơn Mao đó~',93,686,38,C.muted);
  panel(c,88,792,1040,125,23,C.green);
  const seconds=cooldownSeconds(state,now,offset);
  if(seconds>0)text(c,`Vòng mới sau ${seconds} giây`,608,853,50,C.white,650,'center');
  else{text(c,'Gõ',126,853,37,C.white);text(c,'!vuatiengviet',206,853,55,C.white,750);text(c,'để bắt đầu',660,853,37,C.white);}
  mascot(c,1210,241,585,627);star(c,1224,328,32,C.green);star(c,1780,787,25,C.green);
  footer(c,'60 giây · 3 gợi ý · Cùng nhau tìm đáp án','Mao bày trò, bạn giải nha ♡');
}
function result(c,state,now,offset){
  text(c,'Đáp án đây rồi!',84,226,89,C.green,700,'left',1300,SERIF);chip(c,'HẸN BẠN VÒNG SAU NHA',1403,223,420);
  panel(c,76,316,1295,124,24,C.green,C.silver);text(c,String(state.answer||'').toLocaleUpperCase('vi'),113,379,71,C.white,700,'left',1215,SERIF);
  const board=state.leaderboard||[],leader=board[0],win=!leader?'Vòng sau thử cùng Mao nha!':leader.score===100?`${leader.nickname} đoán đúng sớm nhất!`:`${leader.nickname} gần đúng nhất · ${leader.score} điểm`;
  text(c,short(c,win,1260,39,600),85,486,39,C.ink,600);
  panel(c,76,542,1295,414,23,C.white,C.line);panel(c,76,542,1295,58,20,'#dce7d4');
  text(c,'Bạn cùng chơi',181,572,27,C.green,650);text(c,'Thời gian',1100,572,26,C.muted,600,'right');text(c,'Điểm',1324,572,26,C.green,650,'right');
  board.slice(0,5).forEach((player,i)=>{const y=640+i*65;if(i===0)panel(c,91,y-28,1265,58,12,'#edf1df');text(c,String(i+1).padStart(2,'0'),112,y,28,C.muted,600);text(c,short(c,player.nickname,800,35),181,y,35,C.ink,600);text(c,`${Number(player.seconds).toFixed(1)}s`,1100,y,30,C.muted,500,'right');text(c,`${player.score}`,1324,y,37,C.green,750,'right');});
  const seconds=cooldownSeconds(state,now,offset);
  if(!board.length)text(c,seconds>0?'Mình nghỉ một chút rồi thử tiếp nha!':'Gõ !vuatiengviet để cùng Mao thử lại nào.',720,748,36,C.muted,500,'center');
  mascot(c,1410,373,415,438);text(c,!leader?'Vòng sau chơi nha~':leader.score===100?'Đỉnh quá đi~':'Suýt nữa thôi mà~',1614,854,35,C.green,'italic 600','center',400,SERIF);
  footer(c,seconds>0?`Vòng mới sau ${seconds} giây · Mình chờ Mao một chút nha`:'Gõ !vuatiengviet để mở vòng tiếp theo','Mao cảm ơn bạn đã chơi ♡');
}
export function drawTvScreen(canvas,state,{now=Date.now(),offset=0,offline=false}={}){
  loadSticker();const c=canvas.getContext('2d');if(!c)return;c.save();c.clearRect(0,0,canvas.width,canvas.height);c.scale(canvas.width/1920,canvas.height/1080);
  background(c);brand(c,offline);const phase=screenPhase(state,now,offset);if(phase==='idle')idle(c,state,now,offset);else if(phase==='finished')result(c,state,now,offset);else playing(c,state,phase,now,offset);c.restore();
}
