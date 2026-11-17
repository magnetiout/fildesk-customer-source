#!/usr/bin/env python3
"""Fail closed: release evidence is supplied by real Windows testers, never synthesized."""
import json,pathlib,sys,hashlib,importlib.util
root=pathlib.Path(__file__).resolve().parents[1]
fail=[]
for repo in ('client','server'):
    p=root/f'reports/{repo}-audit.json'
    if not p.exists() or not p.stat().st_size:fail.append(f'{repo}: vulnerability audit missing');continue
    inputs=json.loads((root/'reports/security-inputs.json').read_text())
    if hashlib.sha256((root/repo/'Cargo.lock').read_bytes()).hexdigest()!=inputs.get(repo):
        fail.append(f'{repo}: audit evidence does not match current lockfile')
    d=json.loads(p.read_text())
    if d.get('vulnerabilities',{}).get('count',1):
        if repo == 'client':
            # Preserve the complete raw audit; exact target/API exclusion is an
            # evidence-bound review, never an ignored advisory or risk waiver.
            try:
                sys.path.insert(0, str(root/'scripts'))
                import distribution_gate, security_audit_gate
                release=distribution_gate.read(root,'reports/trusted-distribution.json')
                security_audit_gate.validate(root,release,d,distribution_gate.read,
                    distribution_gate.scoped,distribution_gate.digest,distribution_gate.identity)
            except (ValueError,TypeError,KeyError,OSError,AttributeError) as error:
                fail.append(f'{repo}: security applicability blocked: {error}')
        else:
            fail.append(f'{repo}: known vulnerabilities remain; separate server review required')
spec=importlib.util.spec_from_file_location('windows_gate',root/'scripts/windows-release-gate.py')
windows_gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(windows_gate)
fail.extend(windows_gate.check(root))
spec=importlib.util.spec_from_file_location('browser_gate',root/'scripts/browser-release-gate.py')
browser_gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(browser_gate)
fail.extend(browser_gate.check(root))
spec=importlib.util.spec_from_file_location('distribution_gate',root/'scripts/distribution_gate.py')
distribution_gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(distribution_gate)
fail.extend(distribution_gate.check(root))
for line in fail:print('BLOCKED:',line)
if fail:sys.exit(1)
print('Automated technical gate passed. Legal/source/brand/network operational prerequisites remain owner responsibilities.')
