import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const writeIfChanged=(file,source)=>{if(!fs.existsSync(file)||fs.readFileSync(file,'utf8')!==source)fs.writeFileSync(file,source);};
export function buildDracoShell(root){
  const renderer=path.join(root,'private/tools/vtuber-desktop-unpacked/out/renderer');
  const html=fs.readFileSync(path.join(renderer,'index.html'),'utf8');
  const bundle=html.match(/src="\.\/assets\/([^"/]+\.js)"/)[1];
  let source=fs.readFileSync(path.join(renderer,'assets',bundle),'utf8').replace(/\r\n/g,'\n');
  const replace=(before,after)=>{
    if(source.split(before).length!==2)throw Error(`Desktop integration anchor missing or ambiguous: ${before.slice(0,100)}`);
    source=source.replace(before,after);
  };
  replace('const Live2D = reactExports.memo(',fs.readFileSync(path.join(root,'scripts/draco-shell-component.js'),'utf8')+'\nconst Live2D = reactExports.memo(');
  replace('children: /* @__PURE__ */ jsxRuntimeExports.jsx(Live2D, {})','children: /* @__PURE__ */ jsxRuntimeExports.jsx(MaoDesktopAvatar, {})');
  replace('jsxRuntimeExports.jsx(Background, {})','jsxRuntimeExports.jsx(MaoDesktopBackground, {})');
  replace('const [showSidebar, setShowSidebar] = reactExports.useState(true);','const [showSidebar, setShowSidebar] = reactExports.useState(() => !window.maoDraco);');
  replace('children: /* @__PURE__ */ jsxRuntimeExports.jsx(Subtitle, {})','id: "mao-window-subtitle",\n              children: /* @__PURE__ */ jsxRuntimeExports.jsx(Subtitle, {})');
  replace('children: /* @__PURE__ */ jsxRuntimeExports.jsx(WebSocketStatus, {})','id: "mao-legacy-status", children: /* @__PURE__ */ jsxRuntimeExports.jsx(WebSocketStatus, {})');
  source=source.replaceAll('children: "Open LLM VTuber"','children: "Mao VTuber"');
  replace('...layoutStyles.footer,\n              zIndex: 10,','...layoutStyles.footer,\n              id: "mao-window-footer",\n              zIndex: 10,');
  replace('const live2dManager = window.getLive2DManager?.();','const live2dManager = window.maoDraco?.renderer ? {getModel:()=>window.maoDraco.audioModel} : window.getLive2DManager?.();');
  replace('const audio = new Audio(audioDataUrl);','const audio = new Audio(audioDataUrl);\n        if(window.maoDraco?.renderer)window.maoDraco.attachAudio(audio,options2);');
  replace('expressions: message.actions?.expressions || null,','expressions: message.actions?.expressions || null,\n            body: window.maoDraco?.renderer ? message.actions?.body : null,\n            motions: window.maoDraco?.renderer ? message.actions?.motions : null,\n            pose: window.maoDraco?.renderer ? message.actions?.pose : null,');
  replace('audio.addEventListener("canplaythrough", () => {\n          if (stateRef.current.aiState', 'audio.addEventListener("canplaythrough", async () => {\n          if (stateRef.current.aiState');
  replace('          console.log("Starting audio playback with lip sync");', '          if(window.maoDraco?.renderer){\n            const facingReady=await window.maoDraco.prepareAudio(audio);\n            if(!facingReady||stateRef.current.aiState==="interrupted"||!audioManager.hasCurrentAudio()){cleanup();return;}\n          }\n          console.log("Starting audio playback with lip sync");');
  replace('sendMessage(message) {\n    if (this.ws?.readyState === WebSocket.OPEN)', 'sendMessage(message) {\n    if(message.type==="interrupt-signal")window.dispatchEvent(new CustomEvent("mao-reply-event",{detail:message}));\n    if(message.type==="text-input"){const handled=window.maoDraco?.operatorFeedback?.(message.text);if(handled&&message.text.trim().startsWith("/co-the"))return;window.maoDraco?.command(message.text);}\n    if (this.ws?.readyState === WebSocket.OPEN)');
  replace('case "user-input-transcription":','case "mao-sing-command-result":\n        window.dispatchEvent(new CustomEvent("mao-sing-command-result",{detail:message}));\n        break;\n      case "user-input-transcription":\n        window.dispatchEvent(new CustomEvent("mao-reply-event",{detail:message}));\n        window.maoDraco?.command(message.text);');
  replace('case "control":','case "control":\n        window.dispatchEvent(new CustomEvent("mao-reply-event",{detail:message}));');
  replace('ref: elementRef,\n      ...inputSubtitleStyles.container,','ref: elementRef,\n      id: "mao-native-input-subtitle",\n      ...inputSubtitleStyles.container,');
  replace('const [isVisible, setIsVisible] = reactExports.useState(true);','const [isVisible, setIsVisible] = reactExports.useState(() => localStorage.getItem("mao.draco.pet-chat.v1") === "true");\n  reactExports.useEffect(()=>{localStorage.setItem("mao.draco.pet-chat.v1",String(isVisible));if(window.maoDraco)window.maoDraco.subtitleDragging=isDragging;},[isVisible,isDragging]);');
  const generated='mao-draco-shell.js';
  const output=path.join(renderer,'assets',generated);writeIfChanged(output,source);
  const init=`<script type="importmap">{"imports":{"three":"http://127.0.0.1:12393/web-tool/mao-5070/3d/vendor/three.module.js"}}</script>\n<script type="module">\nimport {createNativeBridge} from 'http://127.0.0.1:12393/web-tool/mao-5070/draco/native-bridge.mjs?v=7';\nwindow.maoDraco=createNativeBridge();\nawait import('./assets/${generated}');\n</script>`;
  const gameInit=`<script type="module">import {createWordGameOverlay} from 'http://127.0.0.1:12393/web-tool/mao-5070/draco/word-game-overlay.mjs?v=10';window.maoWordGame=createWordGameOverlay();</script>`;
  const shell=html.replace(/<script type="module" crossorigin src="\.\/assets\/[^"/]+\.js"><\/script>/,init+gameInit).replace('<title>Open-LLM-Vtuber</title>','<title>Mao VTuber</title>');
  writeIfChanged(path.join(renderer,'draco-shell.html'),shell);
  return ['out/renderer/draco-shell.html',`out/renderer/assets/${generated}`];
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  console.log(buildDracoShell(path.resolve(import.meta.dirname,'..')).join('\n'));
}
