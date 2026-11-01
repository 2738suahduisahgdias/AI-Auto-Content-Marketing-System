import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {createHash} from 'node:crypto';
import {existsSync} from 'node:fs';
import {mkdir, readFile, readdir, writeFile} from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const templatesPath = path.join(root, '..', 'config', 'video_templates.json');
const outDir = path.join(root, 'public-static', 'previews');

const walk = async directory => {
  const entries = await readdir(directory, {withFileTypes: true});
  const files = await Promise.all(entries.map(async entry => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(target) : target;
  }));
  return files.flat();
};

const sourceFiles = [...await walk(path.join(root, 'src')), path.join(root, 'remotion.config.ts'), path.join(root, 'package-lock.json')].sort();
const hash = createHash('sha256');
for (const file of sourceFiles) hash.update(file).update(await readFile(file));
const bundleDir = path.join(root, 'out', 'bundle-cache', hash.digest('hex').slice(0, 20));
const serveUrl = existsSync(path.join(bundleDir, 'index.html')) ? bundleDir : await bundle({
  entryPoint: path.join(root, 'src', 'index.ts'),
  outDir: bundleDir,
  publicDir: path.join(root, 'public-static'),
  enableCaching: true,
});

const baseProps = {
  title: '真实任务，完整交付',
  durationSeconds: 6,
  scenes: [
    {id: 'preview-1', name: '减少重复工作', type: 'metric', start_seconds: 0, end_seconds: 3, asset_type: 'own', description: '企业 AI 落地先减少40%的重复工作', narration: '企业 AI 落地先减少40%的重复工作', keywords: ['企业', 'AI'], data: {metric: {value: 40, unit: '%', direction: 'down'}, items: []}, visualBeats: [{at: 0, offset_seconds: 0, action: 'scene_enter'}, {at: 2.8, offset_seconds: 2.8, action: 'metric_grow'}]},
    {id: 'preview-2', name: '三步实施路径', type: 'process', start_seconds: 3, end_seconds: 6, asset_type: 'screen_record', description: '第一步选择任务，第二步接入数据，第三步人工验收', narration: '第一步选择任务，第二步接入数据，第三步人工验收', keywords: ['任务', '数据'], data: {metric: null, items: ['选择真实任务', '接入业务数据', '人工验收结果']}, visualBeats: [{at: 3, offset_seconds: 0, action: 'scene_enter'}, {at: 5.8, offset_seconds: 2.8, action: 'process_advance'}]},
  ],
  captions: [
    {text: '先选一个真实业务任务', startMs: 0, endMs: 2800, timestampMs: null, confidence: null},
    {text: '过程可检查，结果由人确认', startMs: 3000, endMs: 5800, timestampMs: null, confidence: null},
  ],
};

const templates = JSON.parse(await readFile(templatesPath, 'utf8')).filter(item => item.status !== 'deprecated');
await mkdir(outDir, {recursive: true});
const manifest = {};
for (const template of templates) {
  const props = {...baseProps, ...template.default_props};
  const composition = await selectComposition({serveUrl, id: template.composition_id, inputProps: props});
  const name = `${template.id}-${template.version}.png`;
  await renderStill({composition, serveUrl, output: path.join(outDir, name), inputProps: props, frame: 30});
  manifest[`${template.id}@${template.version}`] = `/api/video-templates/${template.id}@${template.version}/preview`;
  console.log(JSON.stringify({template: template.id, preview: name}));
}
await writeFile(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
