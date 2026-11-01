"""Customer entry point: retain the original app, require offline license for writes."""
import os
import runpy
from pathlib import Path
import sys
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
os.environ['CONTENT_AGENT_LICENSE_MODE'] = 'required'
runpy.run_path(str(repo/'app.py'), run_name='__main__')
