(() => {
  const $=id=>document.getElementById(id);
  const renderer=new window.MaoMesh.Renderer($('character'),'parts-atlas.png');
  let talkingUntil=0,lastAction='greet',audioContext,analyser,samples,objectUrl,demoNext=0,demoIndex=0;
  window.maoMeshPreview=renderer;
  const audio=$('audio');
  audio.src='voice-preview.wav';audio.classList.add('loaded');
  function setupAudio(){
    if(audioContext)return;
    audioContext=new AudioContext();const source=audioContext.createMediaElementSource(audio);analyser=audioContext.createAnalyser();analyser.fftSize=1024;samples=new Float32Array(analyser.fftSize);source.connect(analyser);analyser.connect(audioContext.destination);
  }
  renderer.audioLevel=()=>{
    if(analyser&&!audio.paused){analyser.getFloatTimeDomainData(samples);return Math.sqrt(samples.reduce((sum,x)=>sum+x*x,0)/samples.length);}
    return performance.now()<talkingUntil?Math.max(0,Math.sin(performance.now()/110))*.23:0;
  };
  renderer.ready.then(()=>{$('status').textContent='SẴN SÀNG';}).catch(error=>{$('status').textContent=error.message;console.error(error);});
  function hold(){
    renderer.rig=new window.MaoMesh.Rig();for(let i=0;i<120;i++)renderer.rig.update(1/120);
    renderer.rig.play(lastAction);for(let i=0;i<(lastAction==='blink'?12:180);i++)renderer.rig.update(1/120,0);
  }
  document.querySelectorAll('[data-action]').forEach(button=>button.addEventListener('click',()=>{
    $('demo').checked=false;
    lastAction=button.dataset.action;renderer.rig.play(lastAction);if($('hold').checked)hold();
    $('action').textContent=button.textContent;
    document.querySelectorAll('[data-action]').forEach(b=>b.classList.toggle('active',b===button));
  }));
  $('talk').addEventListener('click',async()=>{
    $('demo').checked=false;
    $('hold').checked=false;$('pause').checked=false;renderer.paused=false;
    if(audio.src){try{setupAudio();await audioContext.resume();audio.currentTime=0;await audio.play();$('action').textContent='Nói theo âm thanh';}catch(error){$('status').textContent='Không phát được âm thanh';console.error(error);}}
    else{talkingUntil=performance.now()+10000;$('action').textContent='Nhịp nói giả lập · 10 giây';}
  });
  $('pause').addEventListener('change',e=>{renderer.paused=e.target.checked||$('hold').checked;});
  $('hold').addEventListener('change',e=>{renderer.paused=e.target.checked||$('pause').checked;if(e.target.checked)hold();});
  $('demo').addEventListener('change',e=>{if(e.target.checked){$('hold').checked=false;$('pause').checked=false;renderer.paused=false;demoNext=0;demoIndex=0;}});
  $('wire').addEventListener('change',e=>{renderer.wire=e.target.checked;});
  $('closeup').addEventListener('change',e=>{renderer.closeup=e.target.checked;});
  $('transparent').addEventListener('change',e=>document.querySelector('.stage').classList.toggle('transparent',e.target.checked));
  $('audio-file').addEventListener('change',async e=>{
    const file=e.target.files[0];if(!file)return;
    if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=URL.createObjectURL(file);audio.src=objectUrl;audio.classList.add('loaded');
    setupAudio();
    $('audio-note').textContent='Đã chọn âm thanh local. Nhấn Thử nói chuyện để kiểm tra miệng theo tiếng thật.';
  });
  audio.addEventListener('play',()=>{setupAudio();audioContext.resume();});
  document.querySelector('.stage').addEventListener('pointermove',e=>{const b=e.currentTarget.getBoundingClientRect();renderer.rig.gaze=[Math.max(-1,Math.min(1,(e.clientX-b.left)/b.width*2-1)),Math.max(-.5,Math.min(.5,(e.clientY-b.top)/b.height-.5))];});
  document.querySelector('.stage').addEventListener('pointerleave',()=>{renderer.rig.gaze=[0,0];});
  let frames=0,now=performance.now();setInterval(()=>{const next=performance.now();$('metrics').textContent=`${Math.round((renderer.frames-frames)*1000/(next-now))} FPS · 6 lớp mesh`;frames=renderer.frames;now=next;},1000);
  setInterval(()=>{$('character').dataset.mouthOpen=(renderer.rig.p.mouth||0).toFixed(3);$('character').dataset.eyeClosed=(renderer.rig.p.blink||0).toFixed(3);},100);
  const demo=[['greet','Vẫy tay chào',6.5],['explain','Cử chỉ giải thích',7.5],['weight','Chuyển trọng tâm',7.5],['turn','Quay vai và đầu',7.5],['nod','Gật đầu',5.5],['curious','Tò mò',6],['laugh','Cười',6.5],['shy','Ngượng ngùng',6],['sad','Buồn',8.5],['idle','Đứng nghỉ',5]];
  setInterval(()=>{if(!$('demo').checked||renderer.paused||renderer.rig.time<demoNext)return;const [action,label,duration]=demo[demoIndex++%demo.length];renderer.rig.play(action);lastAction=action;$('action').textContent=label;demoNext=renderer.rig.time+duration;document.querySelectorAll('[data-action]').forEach(b=>b.classList.toggle('active',b.dataset.action===action));},100);
  audio.addEventListener('ended',()=>{$('action').textContent='Đứng nghỉ';});
  let clipUrl;
  $('record').addEventListener('click',()=>{
    if(!window.MediaRecorder||!$('character').captureStream){$('status').textContent='Trình duyệt chưa hỗ trợ ghi clip';return;}
    const button=$('record'),stream=$('character').captureStream(30),chunks=[];
    const mime=['video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(type=>MediaRecorder.isTypeSupported(type));
    const recorder=new MediaRecorder(stream,mime?{mimeType:mime,videoBitsPerSecond:3500000}:undefined);
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
    recorder.onstop=()=>{stream.getTracks().forEach(t=>t.stop());if(clipUrl)URL.revokeObjectURL(clipUrl);clipUrl=URL.createObjectURL(new Blob(chunks,{type:recorder.mimeType}));const link=$('clip');link.href=clipUrl;link.hidden=false;button.disabled=false;button.textContent='Ghi clip chuyển động · 28 giây';$('status').textContent='Đã ghi clip';};
    $('hold').checked=false;$('pause').checked=false;$('closeup').checked=false;renderer.paused=false;renderer.closeup=false;
    $('demo').checked=true;demoIndex=0;demoNext=0;
    button.disabled=true;button.textContent='Đang ghi clip…';$('status').textContent='Đang ghi 28 giây';recorder.start();setTimeout(()=>{if(recorder.state==='recording')recorder.stop();},28000);
  });
  window.addEventListener('pagehide',()=>{renderer.destroy();audioContext?.close();if(objectUrl)URL.revokeObjectURL(objectUrl);});
})();
