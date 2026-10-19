import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {buildDracoShell} from '../scripts/build_draco_shell.mjs';
import {createNativeBridge} from '../web_tool/mao-5070/draco/native-bridge.mjs';
import {DesktopSpace} from '../web_tool/mao-5070/draco/desktop-space.mjs';
const root=path.resolve(import.meta.dirname,'..');
buildDracoShell(root);
const directory=path.join(root,'private/tools/vtuber-desktop-unpacked/out/renderer');
const html=fs.readFileSync(path.join(directory,'index.html'),'utf8'),original=fs.readFileSync(path.join(directory,'assets',html.match(/src="\.\/assets\/([^"/]+\.js)"/)[1]),'utf8').replace(/\r\n/g,'\n');
const generated=fs.readFileSync(path.join(directory,'assets/mao-draco-shell.js'),'utf8');
let audioTask;
const taskSource=generated.match(/addAudioTask\(\{[\s\S]*?\n          \}\);/)[0];
const intent={id:'pipeline-test',command:'dj'};
const pose={right:.72,tilt:-4,smile:.4};
vm.runInNewContext(taskSource,{message:{actions:{body:intent,motions:['refuse'],pose}},window:{maoDraco:{renderer:{}}},addAudioTask:value=>{audioTask=value;}});
assert.equal(audioTask.body,intent,'queued audio discarded body intent before playback');
assert.equal(audioTask.motions[0],'refuse','queued audio discarded explicit story gesture');
assert.equal(audioTask.pose,pose,'queued audio discarded composed motor intention');
// Complete original UI components remain verbatim; the renderer is replaced
// at a single AppContent call site, rather than reimplementing those features.
for(const [start,end] of [['function useDraggable(', 'function InputSubtitle()'],['function useIpcHandlers()', 'const DEFAULT_HISTORY ='],['function AppContent()', 'function App()']]){
  let section=original.slice(original.indexOf(start),original.indexOf(end,original.indexOf(start)));
  if(start==='function AppContent()')section=section.replace('jsxRuntimeExports.jsx(Live2D, {})','jsxRuntimeExports.jsx(MaoDesktopAvatar, {})').replace('jsxRuntimeExports.jsx(Background, {})','jsxRuntimeExports.jsx(MaoDesktopBackground, {})');
  if(start==='function AppContent()')section=section.replace('...layoutStyles.footer,\n              zIndex: 10,','...layoutStyles.footer,\n              id: "mao-window-footer",\n              zIndex: 10,');
  if(start==='function AppContent()')section=section
    .replace('const [showSidebar, setShowSidebar] = reactExports.useState(true);','const [showSidebar, setShowSidebar] = reactExports.useState(() => !window.maoDraco);')
    .replace('children: /* @__PURE__ */ jsxRuntimeExports.jsx(Subtitle, {})','id: "mao-window-subtitle",\n              children: /* @__PURE__ */ jsxRuntimeExports.jsx(Subtitle, {})')
    .replace('children: /* @__PURE__ */ jsxRuntimeExports.jsx(WebSocketStatus, {})','id: "mao-legacy-status", children: /* @__PURE__ */ jsxRuntimeExports.jsx(WebSocketStatus, {})');
  assert.ok(generated.includes(section),`original desktop behavior changed: ${start}`);
}
const bridge=createNativeBridge();
let mode='pet',modelInfo={url:'/live2d-models/mao_pro/runtime/mao_pro.model3.json',scrollToResize:false},forceIgnoreMouse=true,refreshes=0;
bridge.renderer={refresh(){refreshes++;}};
let cameraStops=0;
const effects=[],hooks=[],legacy=()=>{},background=()=>{},box=()=>{},context={window:{maoDraco:bridge},
  reactExports:{memo:value=>value,useRef:()=>({current:null}),useEffect:fn=>effects.push(fn)},
  useMode:()=>({mode}),useLive2DConfig:()=>({modelInfo}),useForceIgnoreMouse:()=>({forceIgnoreMouse}),useWebSocket:()=>({wsState:'OPEN'}),
  useAiState:()=>({aiState:'thinking-speaking'}),
  useIpcHandlers:()=>hooks.push('ipc'),useInterrupt:()=>hooks.push('interrupt'),useAudioTask:()=>hooks.push('audio'),
  useCamera:()=>({stopBackgroundCamera(){cameraStops++;}}),Box:box,Background:background,canvasStyles:{background:{container:{position:'relative'}}},
  jsxRuntimeExports:{jsx:(type,props)=>({type,props})},Live2D:legacy
};
vm.createContext(context);vm.runInContext(fs.readFileSync('scripts/draco-shell-component.js','utf8')+'\nglobalThis.components={MaoDracoAvatar,MaoDesktopAvatar,MaoDesktopBackground};',context);
const {MaoDracoAvatar,MaoDesktopAvatar,MaoDesktopBackground}=context.components;
assert.equal(MaoDesktopAvatar({}).type,MaoDracoAvatar);
MaoDracoAvatar();effects[0]();
assert.deepEqual(hooks,['ipc','interrupt','audio']);assert.equal(bridge.options.scrollToResize,false);assert.equal(bridge.options.forceIgnoreMouse,true);assert.equal(bridge.state.socket,'open');assert.equal(refreshes,1);
const plain=MaoDesktopBackground({children:'content'});effects.at(-1)();
assert.equal(plain.type,box);assert.equal(plain.props['data-mao-background'],'none');assert.equal(plain.props.children,'content');assert.equal(plain.props.src,undefined);assert.equal(cameraStops,1);
modelInfo={url:'/live2d-models/other/other.model3.json'};assert.equal(MaoDesktopAvatar({}).type,legacy,'Switch Character lost the original renderer');
assert.equal(MaoDesktopBackground({}).type,background,'other characters lost their original background');effects.at(-1)();assert.equal(cameraStops,1);
class AudioFixture extends EventTarget {getAttribute(){return 'data:audio/wav;base64,fixture';}}
const audio=new AudioFixture(),payload={displayText:{text:'Chào bạn'},volumes:[.5],sliceLength:20};
bridge.attachAudio(audio,payload);assert.equal(bridge.audio,audio);assert.equal(bridge.payload,payload);
audio.dispatchEvent(new Event('playing'));audio.dispatchEvent(new Event('playing'));assert.equal(bridge.state.audioStarted,1);
audio.dispatchEvent(new Event('ended'));assert.equal(bridge.state.audioEnded,1);assert.equal(bridge.audio,null);assert.equal(bridge.state.audioErrors,0);
let prepared=false;
bridge.renderer={prepareSpeech:async value=>{assert.equal(value,audio);prepared=true;return true;},refresh(){}};
bridge.attachAudio(audio,payload);assert.equal(await bridge.prepareAudio(audio),true);assert.ok(prepared&&bridge.speechSession);
bridge.update({aiState:'thinking-speaking'});assert.equal(bridge.speechSession,true,'gaps between queued sentences released speech focus');
bridge.update({aiState:'idle'});assert.equal(bridge.speechSession,false);
assert.equal(await bridge.prepareAudio(new AudioFixture()),false,'stale audio must not acquire speech focus');
// A normal desktop text input starts its motion locally, even if inference or
// the backend's conversation queue is busy. The original message is unchanged.
const motion=new DesktopSpace(),sent=[];bridge.renderer={perform:value=>motion.perform(value)};
const serviceSource=generated.slice(generated.indexOf('class WebSocketService {'),generated.indexOf('const wsService = WebSocketService.getInstance();'));
vm.runInNewContext(serviceSource+'\nconst service=new WebSocketService();service.ws={readyState:1,send:raw=>sent.push(JSON.parse(raw))};service.sendMessage({type:"text-input",text:"Mao xoay một vòng đi!"});',{
  Subject:class{next(){}},WebSocket:{OPEN:1},window:{maoDraco:bridge},sent,console
});
assert.equal(motion.phase,'step-back');assert.equal(sent[0].text,'Mao xoay một vòng đi!');
console.log('Original desktop shell: original UI/IPC/drag preserved, 3D renderer selection, scroll/passthrough options, character switching and audio bridge passed.');
