"""Only manage derived Yingxu render inputs, never originals or final outputs."""
import fcntl
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from content_workbench.domain.errors import DomainError

_leases = threading.local()

NAME = re.compile(r'^[0-9a-f]{64}\.[a-z0-9]+(?:\.[0-9a-f]{32}\.staging)?$')

@contextmanager
def lease(directory, allow_reentry=True):
    directory = Path(directory)
    directory.parent.mkdir(parents=True, exist_ok=True)
    key = str((directory.parent / '.yingxu-cache.lock').resolve())
    held = getattr(_leases, 'held', {})
    if key in held:
        if not allow_reentry:
            raise DomainError('RENDER_CACHE_BUSY', '正在渲染或整理缓存，请完成后重试', 409)
        held[key] += 1
        try: yield
        finally: held[key] -= 1
        return
    with Path(key).open('a') as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DomainError('RENDER_CACHE_BUSY', '正在渲染或整理缓存，请完成后重试', 409)
        held[key] = 1
        _leases.held = held
        try:
            yield
        finally:
            del held[key]
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
    bundles = bundle_stats(directory, entries)
    return {'bytes':sum(size for _,size,_ in entries)+bundles, 'bundle_bytes':bundles, 'files':len(entries),
            'reclaimable_bytes':sum(size for _,size,keep in entries if not keep)+bundles,
            'protected_files':sum(1 for _,_,keep in entries if keep)}

def clear(directory, protected=()):
    # Caller holds lease throughout both cleanup and all production rendering.
    before = stats(directory, protected)['bytes']
    clear_bundles(directory, protected)
    removed = 0
    for path,size,keep in inventory(directory,protected):
        if not keep:
            path.unlink()
            removed += size
    return before - stats(directory, protected)['bytes']


def bundle_files(directory):
    root = Path(directory).parent.parent / 'out/bundle-cache'
    if root.is_symlink() or not root.is_dir(): return []
    return [p for p in root.rglob('*') if p.is_file() and not p.is_symlink()]

def bundle_stats(directory, input_entries):
    seen = {(p.stat().st_dev,p.stat().st_ino) for p,_,_ in input_entries}
    size = 0
    for p in bundle_files(directory):
        st = p.stat(); identity = (st.st_dev,st.st_ino)
        if identity not in seen: size += st.st_size; seen.add(identity)
    return size

def clear_bundles(directory, protected=()):
    import shutil
    root = Path(directory).parent.parent / 'out/bundle-cache'
    protected = {Path(p).resolve() for p in protected}
    if root.is_symlink() or not root.is_dir(): return
    for item in root.iterdir():
        if item.is_symlink(): continue
        if any(p == item.resolve() or item.resolve() in p.parents for p in protected): continue
        if item.is_dir(): shutil.rmtree(item)
        elif item.is_file(): item.unlink()
