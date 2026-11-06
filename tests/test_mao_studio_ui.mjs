import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
let subtitleText='Thinking...',spoken='',sync,effect=false;
const jsx=(type,props)=>({type,props});
const bridge={audio:null,payload:null};
const context={jsxRuntimeExports:{jsx},useSubtitleDisplay:()=>({isLoaded:true,subtitleText}),useSubtitle:()=>({showSubtitle:true}),DEFAULT_SUBTITLE:{text:'Default greeting'},window:{maoDraco:bridge},setInterval:fn=>{sync=fn;return 1;},clearInterval(){},reactExports:{useState:()=>[spoken,fn=>{spoken=typeof fn==='function'?fn(spoken):fn;}],useEffect:fn=>{if(!effect){effect=true;fn();}}}};
vm.createContext(context);
const source=fs.readFileSync('scripts/mao-studio-component.js','utf8');
vm.runInContext(source+';globalThis.ui={MaoDesktopSubtitle};',context);
assert.equal(context.ui.MaoDesktopSubtitle(),null);
subtitleText='giá trị.';sync();assert.equal(context.ui.MaoDesktopSubtitle(),null,'stale text must stay hidden while idle');
bridge.audio={paused:true,ended:false};bridge.payload={displayText:{text:'Lời đang phát.'}};sync();assert.equal(context.ui.MaoDesktopSubtitle(),null,'queued speech must not show a caption');
bridge.audio.paused=false;sync();assert.equal(context.ui.MaoDesktopSubtitle().props.children.props.children,'Lời đang phát.');
bridge.audio.ended=true;sync();assert.equal(context.ui.MaoDesktopSubtitle(),null,'caption must clear at audio end');
bridge.audio.ended=false;bridge.audio.paused=true;sync();assert.equal(context.ui.MaoDesktopSubtitle(),null,'paused or interrupted audio must not leave text');
assert.ok(!source.includes('MaoStudioHeader'));
assert.ok(!source.includes('useTextInput'));

console.log('Mao livestream: no header/composer, dialogue captions passed.');
if(process.argv.includes('--layout-fixture')){
  fs.writeFileSync('logs/mao-studio-layout-fixture.html','<main><div id="mao-original-avatar"></div><div id="mao-window-subtitle" style="position:absolute;left:50%;transform:translateX(-50%)"><div class="mao-caption"><p>Mao đang nghe đây! Hôm nay có chuyện gì vui không? Kể một chút đi, Mao muốn nghe câu chuyện của bạn.</p></div></div></main>');
}
