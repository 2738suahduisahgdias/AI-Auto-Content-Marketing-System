"""Versioned, skill-grounded scene code for the existing Yingxu renderer."""
import hashlib
import json
import os
import re
from pathlib import Path

from content_workbench.domain.errors import DomainError
from content_workbench.storage.db import PROJECT_ROOT

GENERATOR_VERSION = 'yingxu-scene-code-v1'
SKILLS = PROJECT_ROOT / 'skills/remotion/remotion-best-practices'


def skill_documents():
    paths = ['SKILL.md', 'remotion-create/REFERENCE.md', 'remotion-markup/REFERENCE.md',
             'remotion-interactivity/timeline-structure.md', 'remotion-render/REFERENCE.md']
    docs = []
    for name in paths:
        path = SKILLS / name
        if not path.is_file():
            raise DomainError('REMOTION_SKILL_MISSING', '缺少 Remotion 前置规则：' + name, 503,
                              'skills', '更新到包含官方 Remotion Skills 的客户端后重试')
        text = path.read_text(encoding='utf-8')
        docs.append({'path': name, 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'content': text})
    lock = json.loads((SKILLS.parent / 'source-lock.json').read_text())
    return docs, lock


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(text, encoding='utf-8')
    os.replace(temporary, path)


def entry_source(module, video_module):
    return '''import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {VideoComposition} from %s;
import {GeneratedScene} from './GeneratedScene';
const Component = (props:any) => <VideoComposition {...props} sceneRenderer={GeneratedScene}/>;
const Root = () => <Composition id="TalkingHead" component={Component} width={1080} height={1920} fps={30} durationInFrames={30} defaultProps={{title:'',scenes:[],captions:[],durationSeconds:1}} calculateMetadata={({props}:any)=>({durationInFrames:Math.max(1,Math.ceil(props.durationSeconds*30)),width:props.outputWidth||1080,height:props.outputHeight||1920})}/>;
registerRoot(Root);
''' % json.dumps(video_module)


def prepare_scene_code(task, appearance, runtime, root, generate, validate):
    snapshot = task.get('source', {}).get('yingxu', {}).get('snapshot', {})
    shots = snapshot.get('shots') or []
    code_shots = [{'id': str(index), 'shot': {key: shot[key] for key in ('title','label','text','desc','duration','visual','motion','effect','template') if key in shot}} for index, shot in enumerate(shots)
                  if shot.get('source') == 'Remotion 代码' and not shot.get('fileId')]
    if not code_shots:
        return None
    docs, lock = skill_documents()
    request = {'contract': GENERATOR_VERSION, 'runtime_remotion': '4.0.538',
               'title': (snapshot.get('manuscript') or {}).get('title', task.get('title', '')),
               'format': snapshot.get('format'), 'appearance': appearance, 'shots': code_shots,
               'creative_brief': {key: snapshot[key] for key in ('template','reference','brand','brief') if key in snapshot},
               'skill_commit': lock['commit'], 'skill_documents': docs}
    serialized = json.dumps(request, ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(serialized.encode()).hexdigest()
    directory = Path(root) / 'assets/remotion-code' / task['content_id'] / fingerprint
    code_path, manifest_path = directory / 'GeneratedScene.tsx', directory / 'manifest.json'
    reused = manifest_path.is_file() and code_path.is_file()
    if reused:
        manifest = json.loads(manifest_path.read_text())
        code = code_path.read_text(encoding='utf-8')
        if hashlib.sha256(code.encode()).hexdigest() != manifest.get('code_sha256'):
            raise DomainError('REMOTION_CODE_CHANGED', '已保存的动画代码被外部修改，未自动覆盖', 409,
                              'code', '保留当前修改，核对项目 generated/remotion 中的代码后再操作')
        validate(code_path)
    else:
        # Incomplete generations are never accepted as a cache hit.
        directory.mkdir(parents=True, exist_ok=True)
        error = ''
        for attempt in range(2):
            prompt = serialized + ('\n上次代码检查失败，请修正后重新输出完整 TSX：' + error if error else '')
            code = generate(prompt).strip()
            if code.startswith('```') and code.endswith('```'):
                code = '\n'.join(code.splitlines()[1:-1]).strip()
            if not code or len(code.encode()) > 128 * 1024:
                raise DomainError('REMOTION_CODE_INVALID', '动画代码为空或超过大小限制', 502)
            atomic_text(code_path, code)
            try:
                validate(code_path)
                break
            except Exception as exc:
                error = str(exc)[-2000:]
                if attempt:
                    raise DomainError('REMOTION_CODE_INVALID', '动画代码检查未通过，旧成片保留：' + error,
                                      502, 'code', '检查分镜效果说明后重新生成')
        manifest = {'generator': GENERATOR_VERSION, 'input_sha256': fingerprint,
                    'code_sha256': hashlib.sha256(code.encode()).hexdigest(), 'skill_commit': lock['commit'],
                    'rules': [{key: doc[key] for key in ('path', 'sha256')} for doc in docs]}
        atomic_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    # Runtime imports resolve against the shipped dependencies, never the user CWD.
    runtime_directory = Path(runtime) / 'generated' / fingerprint
    runtime_directory.mkdir(parents=True, exist_ok=True)
    atomic_text(runtime_directory / 'GeneratedScene.tsx', code)
    video_module = os.path.relpath(Path(runtime) / 'src/VideoComposition', runtime_directory).replace(os.sep, '/')
    entry = runtime_directory / 'index.tsx'
    atomic_text(entry, entry_source(code_path, video_module))
    return {'entry': str(entry), 'manifest': str(manifest_path), 'code_sha256': manifest['code_sha256'],
            'skill_commit': lock['commit'], 'cache_hit': reused}
