// Close-up visual inspection of the real GLB, without starting Mao's services.
const {chromium}=require('playwright');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--allow-file-access-from-files','--mute-audio']});
 try{
  const page=await browser.newPage({viewport:{width:700,height:700}});
  await page.goto(pathToFileURL(path.resolve('web_tool/mao-5070/performance-scene-preview.html')).href);
  await page.waitForFunction(()=>window.previewBridge?.state.ready);
  await page.evaluate(async()=>{
   const T=await import('./3d/vendor/three.module.js'),{GLTFLoader}=await import('./3d/vendor/loaders/GLTFLoader.js'),{AdaptiveBodyActor:BodyActor}=await import('./draco/motor-body.mjs');
   window.previewAvatar.dispose();document.body.replaceChildren();
   const canvas=document.createElement('canvas');document.body.append(canvas);const renderer=new T.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});renderer.setSize(700,700);renderer.setPixelRatio(1);renderer.outputColorSpace=T.SRGBColorSpace;
   const scene=new T.Scene();scene.background=new T.Color('#19201e');scene.add(new T.HemisphereLight(0xffffff,0x777777,2));const light=new T.DirectionalLight(0xffffff,2);light.position.set(-2,3,4);scene.add(light);
   const asset=(await new GLTFLoader().loadAsync('./draco/character.glb')).scene,wrapper=new T.Group();wrapper.add(asset);scene.add(wrapper);asset.updateMatrixWorld(true);
   const bounds=new T.Box3().setFromObject(asset),center=bounds.getCenter(new T.Vector3()),scale=1.8/bounds.getSize(new T.Vector3()).y;wrapper.scale.setScalar(scale);wrapper.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale);wrapper.updateMatrixWorld(true);
   const actor=new BodyActor(asset);for(let i=0;i<180;i++)actor.update(1/120);
   const pelvis=actor.joints.pelvis.getWorldPosition(new T.Vector3()),unit=actor.dynamics.unit;
   const camera=new T.PerspectiveCamera(30,1,.01,20);camera.position.copy(pelvis).add(new T.Vector3(0,-.09*unit,1.15*unit));camera.lookAt(pelvis.clone().add(new T.Vector3(0,-.09*unit,0)));
   window.skirtQA={actor,asset,renderer,scene,camera};renderer.render(scene,camera);
  });
  const prefix=process.argv[2]||'logs/mao-skirt';
  await page.screenshot({path:prefix+'-idle.png'});
  for(const action of ['hipSway','refuse']){
   await page.evaluate(action=>{const q=window.skirtQA;q.actor.play(action);for(let i=0;i<210;i++)q.actor.update(1/120);q.renderer.render(q.scene,q.camera);},action);
   await page.screenshot({path:prefix+'-'+action+'.png'});
  }
  await page.evaluate(()=>{
   document.body.dataset.mode='window';
   const subtitle=document.createElement('section');subtitle.id='mao-window-subtitle';Object.assign(subtitle.style,{position:'fixed',bottom:'12px',left:'50%',transform:'translateX(-50%)'});
   const box=document.createElement('div'),text=document.createElement('p');text.textContent='Hết giờ! Tiếc quá nè, Mao đợi mà chưa thấy ai thử đoán! Đáp án là mưa rào. Mưa rào là cơn mưa thường đến nhanh, hạt to và có thể tạnh khá nhanh. Kiểu đang đi giữa trời nắng mà phải chạy vội vào mái hiên trú mưa đó!';box.append(text);subtitle.append(box);document.body.append(subtitle);
  });
  for(const width of [1000,460]){
   await page.setViewportSize({width,height:700});
   const result=await page.locator('#mao-window-subtitle>div').evaluate(box=>({overflow:getComputedStyle(box).overflow,scrollbar:box.offsetWidth-box.clientWidth,inside:box.getBoundingClientRect().right<=innerWidth}));
   if(result.overflow!=='hidden'||result.scrollbar>3||!result.inside)throw Error('Subtitle scrollbar regression: '+JSON.stringify(result));
   await page.screenshot({path:prefix+'-subtitle-'+width+'.png'});
  }
  console.log(prefix);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
