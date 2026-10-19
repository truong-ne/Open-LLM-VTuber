export function attachMotorPreview({actor,face,start}){
  const panel=document.createElement('section');panel.className='story-panel';
  const heading=document.createElement('h2');heading.textContent='Tự phối tư thế';panel.append(heading);
  const note=document.createElement('p');note.className='note';note.textContent='Các mức bên dưới ghép thành tư thế liên tục, không dùng clip có sẵn. Bản thử này không sửa bộ nhớ của Mao desktop.';panel.append(note);
  const values={tilt:-4,nod:2,lean:1,left:.2,right:.65,height:0,smile:.4,brow:.2,eyes:.1};
  for(const [key,label,min,max,step] of [
    ['tilt','Nghiêng đầu',-12,12,1],['nod','Cúi đầu',-10,12,1],['lean','Cúi thân',-4,4,.5],
    ['left','Mở tay trái',0,1,.05],['right','Mở tay phải',0,1,.05],['height','Độ cao tay',-.10,.10,.01],
    ['smile','Nụ cười',0,1,.05],['brow','Nhướng mày',0,1,.05],['eyes','Mở to mắt',0,1,.05]
  ]){
    const row=document.createElement('label');Object.assign(row.style,{display:'flex',alignItems:'center',gap:'10px',margin:'9px 0',fontSize:'13px'});
    const title=document.createElement('span');title.textContent=label;title.style.minWidth='110px';
    const input=document.createElement('input');input.type='range';input.min=min;input.max=max;input.step=step;input.value=values[key];input.setAttribute('aria-label',label);
    input.oninput=()=>{values[key]=Number(input.value);};row.append(title,input);panel.append(row);
  }
  const button=document.createElement('button');button.textContent='Diễn tư thế vừa phối';button.onclick=()=>{start();actor().setMotor({...values,duration:6});face.setExpression('neutral');};panel.append(button);
  document.getElementById('story-actions').after(panel);
}
