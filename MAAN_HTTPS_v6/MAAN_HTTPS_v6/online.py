"""Start public MAAN using its existing background Funnel, or set up an empty one."""
import os, re, socket, subprocess, sys
from pathlib import Path
from public_link import tailscale_path, read_json
ROOT=Path(__file__).resolve().parent

def check_config(config, name):
    endpoint=name+':443'
    web=config.get('Web',{})
    handler=web.get(endpoint,{}).get('Handlers',{}).get('/',{})
    if handler.get('Proxy')=='http://127.0.0.1:8080' and config.get('AllowFunnel',{}).get(endpoint) is True:
        return 'reuse'
    if any(config.get(k) for k in ('Web','TCP','Foreground','AllowFunnel')):
        raise RuntimeError('A different or foreground Tailscale configuration exists. It was not changed. Run tailscale funnel status and share its output.')
    return 'create'

def main():
    os.chdir(ROOT)
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',8080))==0:
            raise RuntimeError('Port 8080 is already in use. Stop the previous MAAN server window with Ctrl+C, then start this launcher again. Do not stop Ollama or Tailscale.')
    ts=tailscale_path()
    status=read_json([ts,'status','--json'])
    if status.get('BackendState')!='Running':raise RuntimeError('Open Tailscale and connect first.')
    name=status.get('Self',{}).get('DNSName','').rstrip('.').lower()
    if not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+\.ts\.net',name):raise RuntimeError('Tailscale did not provide a valid HTTPS name.')
    config=read_json([ts,'funnel','status','--json'])
    action=check_config(config,name)
    if subprocess.run([sys.executable,'app.py','--ensure-user']).returncode:raise RuntimeError('An enabled MAAN account is required.')
    if action=='create':
        print('Setting up the public link. Follow any Tailscale approval link shown below.',flush=True)
        if subprocess.run([ts,'funnel','--bg','--https=443','http://127.0.0.1:8080']).returncode:raise RuntimeError('Funnel could not start. Review the message above.')
        if check_config(read_json([ts,'funnel','status','--json']),name)!='reuse':raise RuntimeError('Funnel did not confirm the MAAN route.')
    url='https://'+name
    env=os.environ.copy();env['MAAN_PUBLIC_ORIGIN']=url
    (ROOT/'YOUR_MAAN_LINK.txt').write_text(url+'\n',encoding='utf-8')
    print('\nMAAN v6 - public mode\nYour link: '+url+'\nKeep this window open. Test on your phone to confirm access.\n',flush=True)
    # The background Funnel is retained; the local app stops when this process ends.
    child=subprocess.Popen([sys.executable,'app.py','--public'],env=env)
    try:return child.wait()
    finally:
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()

if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:print('\nMAAN stopped. The public route remains configured for next launch.')
    except (RuntimeError,ValueError,OSError,subprocess.SubprocessError) as e:
        print('Could not start MAAN:',e);sys.exit(1)
