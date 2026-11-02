import shutil
from content_workbench.domain.errors import DomainError

def stream_upload(stream, length, path):
    if length <= 0:
        raise DomainError("INVALID_UPLOAD_SIZE", "文件为空", 413)
    if shutil.disk_usage(path.parent).free < length + 64 * 1024 ** 2:
        raise DomainError("UPLOAD_DISK_FULL", "磁盘空间不足，请清理缓存或更换素材磁盘", 413)
    created = False
    try:
        with path.open("xb") as output:
            created = True
            remaining = length
            while remaining:
                block = stream.read(min(1024 * 1024, remaining))
                if not block:
                    raise DomainError("INCOMPLETE_UPLOAD", "上传中断，请重新上传", 400)
                output.write(block)
                remaining -= len(block)
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise
