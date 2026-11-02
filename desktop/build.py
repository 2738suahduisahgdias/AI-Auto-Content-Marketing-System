"""Build an isolated Intel Mac .app and DMG from tracked source + locked dependencies."""
import argparse
import json
import os
import plistlib
import platform
import shutil
import subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--public-keys',required=True);p.add_argument('--assemble-only',action='store_true');a=p.parse_args()
repo=Path(__file__).resolve().parents[1];out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
stage=out/'resources';stage.mkdir(exist_ok=True)
for folder in ('migrations','agents','workers','templates','content_workbench','config','skills'):
    if (repo/folder).is_dir():shutil.copytree(repo/folder,stage/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
(stage/'data').mkdir(exist_ok=True);shutil.copyfile(repo/'data/seed.example.json',stage/'data/seed.example.json')
shutil.copytree(repo/'web/react-dist',stage/'web/react-dist',dirs_exist_ok=True)
shutil.copytree(repo/'web',stage/'web',dirs_exist_ok=True,ignore=shutil.ignore_patterns('react-dist'))
for name in ('src','scripts','public','public-static'):
    source=repo/'remotion-app'/name
    if source.is_dir():shutil.copytree(source,stage/'remotion-app'/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('yingxu-assets'))
renderer=stage/'remotion-app/scripts/render.mjs'
renderer.write_text(renderer.read_text().replace('enableCaching: true','enableCaching: false'))
for name in ('package.json','package-lock.json','remotion.config.ts','tsconfig.json'):
    if (repo/'remotion-app'/name).exists():shutil.copyfile(repo/'remotion-app'/name,stage/'remotion-app'/name)
if not (stage/'dependencies.complete').exists():
    print('Copying locked Remotion runtime',flush=True)
    subprocess.run(['/usr/bin/rsync','-a','--exclude=.cache','--exclude=*.map','--exclude=*.tsbuildinfo',str((repo/'remotion-app/node_modules').resolve())+'/',str(stage/'remotion-app/node_modules')+'/'],check=True)
    for mapping in (stage/'remotion-app/node_modules').rglob('*.map'):mapping.unlink()
    shutil.rmtree(stage/'remotion-app/node_modules/.cache',ignore_errors=True)
    (stage/'dependencies.complete').write_text('complete')
if a.public_keys:
    subprocess.run([os.sys.executable,str(repo/'scripts/configure-license.py'),'--root',str(stage),'--public-keys',a.public_keys],check=True)
os.environ['PYINSTALLER_CONFIG_DIR']=str(out/'pyinstaller-cache')
command=[os.sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--name','YingxuService','--distpath',str(out/'engine'),'--workpath',str(out/'build'),'--specpath',str(out),'--paths',str(repo),'--collect-submodules','content_workbench','--hidden-import','app','--collect-submodules','PIL','--collect-submodules','xlrd','--collect-submodules','playwright']
# Keep vendor Chromium intact: PyInstaller must not rewrite its Mach-O load commands.
for item in stage.iterdir():
    if item.name == 'dependencies.complete':continue
    if item.name == 'remotion-app':
        for child in item.iterdir():
            if child.name != 'node_modules':command += ['--add-data',str(child)+':'+('remotion-app/'+child.name if child.is_dir() else 'remotion-app')]
    else:command += ['--add-data',str(item)+':'+item.name]
for binary in ('node','ffmpeg','ffprobe','openssl'):
    path=shutil.which(binary)
    if not path:raise SystemExit('缺少打包依赖 '+binary)
    command+=['--add-binary',path+':bin']
command.append(str(repo/'desktop/entry.py'))
if not a.assemble_only:subprocess.run(command,cwd=repo,check=True)
else:
    for item in (stage/'remotion-app').iterdir():
        if item.name=='node_modules':continue
        target=out/'engine/YingxuService/_internal/remotion-app'/item.name
        if item.is_dir():shutil.copytree(item,target,dirs_exist_ok=True)
        else:shutil.copyfile(item,target)
def clone(source,destination):
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.is_symlink():destination.unlink()
    elif destination.exists():shutil.rmtree(destination)
    result=subprocess.run(['/bin/cp','-cRp',str(source),str(destination)])
    if result.returncode:subprocess.run(['/usr/bin/ditto','--noqtn',str(source),str(destination)],check=True)
if not a.assemble_only or (out/'engine/YingxuService/_internal/remotion-app/node_modules').is_symlink():
    clone((stage/'remotion-app/node_modules').resolve(),out/'engine/YingxuService/_internal/remotion-app/node_modules')
app=out/'映序工作台.app';contents=app/'Contents';(contents/'MacOS').mkdir(parents=True,exist_ok=True)
clone(out/'engine/YingxuService',contents/'Resources/engine')
# A native launcher can be sealed as a Mac application; shell entry points cannot.
launcher=contents/'MacOS/launcher'
launcher_source=out/'launcher.c'
launcher_source.write_text(r'''#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc, char **argv) {
 char raw[PATH_MAX], resolved[PATH_MAX], target[PATH_MAX]; uint32_t size=sizeof(raw);
 if (_NSGetExecutablePath(raw,&size)!=0 || !realpath(raw,resolved)) return 1;
 char *slash=strrchr(resolved,'/'); if (!slash) return 1; *slash=0;
 snprintf(target,sizeof(target),"%s/../Resources/engine/YingxuService",resolved);
 argv[0]=target; execv(target,argv); perror("Yingxu launch"); return 1;
}
''')
subprocess.run(['/usr/bin/clang','-Os',str(launcher_source),'-o',str(launcher)],check=True)
shutil.copyfile(repo/'desktop/assets/Workbench.icns',contents/'Resources/Workbench.icns')
with (contents/'Info.plist').open('wb') as f:plistlib.dump({'CFBundleExecutable':'launcher','CFBundleIconFile':'Workbench.icns','CFBundleIdentifier':'com.yingxu.workbench','CFBundleName':'映序工作台','CFBundleVersion':'0.1.3.4','CFBundleShortVersionString':'0.1.3.4','NSAppleEventsUsageDescription':'用于找到并唤起已有的 Chrome 工作台标签，避免重复打开页面。','CFBundlePackageType':'APPL','LSMinimumSystemVersion':subprocess.check_output(['sw_vers','-productVersion'],text=True).strip().split('.')[0]+'.0'},f)
subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
volume=out/'volume';volume.mkdir(exist_ok=True)
clone(app,volume/app.name)
if not (volume/'Applications').is_symlink():(volume/'Applications').symlink_to('/Applications')
(volume/'安装说明.txt').write_text('将映序工作台拖入 Applications。首次启动选择本地或外置硬盘工作区。\n本构建为 Intel Mac 测试版，未经过 Apple Developer ID 公证；不是对外正式发布包。\n不包含私钥、客户数据、平台登录或模型密钥。\n')
subprocess.run(['hdiutil','create','-volname','映序工作台','-srcfolder',str(volume),'-ov','-format','UDZO',str(out/('Yingxu-Mac-'+platform.machine()+'.dmg'))],check=True)
print(app)
