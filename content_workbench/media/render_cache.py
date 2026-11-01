"""Only manage derived Yingxu render inputs, never originals or final outputs."""
import fcntl
import re
from contextlib import contextmanager
from pathlib import Path
from content_workbench.domain.errors import DomainError

NAME = re.compile(r'^[0-9a-f]{64}\.[a-z0-9]+(?:\.[0-9a-f]{32}\.staging)?$')

@contextmanager
def lease(directory):
    directory = Path(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with (directory.parent / '.yingxu-cache.lock').open('a') as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DomainError('RENDER_CACHE_BUSY', '正在渲染或整理缓存，请完成后重试', 409)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def inventory(directory, protected=()):
    directory = Path(directory)
    protected = {Path(path).resolve() for path in protected}
    entries = []
    if directory.is_dir() and not directory.is_symlink():
        for path in directory.iterdir():
            if path.is_symlink() or not path.is_file() or not NAME.fullmatch(path.name):
                continue
            entries.append((path, path.stat().st_size, path.resolve() in protected))
    return entries

def stats(directory, protected=()):
    entries = inventory(directory, protected)
    return {'bytes':sum(size for _,size,_ in entries), 'files':len(entries),
            'reclaimable_bytes':sum(size for _,size,keep in entries if not keep),
            'protected_files':sum(1 for _,_,keep in entries if keep)}

def clear(directory, protected=()):
    # Caller holds lease throughout both cleanup and all production rendering.
    removed = 0
    for path,size,keep in inventory(directory,protected):
        if not keep:
            path.unlink()
            removed += size
    return removed
