import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {createHash} from 'node:crypto';
import {existsSync} from 'node:fs';
import {cp, mkdir, readFile, readdir} from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const args = process.argv.slice(2);
const readArg = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : fallback;
};

const propsPath = readArg('--props');
const output = readArg('--output');
const compositionId = readArg('--composition-id', 'TalkingHead');
const entry = path.resolve(readArg('--entry', path.join(root, 'src/index.ts')));
if (entry !== path.join(root,'src/index.ts') && !entry.startsWith(path.join(root,'generated')+path.sep)) throw new Error('Generated entry must belong to the current runtime');
const scale = Number(readArg('--scale', '1'));
if (!Number.isFinite(scale) || scale < 0.1 || scale > 2) throw new Error('--scale must be between 0.1 and 2');
if (!propsPath || !output) throw new Error('Usage: node scripts/render.mjs --props <json> --output <mp4> [--composition-id <id>] [--scale 0.5]');

const walk = async directory => {
  const entries = await readdir(directory, {withFileTypes: true});
  const files = await Promise.all(entries.map(async entry => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(target) : target;
  }));
  return files.flat();
};

const sourceFiles = [...await walk(path.join(root, 'src')), ...(entry===path.join(root,'src/index.ts')?[]:await walk(path.dirname(entry))), path.join(root, 'remotion.config.ts'), path.join(root, 'package-lock.json')].sort();
const hash = createHash('sha256');
hash.update(entry);
for (const file of sourceFiles) hash.update(file).update(await readFile(file));
const bundleDir = path.join(root, 'out', 'bundle-cache', hash.digest('hex').slice(0, 20));
const bundleExists = existsSync(path.join(bundleDir, 'index.html'));
const serveUrl = bundleExists ? bundleDir : await bundle({
  entryPoint: entry,
  outDir: bundleDir,
  publicDir: path.join(root, 'public-static'),
  enableCaching: true,
  onProgress: progress => console.log(JSON.stringify({stage: 'bundle', progress})),
});

// Migrated task media can be added after a compiled bundle is cached.
const yingxuAssets = path.join(root, 'public-static', 'yingxu-assets');
if (existsSync(yingxuAssets)) await cp(yingxuAssets, path.join(bundleDir, 'public', 'yingxu-assets'), {recursive: true});

// Copy only files referenced by this render, never every historical task video.
const props = JSON.parse(await readFile(propsPath, 'utf8'));
const referenced = new Set();
const inspect = value => {
  if (typeof value === 'string' && value.startsWith('assets/')) referenced.add(value);
  else if (Array.isArray(value)) value.forEach(inspect);
  else if (value && typeof value === 'object') Object.values(value).forEach(inspect);
};
inspect(props);
for (const relative of referenced) {
  const source = path.resolve(root, 'public', relative);
  const base = path.resolve(root, 'public', 'assets') + path.sep;
  if (!source.startsWith(base)) throw new Error('Invalid render media path');
  const destination = path.resolve(bundleDir, 'public', relative);
  await mkdir(path.dirname(destination), {recursive: true});
  await cp(source, destination);
}

const composition = await selectComposition({serveUrl, id: compositionId, inputProps: props, timeoutInMilliseconds: 120000});
await mkdir(path.dirname(output), {recursive: true});
if (output.endsWith('.png')) {
  await renderStill({composition, serveUrl, output, inputProps: props, frame: Math.min(45, composition.durationInFrames - 1), scale});
  console.log(JSON.stringify({stage: 'completed', bundle_reused: bundleExists, bundle_dir: bundleDir, output, kind: 'still'}));
  process.exit(0);
}
await renderMedia({
  composition,
  serveUrl,
  timeoutInMilliseconds: 120000,
  codec: 'h264',
  outputLocation: output,
  inputProps: props,
  pixelFormat: 'yuv420p',
  colorSpace: 'bt709',
  scale,
  onProgress: progress => console.log(JSON.stringify({stage: 'render', progress: progress.progress})),
});
console.log(JSON.stringify({stage: 'completed', bundle_reused: bundleExists, bundle_dir: bundleDir, output}));
