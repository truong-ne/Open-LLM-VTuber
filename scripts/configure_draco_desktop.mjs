import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Readable} from 'node:stream';
import {buildDracoShell,obsoleteDesktopFiles,keepDesktopEntry} from './build_draco_shell.mjs';
const root=path.resolve(import.meta.dirname,'..');
const app=path.join(root,'private/tools/vtuber-desktop-unpacked');
const main=path.join(app,'out/main/index.js'),archive=path.join(root,'private/tools/vtuber-desktop/resources/app.asar');
const shellFiles=[...buildDracoShell(root),'package.json'];
const manifestPath=path.join(app,'package.json');
const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
manifest.dependencies={'@electron-toolkit/utils':'^3.0.0','@electron-toolkit/preload':'^3.0.1'};
fs.writeFileSync(manifestPath,JSON.stringify(manifest,null,2)+'\n');
let source=fs.readFileSync(main,'utf8');
const hook='    if (require("./draco-local.cjs").loadDraco(this.window)) return;';
if(!source.includes(hook)){
  const anchor='  loadContent() {\n';
  const normalized=source.replace(/\r\n/g,'\n');
  if(normalized.split(anchor).length!==2)throw new Error('Desktop loadContent entry is ambiguous');
  source=normalized.replace(anchor,anchor+hook+'\n');fs.writeFileSync(main,source);
}
const desktopMain=fs.readFileSync(path.join(root,'scripts/draco-desktop-main.cjs'),'utf8').replace('__MAO_WORKSPACE__',JSON.stringify(root));
fs.writeFileSync(path.join(app,'out/main/draco-local.cjs'),desktopMain);
const asar=await import(pathToFileURL(path.join(root,'private/tools/desktop-patch/node_modules/@electron/asar/lib/asar.js')).href);
try{
  if(asar.extractFile(archive,path.join('out','main','index.js')).toString()===source&&asar.extractFile(archive,path.join('out','main','draco-local.cjs')).equals(Buffer.from(desktopMain))&&asar.listPackage(archive).every(relative=>keepDesktopEntry(relative.replaceAll('\\','/').replace(/^\//,'')))&&obsoleteDesktopFiles.every(relative=>{try{asar.extractFile(archive,path.normalize(relative));return false;}catch{return true;}})&&shellFiles.every(relative=>asar.extractFile(archive,path.normalize(relative)).equals(fs.readFileSync(path.join(app,relative))))){
    console.log('Draco desktop profile already installed.');process.exit(0);
  }
}catch{/* First installation has no Draco entry. */}
// Reuse the installed archive in memory. Reading thousands of extracted
// dependency files makes a two-file update needlessly slow on Windows.
const packed=fs.readFileSync(archive),raw=asar.getRawHeader(archive),entries=[];
const replacements=new Map([
  ['out/main/index.js',Buffer.from(source)],
  ['out/main/draco-local.cjs',Buffer.from(desktopMain)]
]);
for(const relative of shellFiles)replacements.set(relative,fs.readFileSync(path.join(app,relative)));
function collect(files,parent=''){
  for(const [name,entry] of Object.entries(files)){
    const relative=parent?`${parent}/${name}`:name;
    if(!keepDesktopEntry(relative))continue;
    if(entry.files){entries.push({path:relative,type:'directory',unpacked:entry.unpacked});collect(entry.files,relative);continue;}
    if(entry.link)throw new Error(`Unexpected dependency link: ${relative}`);
    let bytes=replacements.get(relative);replacements.delete(relative);
    if(!bytes){
      if(entry.unpacked)bytes=fs.readFileSync(path.join(`${archive}.unpacked`,relative));
      else{const start=8+raw.headerSize+Number(entry.offset),end=start+entry.size;if(!Number.isSafeInteger(start)||start<8+raw.headerSize||end>packed.length)throw new Error(`Invalid archive entry: ${relative}`);bytes=packed.subarray(start,end);}
    }
    entries.push({path:relative,type:'file',unpacked:!!entry.unpacked,stat:{size:bytes.length,mode:entry.executable?0o755:0o644},streamGenerator:()=>Readable.from([bytes])});
  }
}
collect(raw.header.files);
for(const [relative,bytes] of replacements)entries.push({path:relative,type:'file',unpacked:false,stat:{size:bytes.length,mode:0o644},streamGenerator:()=>Readable.from([bytes])});
await asar.createPackageFromStreams(archive,entries);
asar.uncacheAll();
if(asar.extractFile(archive,path.join('out','main','index.js')).toString()!==source)throw new Error('Desktop entry verification failed');
if(!asar.extractFile(archive,path.join('out','main','draco-local.cjs')).equals(Buffer.from(desktopMain)))throw new Error('Draco profile verification failed');
for(const relative of shellFiles)if(!asar.extractFile(archive,path.normalize(relative)).equals(fs.readFileSync(path.join(app,relative))))throw new Error(`Desktop shell verification failed: ${relative}`);
console.log('Mao-only desktop installed; obsolete original UI removed.');
