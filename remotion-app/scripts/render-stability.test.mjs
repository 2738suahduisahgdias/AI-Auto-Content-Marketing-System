import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,stat,access,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {prepareRenderAssets} from './render-assets.mjs';
import {allowRenderRequest} from './render-isolation.mjs';
test('only current referenced assets, no historical copies',async()=>{
 const root=await mkdtemp(path.join(tmpdir(),'yx-assets-'));
 try{await mkdir(path.join(root,'public-static/yingxu-assets'),{recursive:true});await mkdir(path.join(root,'public/assets'),{recursive:true});
 await writeFile(path.join(root,'public-static/yingxu-assets/needed.mp4'),'video');await writeFile(path.join(root,'public-static/yingxu-assets/history.mp4'),'old');await writeFile(path.join(root,'public/assets/narration.wav'),'audio');
 const bundle=path.join(root,'out/bundle');await prepareRenderAssets(root,bundle,{media:'yingxu-assets/needed.mp4',audio:'assets/narration.wav'});
 assert.equal((await stat(path.join(bundle,'public/yingxu-assets/needed.mp4'))).ino,(await stat(path.join(root,'public-static/yingxu-assets/needed.mp4'))).ino);
 await assert.rejects(access(path.join(bundle,'public/yingxu-assets/history.mp4')));
 await assert.rejects(prepareRenderAssets(root,bundle,{media:'yingxu-assets/../../private'}));
 }finally{await rm(root,{recursive:true,force:true})}
});
test('network permits only the render origin and local media proxy',()=>{
 const origin='http://localhost:3999';assert(allowRenderRequest(origin+'/bundle.js',origin));
 assert(!allowRenderRequest('https://example.invalid/',origin));assert(!allowRenderRequest('http://127.0.0.1:8848/api/bootstrap',origin));
 assert(allowRenderRequest(origin+'/proxy?src='+encodeURIComponent(origin+'/public/file.mp4'),origin));
 assert(!allowRenderRequest(origin+'/proxy?src='+encodeURIComponent('https://example.invalid/file'),origin));
 assert(!allowRenderRequest('file:///etc/passwd',origin));
});
