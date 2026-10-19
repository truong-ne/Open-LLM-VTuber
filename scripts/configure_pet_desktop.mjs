// Add the repository's context-gesture adapter to an extracted desktop client.
// Usage: node scripts/configure_pet_desktop.mjs EXTRACTED_APP RESOURCES_DIR
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [appDirectory, resourcesDirectory] = process.argv.slice(2).map(value => path.resolve(value));
if (!appDirectory || !resourcesDirectory) throw new Error('Provide the extracted app and resources directories.');
const renderer = path.join(appDirectory, 'out/renderer');
const indexPath = path.join(renderer, 'index.html');
const archive = path.join(resourcesDirectory, 'app.asar');
if (!fs.existsSync(`${archive}.original`)) fs.copyFileSync(archive, `${archive}.original`);
fs.copyFileSync('web_tool/pet-context.js', path.join(renderer, 'pet-context.js'));
let html = fs.readFileSync(indexPath, 'utf8');
// Experimental Mao 5070 renderers belong only in their separate preview.
html = html.replace(/\s*<script src="\.\/mao-5070-(?:renderer|adapter)\.js"><\/script>/g, '');
if (!html.includes('src="./pet-context.js"')) {
  html = html.replace('<meta charset="UTF-8" />', '<meta charset="UTF-8" />\n    <script src="./pet-context.js"></script>');
  fs.writeFileSync(indexPath, html);
}
fs.writeFileSync(indexPath, html);
const asarPath = path.resolve('private/tools/desktop-patch/node_modules/@electron/asar/lib/asar.js');
const asar = await import(pathToFileURL(asarPath).href);
await asar.createPackageWithOptions(appDirectory, archive, { unpack: '**/*.{node,dll}' });
console.log('PET_DESKTOP_ADAPTER_INSTALLED', archive);
