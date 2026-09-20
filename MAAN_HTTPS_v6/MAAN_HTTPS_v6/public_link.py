"""Shared Tailscale helpers; legacy launcher delegates to online.py."""
import json, os, re, shutil, socket, subprocess, sys, time
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)

def tailscale_path():
    found=shutil.which('tailscale')
    if found: return found
    candidate=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Tailscale'/'tailscale.exe'
    if candidate.exists(): return str(candidate)
    raise RuntimeError('Tailscale was not found. Install it and sign in on this laptop.')

def read_json(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
    if r.returncode: raise RuntimeError(r.stderr.strip() or 'Tailscale command failed.')
    return json.loads(r.stdout)

if __name__=='__main__':
    from online import main
    main()
