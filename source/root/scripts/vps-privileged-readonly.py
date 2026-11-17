#!/usr/bin/env python3
"""Approval-only, read-only VPS metadata audit. No service, DB or file mutations."""
import json, os, pathlib, socket, subprocess, resource
if os.geteuid() != 0 or socket.gethostname() != 'ubuntu-s-1vcpu-1gb-sgp1':
    raise SystemExit('Refusing: approved VPS root context required')
os.nice(15)
resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
out = {'scope': 'read-only metadata; no PM2 CLI, env dump, database queries or changes'}
path = pathlib.Path('/root/.pm2/dump.pm2')
if path.is_file() and path.stat().st_size <= 4 * 1024 * 1024:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        out['saved_pm2_not_live_status'] = [{k: p.get(k) for k in
            ('name', 'pm_cwd', 'pm_exec_path', 'pm_out_log_path', 'pm_err_log_path')}
            for p in data if isinstance(p, dict)]
# Process identity and cwd only; argv/environment can contain secrets and are excluded.
rows = []
for entry in pathlib.Path('/proc').iterdir():
    if not entry.name.isdecimal(): continue
    try:
        comm = (entry/'comm').read_text().strip()
        if not any(x in comm.lower() for x in ('node', 'next', 'python', 'pm2', 'postgres')): continue
        rows.append({'pid': int(entry.name), 'comm': comm, 'cwd': os.readlink(entry/'cwd')})
    except (OSError, PermissionError): pass
out['process_cwd'] = rows
out['directory_usage'] = []
for path in ('/root', '/var/lib/postgresql', '/var/www/taner/server/data', '/root/.pm2/logs'):
    result = subprocess.run(['timeout','15','ionice','-c','3','du','-x','-B1','--max-depth=1',path],
        capture_output=True, text=True, timeout=18)
    out['directory_usage'].append({'path':path,'exit_code':result.returncode,
        'partial_if_nonzero':True,'output':result.stdout,'error':result.stderr})
print(json.dumps(out, indent=2))
