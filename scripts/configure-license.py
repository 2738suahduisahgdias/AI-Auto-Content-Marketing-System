"""Install operator PUBLIC keys only into a customer working directory."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
p=argparse.ArgumentParser()
p.add_argument('--root',required=True)
p.add_argument('--public-keys',required=True)
a=p.parse_args()
source=Path(a.public_keys)
if source.stat().st_size>100000:raise SystemExit('公钥文件过大')
keys=json.loads(source.read_text())
if not isinstance(keys,dict) or not keys:raise SystemExit('公钥文件格式无效')
for key_id,key in keys.items():
 if not isinstance(key,str) or not key.startswith('-----BEGIN PUBLIC KEY-----') or key_id!=hashlib.sha256(key.encode()).hexdigest()[:16]:raise SystemExit('公钥或 keyId 不匹配')
 # Ed25519 SubjectPublicKeyInfo has a fixed DER prefix and 32-byte key.
 import base64
 der=base64.b64decode(''.join(key.splitlines()[1:-1]),validate=True)
 if len(der)!=44 or der[:12]!=bytes.fromhex('302a300506032b6570032100'):raise SystemExit('只支持 Ed25519 公钥')
folder=Path(a.root)/'license';folder.mkdir(parents=True,exist_ok=True)
file=folder/'public-keys.json'
old=json.loads(file.read_text()) if file.exists() else {}
for key_id,key in keys.items():
 if key_id in old and old[key_id]!=key:raise SystemExit('已有 keyId 不允许替换')
old.update(keys)
temp=file.with_suffix('.tmp');temp.write_text(json.dumps(old));temp.replace(file)
print('公钥已安装；没有导入任何私钥。')
