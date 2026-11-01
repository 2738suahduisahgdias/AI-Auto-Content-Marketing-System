"""Disposable 720p preview; never substitute into final render or delivery."""
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from content_workbench.storage.db import file_hash
from content_workbench.media.probe import probe
from content_workbench.domain.errors import DomainError


def prepare(source, directory, capacity_bytes):
    source, directory = Path(source), Path(directory)
    digest = file_hash(source)
    key = hashlib.sha256(('yingxu-proxy-v1:' + digest).encode()).hexdigest()
    output, manifest = directory/(key+'.mp4'), directory/(key+'.json')
    if output.is_file() and manifest.is_file():
        try:
            info=json.loads(manifest.read_text())
            if info['source_sha256']==digest and info['proxy_sha256']==file_hash(output):
                return output
        except (ValueError,KeyError,OSError):
            pass
    source_info=probe(source)
    if not any(s.get('codec_type')=='video' for s in source_info.get('streams',[])):
        raise DomainError('PROXY_NOT_VIDEO','该素材不是视频',422)
    directory.mkdir(parents=True,exist_ok=True)
    # Bounded H264 bit rate and audio; conservative reservation before encoding.
    reserve=int(source_info['duration_seconds']*400000)+16*1024**2
    if reserve > capacity_bytes or shutil.disk_usage(directory).free < reserve+64*1024**2:
        raise DomainError('PROXY_SPACE','代理缓存空间不足，将使用原片预览',409)
    temporary=directory/(key+'.mp4.'+uuid.uuid4().hex+'.staging')
    try:
        command=[shutil.which('ffmpeg') or 'ffmpeg','-v','error','-y','-i',str(source),'-map','0:v:0','-map','0:a:0?',
                 '-vf',"scale=w='min(720,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",'-c:v','libx264','-preset','veryfast','-crf','25','-maxrate','2500k','-bufsize','5000k','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart','-f','mp4',str(temporary)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=1800)
        if result.returncode:raise DomainError('PROXY_FAILED','代理生成失败，将使用原片预览',502)
        info=probe(temporary,'video/mp4')
        audio=lambda data:any(s.get('codec_type')=='audio' for s in data.get('streams',[]))
        if abs(info['duration_seconds']-source_info['duration_seconds'])>.15 or audio(info)!=audio(source_info):
            raise DomainError('PROXY_INVALID','代理音轨或时长不一致，将使用原片预览',409)
        if file_hash(source)!=digest:raise DomainError('PROXY_SOURCE_CHANGED','生成代理时原素材发生变化',409)
        if temporary.stat().st_size>capacity_bytes:raise DomainError('PROXY_SPACE','代理超过缓存容量',409)
        record={'source_sha256':digest,'proxy_sha256':file_hash(temporary),'duration_seconds':info['duration_seconds']}
        temporary.replace(output)
        manifest.write_text(json.dumps(record))
        return output
    finally:
        temporary.unlink(missing_ok=True)
