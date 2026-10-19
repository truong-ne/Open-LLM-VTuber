// Record an offline fixture, then mix the same licensed curtain pull samples
// at the browser's actual BufferSource start times. Headless playback is muted.
const fs=require('node:fs'),path=require('node:path');
// Reuse the workspace FFmpeg instead of downloading a browser/tool runtime.
process.env.PLAYWRIGHT_BROWSERS_PATH=path.resolve('private/playwright-media');
const mediaBin=path.resolve('private/tools/ffmpeg/ffmpeg-master-latest-win64-lgpl-shared/bin');
const registry=JSON.parse(fs.readFileSync(path.join(path.dirname(require.resolve('playwright-core')),'browsers.json'),'utf8'));
const revision=registry.browsers.find(item=>item.name==='ffmpeg').revision;
const recorder=path.join(process.env.PLAYWRIGHT_BROWSERS_PATH,`ffmpeg-${revision}`,'ffmpeg-win64.exe');
fs.mkdirSync(path.dirname(recorder),{recursive:true});if(!fs.existsSync(recorder))fs.copyFileSync(path.join(mediaBin,'ffmpeg.exe'),recorder);
process.env.PATH=mediaBin+path.delimiter+process.env.PATH;
const {chromium}=require('playwright');
const {pathToFileURL}=require('node:url');
const {spawnSync}=require('node:child_process');
(async()=>{
  const browser=await chromium.launch({executablePath:process.env.MAO_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files','--autoplay-policy=no-user-gesture-required','--mute-audio']});
  let video,start,finish,pulls,epoch;
  try{
    epoch=Date.now();
    const page=await browser.newPage({viewport:{width:1280,height:720},recordVideo:{dir:path.resolve('logs/mao-curtain-v2-recording'),size:{width:1280,height:720}}});
    video=page.video();
    await page.addInitScript(()=>{
      window.curtainPulls=[];
      const original=AudioContext.prototype.createBufferSource;
      AudioContext.prototype.createBufferSource=function(...args){
        const source=original.apply(this,args),start=source.start;
        source.start=function(...params){window.curtainPulls.push({at:Date.now(),duration:source.buffer.duration/source.playbackRate.value,kind:source.buffer.duration<1?'close':'open'});return start.apply(source,params);};
        return source;
      };
    });
    await page.goto(pathToFileURL(path.resolve('web_tool/mao-5070/performance-scene-preview.html')).href);
    await page.waitForFunction(()=>window.previewBridge?.state.ready);
    await page.locator('nav').evaluate(node=>node.style.visibility='hidden');
    start=Date.now();await page.waitForTimeout(750);
    await page.evaluate(()=>window.selectScene('studio'));
    await page.waitForFunction(()=>window.previewBridge?.state.background==='tv-studio'&&window.previewBridge?.state.sceneTransition==='idle');
    await page.waitForTimeout(1100);
    await page.evaluate(()=>window.selectScene('lounge'));
    await page.waitForFunction(()=>window.previewBridge?.state.background==='disco'&&window.previewBridge?.state.sceneTransition==='idle');
    await page.waitForTimeout(800);finish=Date.now();pulls=await page.evaluate(()=>window.curtainPulls);
  }finally{await browser.close();}
  const source=await video.path(),duration=(finish-start)/1000,offset=Math.max(0,(start-epoch)/1000);
  if(pulls.length!==4)throw Error('Expected exactly four synchronized curtain pulls');
  fs.writeFileSync('logs/mao-curtain-v2-demo.json',JSON.stringify({duration,pulls:pulls.map(p=>({...p,at:(p.at-start)/1000})),source,offset,credit:'btherad2000 / Freesound 328031 / CC BY 4.0'},null,2));
  const ffmpeg=path.resolve('private/tools/ffmpeg/ffmpeg-master-latest-win64-lgpl-shared/bin/ffmpeg.exe');
  const args=['-y','-loglevel','error','-ss',String(offset),'-i',source];
  for(const pull of pulls)args.push('-i',path.resolve(`web_tool/mao-5070/draco/assets/curtain-${pull.kind}-v2.ogg`));
  const filters=pulls.map((pull,i)=>{
    return `[${i+1}:a]asetpts=PTS-STARTPTS,volume=0.32,adelay=${Math.max(0,Math.round(pull.at-start))}:all=1[a${i}]`;
  });
  filters.push(pulls.map((_,i)=>`[a${i}]`).join('')+`amix=inputs=${pulls.length}:normalize=0,apad,atrim=duration=${duration}[audio]`);
  args.push('-filter_complex',filters.join(';'),'-map','0:v','-map','[audio]','-t',String(duration),'-c:v','h264_nvenc','-preset','p4','-cq','21','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','160k','-metadata','title=Mao curtain v2 offline preview','-metadata','artist=Visual: ChatGPT image generation; sound: btherad2000','-metadata','comment=Adapted curtain pulls: https://freesound.org/people/btherad2000/sounds/328031/ CC BY 4.0 https://creativecommons.org/licenses/by/4.0/ Trimmed, filtered, time-adjusted and mixed for Mao.','-movflags','+faststart','logs/mao-curtain-v2-demo.mp4');
  const result=spawnSync(ffmpeg,args,{encoding:'utf8'});if(result.status!==0)throw Error(result.stderr);
  const probe=spawnSync(path.join(mediaBin,'ffprobe.exe'),['-v','error','-count_packets','-show_streams','-of','json','logs/mao-curtain-v2-demo.mp4'],{encoding:'utf8'});
  if(probe.status!==0||!JSON.parse(probe.stdout).streams.some(stream=>stream.codec_type==='audio'&&Number(stream.nb_read_packets)>20&&Number(stream.duration)>duration-.1&&Number(stream.start_time)<.1))throw Error('Preview is missing its synchronized audio track');
  console.log(JSON.stringify({video:'logs/mao-curtain-v2-demo.mp4',duration,pulls:pulls.length}));
})().catch(error=>{console.error(error);process.exitCode=1;});
