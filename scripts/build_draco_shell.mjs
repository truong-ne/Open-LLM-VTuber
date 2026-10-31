import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const writeIfChanged=(file,source)=>{if(!fs.existsSync(file)||fs.readFileSync(file,'utf8')!==source)fs.writeFileSync(file,source);};
export const obsoleteDesktopFiles=['out/renderer/assets/index-CW5qlpM1.js','out/renderer/draco-shell.html','out/renderer/libs/live2dcubismcore.js','out/renderer/libs/live2d.min.js','out/renderer/libs/live2dcubismcore.min.js','out/renderer/assets/index-DBAmt0B7.css','out/main/index.js.before-draco'];
export function keepDesktopEntry(relative){
  if(obsoleteDesktopFiles.includes(relative))return false;
  if(!relative.startsWith('node_modules/'))return true;
  return relative==='node_modules/@electron-toolkit'||['node_modules/@electron-toolkit/utils','node_modules/@electron-toolkit/preload'].some(prefix=>relative===prefix||relative.startsWith(prefix+'/'));
}
export function buildDracoShell(root){
  const renderer=path.join(root,'private/tools/vtuber-desktop-unpacked/out/renderer');
  const runtime=path.join(renderer,'assets/mao-draco-shell.js');
  let source=fs.readFileSync(path.join(root,'scripts/desktop/mao-runtime.js'),'utf8');
  // Observe packets once at the socket boundary, before audio is queued. A
  // generic `case "audio"` anchor can accidentally patch React's DOM switch.
  source=source.replaceAll('        window.maoDelivery?.receive(message);','');
  const incoming='          const message = JSON.parse(event.data);';
  if(source.split(incoming).length!==2)throw Error('Ambiguous desktop socket receive anchor');
  source=source.replace(incoming,incoming+'\n        window.maoDelivery?.receive(message);');
  source=source.replace('delivery: {segment_id:message.segment_id},','delivery: {turn_id:message.turn_id,generation_epoch:message.generation_epoch,segment_id:message.segment_id},');
  for(const [key,relative] of [['delivery','web_tool/mao-5070/delivery.mjs'],['avatar','scripts/draco-shell-component.js'],['subtitle','scripts/mao-studio-component.js'],['app','scripts/mao-app-component.js']]){
    const start=`/* MAO:${key}:START */`,end=`/* MAO:${key}:END */`;
    const a=source.indexOf(start),b=source.indexOf(end,a);
    if(a<0||b<0)throw Error(`Missing canonical Mao component: ${key}`);
    const content=fs.readFileSync(path.join(root,relative),'utf8').replace('export class DeliveryClient','class DeliveryClient');
    source=source.slice(0,a)+start+'\n'+content+'\n'+end+source.slice(b+end.length);
  }
  for(const obsolete of ['function SettingUI(','function Footer(','function General(','const SidebarContent','function BgUrlProvider(','const Live2D = reactExports.memo(','live2dcubismcore.js']){
    if(source.includes(obsolete))throw Error(`Obsolete desktop UI returned: ${obsolete}`);
  }
  writeIfChanged(runtime,source);
  const html=`<!doctype html><html><head><meta charset="UTF-8"><title>Mao VTuber</title>
<script src="./pet-context.js"></script>
<script type="importmap">{"imports":{"three":"http://127.0.0.1:12393/web-tool/mao-5070/3d/vendor/three.module.js"}}</script>
<script type="module">
import {createNativeBridge} from 'http://127.0.0.1:12393/web-tool/mao-5070/draco/native-bridge.mjs?v=7';
window.maoDraco=createNativeBridge();
await import('./assets/mao-draco-shell.js');
</script>
<script type="module">import {createWordGameOverlay} from 'http://127.0.0.1:12393/web-tool/mao-5070/draco/word-game-overlay.mjs?v=10';window.maoWordGame=createWordGameOverlay();</script>
<link rel="stylesheet" href="./assets/mao-studio.css">
</head><body><div id="root"></div></body></html>`;
  writeIfChanged(path.join(renderer,'index.html'),html);
  writeIfChanged(path.join(renderer,'assets/mao-studio.css'),fs.readFileSync(path.join(root,'web_tool/mao-5070/draco/desktop-theme.css'),'utf8'));
  return ['out/renderer/index.html','out/renderer/assets/mao-draco-shell.js','out/renderer/assets/mao-studio.css'];
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(buildDracoShell(path.resolve(import.meta.dirname,'..')).join('\n'));
