// Offline visual check. Uses a temporary headless browser, no Mao services.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
  const browser=await chromium.launch({executablePath:process.env.MAO_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files','--autoplay-policy=no-user-gesture-required','--mute-audio']});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];
    page.on('pageerror',error=>errors.push(String(error)));
    await page.goto(pathToFileURL(path.resolve('web_tool/mao-5070/performance-scene-preview.html')).href);
    await page.waitForFunction(()=>window.previewBridge?.state.ready,{timeout:30000});
    await page.locator('nav').evaluate(node=>node.style.visibility='hidden');
    await page.screenshot({path:'logs/mao-theatre-lounge.png'});
    // Sample both the gathered fabric and a complete closed frame.
    await page.evaluate(()=>{window.curtainFrameTimes=[];let previous=performance.now();function frame(now){if(document.querySelector('.mao-curtain')?.dataset.active==='true')window.curtainFrameTimes.push(now-previous);previous=now;requestAnimationFrame(frame);}requestAnimationFrame(frame);});
    await page.evaluate(()=>window.selectScene('studio'));
    await page.waitForFunction(()=>{const c=document.querySelector('.mao-curtain');const p=Number(c?.style.getPropertyValue('--closed'));return c?.dataset.phase==='closing'&&p>.35&&p<.65;});
    await page.screenshot({path:'logs/mao-theatre-curtain-moving-v2.png'});
    await page.waitForFunction(()=>window.previewBridge?.state.sceneTransition==='covered');
    await page.screenshot({path:'logs/mao-theatre-curtain.png'});
    await page.screenshot({path:'logs/mao-theatre-curtain-v2.png'});
    await page.waitForFunction(()=>window.previewBridge?.state.background==='tv-studio'&&window.previewBridge?.state.sceneTransition==='idle');
    const curtainCheck=await page.evaluate(()=>({gpu:document.querySelector('.mao-curtain').dataset.gpu,soundPlays:Number(document.querySelector('.mao-curtain').dataset.soundPlays),frameTimes:window.curtainFrameTimes}));
    if(curtainCheck.gpu!=='true'||curtainCheck.soundPlays!==2)throw Error('Curtain GPU/audio integration failed: '+JSON.stringify(curtainCheck));
    await page.screenshot({path:'logs/mao-theatre-game.png'});
    await page.evaluate(()=>window.selectScene('concert'));
    await page.waitForFunction(()=>window.previewBridge?.state.background==='concert'&&window.previewBridge?.state.sceneTransition==='idle');
    await page.screenshot({path:'logs/mao-theatre-concert.png'});
    await page.evaluate(()=>window.selectScene('lounge'));
    await page.waitForFunction(()=>window.previewBridge?.state.background==='disco'&&window.previewBridge?.state.sceneTransition==='idle');
    await page.setViewportSize({width:460,height:650});
    await page.evaluate(()=>window.selectScene('studio'));
    await page.waitForFunction(()=>window.previewBridge?.state.sceneTransition==='covered');
    await page.screenshot({path:'logs/mao-theatre-curtain-narrow.png'});
    await page.waitForFunction(()=>window.previewBridge?.state.background==='tv-studio'&&window.previewBridge?.state.sceneTransition==='idle');
    // Real HTMLAudio + WebAudio against an intercepted in-memory test tone.
    // Nothing is saved into the prepared song directory or sent to speakers.
    const rate=8000,seconds=2,samples=rate*seconds,wav=Buffer.alloc(44+samples*2);
    wav.write('RIFF',0);wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(rate,24);wav.writeUInt32LE(rate*2,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(samples*2,40);
    for(let i=0;i<samples;i++)wav.writeInt16LE(Math.round(Math.sin(i/rate*Math.PI*440*2)*4000),44+i*2);
    await page.route('http://127.0.0.1:12393/test-song.wav',route=>route.fulfill({status:200,contentType:'audio/wav',headers:{'Access-Control-Allow-Origin':'*'},body:wav}));
    const audioCheck=await page.evaluate(async()=>{
      const {SingingPlayer}=await import('./draco/singing-player.mjs');const events=[];
      let ended;const done=new Promise(resolve=>ended=resolve);
      const player=new SingingPlayer({clientId:'offline-check',api:async event=>{events.push(event.event);if(event.event==='ended')ended();return {accepted:true};},createAudio:()=>new Audio('http://127.0.0.1:12393/test-song.wav')});
      player.update({phase:'loading',run_id:'test',song:{id:'test',bpm:120}});await player.tryStart();
      const pose=player.pose;
      await Promise.race([done,new Promise((_,reject)=>setTimeout(()=>reject(Error('Audio did not end')),8000))]);player.dispose();
      return {events,started:pose.playing};
    });
    if(!audioCheck.started||audioCheck.events.join(',')!=='claim,playing,ended')throw Error(JSON.stringify(audioCheck));
    if(errors.length)throw Error(errors.join('\n'));
    const sorted=curtainCheck.frameTimes.sort((a,b)=>a-b),p95=sorted[Math.floor(sorted.length*.95)];
    const result={ok:true,errors,audioCheck,curtainCheck:{gpu:curtainCheck.gpu,soundPlays:curtainCheck.soundPlays,p95FrameMs:p95},frames:await page.evaluate(()=>window.previewBridge.state.frames)};
    fs.writeFileSync('logs/mao-theatre-visual-check.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
