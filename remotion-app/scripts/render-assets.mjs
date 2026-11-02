import path from 'node:path';
import {mkdir,link,copyFile,stat,unlink} from 'node:fs/promises';
export async function prepareRenderAssets(root,bundleDir,props){
 const referenced=new Set();
 function inspect(value){
  if(typeof value==='string'&&/^(assets|yingxu-assets)\//.test(value))referenced.add(value);
  else if(Array.isArray(value))value.forEach(inspect);
  else if(value&&typeof value==='object')Object.values(value).forEach(inspect);
 }
 inspect(props);
 for(const relative of referenced){
  const base=path.resolve(root,relative.startsWith('yingxu-assets/')?'public-static':'public');
  const source=path.resolve(base,relative);
  const allowed=path.join(base,relative.split('/')[0])+path.sep;
  if(!source.startsWith(allowed))throw Error('Invalid render media path');
  const destination=path.resolve(bundleDir,'public',relative);
  if(!destination.startsWith(path.resolve(bundleDir,'public')+path.sep))throw Error('Invalid bundle asset path');
  await mkdir(path.dirname(destination),{recursive:true});
  const original=await stat(source);
  try{const existing=await stat(destination);if(existing.ino===original.ino&&existing.dev===original.dev)continue;await unlink(destination)}catch(e){if(e.code!=='ENOENT')throw e}
  try{await link(source,destination)}catch(e){if(!['EXDEV','EPERM','ENOTSUP'].includes(e.code))throw e;await copyFile(source,destination)}
 }
 return [...referenced];
}
