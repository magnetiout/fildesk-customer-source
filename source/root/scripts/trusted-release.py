#!/usr/bin/env python3
"""Local immutable preparation only. No network, activation, deployment or signing.
Calls the existing single release authority before either operation.
"""
import argparse, ctypes, fcntl, hashlib, json, os, pathlib, shutil, stat, subprocess, sys, tempfile
from distribution_gate import validate, NAME
ROOT=pathlib.Path(__file__).resolve().parents[1]

def authority(root):
    result=subprocess.run([sys.executable,str(root/'scripts/release-gate.py')],cwd=root,stdin=subprocess.DEVNULL,timeout=120)
    if result.returncode:raise ValueError('authoritative release gate BLOCKED; nothing staged')

def stage(root):
    authority(root)
    record,source=validate(root)
    public_name=record.get("public_name",NAME)
    # Root must be trusted/owner controlled. Never traverse a staging symlink.
    base=root
    for part in ('build','distribution-staging'):
        base=base/part
        try:base.mkdir(mode=0o700)
        except FileExistsError:pass
        info=base.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022:raise ValueError('staging must be owned nonlink non-world/group-writable directory')
    lock=os.open(base/'.stage.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        info=os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('unsafe staging lock')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        final=base/(record['version'].replace('+','-') if record.get('distribution_mode')=='UNSIGNED' else record['version'])
        if final.exists() or final.is_symlink():raise ValueError('immutable version already exists; no overwrite')
        temp=pathlib.Path(tempfile.mkdtemp(prefix='.prepare-',dir=base))
        try:
            # O_NOFOLLOW for final component; validate rejects all parent symlinks.
            src=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                if not stat.S_ISREG(os.fstat(src).st_mode):raise ValueError('regular source required')
                h=hashlib.sha256()
                with os.fdopen(src,'rb',closefd=False) as inp,open(temp/public_name,'xb') as out:
                    for chunk in iter(lambda:inp.read(1024*1024),b''):
                        h.update(chunk);out.write(chunk)
                    out.flush();os.fsync(out.fileno())
                if h.hexdigest()!=record['sha256']:raise ValueError('source changed during copy')
            finally:os.close(src)
            if record.get('distribution_mode')=='UNSIGNED':
                license=__import__('distribution_gate').read(root,record['license_review']['path'])
                source_archive=__import__('distribution_gate').scoped(root,license['source_archive'],'artifacts')
                (temp/'source').mkdir()
                target=temp/'source/FilDesk-Corresponding-Source.tar.gz'
                shutil.copyfile(source_archive,target)
                if hashlib.sha256(target.read_bytes()).hexdigest()!=license['source_sha256']:raise ValueError('source changed during copy')
                os.chmod(target,0o444)
            # Recheck evidence and authority after copy, before publication into LOCAL staging.
            authority(root)
            current,_=validate(root)
            if current!=record:raise ValueError('receipt changed during staging')
            manifest={'schema_version':1,'kind':'fildesk-local-distribution-stage','version':record['version'],'filename':public_name,'sha256':record['sha256'],'url':record['url'],'profile':'customer','source':record['source'],'lock_sha256':record['lock_sha256'],'evidence':{'windows_verification':record['windows_verification'],'review':record['review']},'bytes':(temp/public_name).stat().st_size,'publicly_published':False,'distribution_mode':record.get('distribution_mode','SIGNED'),'signature_status':record.get('signature_status','SIGNED_VERIFIED')}
            with open(temp/'manifest.json','x') as out:
                json.dump(manifest,out,sort_keys=True,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
            for name in (public_name,'manifest.json'):os.chmod(temp/name,0o444)
            fd=os.open(temp,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
            # Cooperative sole writer holds flock. No replace/delete/rollback of existing versions.
            if final.exists() or final.is_symlink():raise ValueError('immutable destination appeared')
            # Linux atomic NOREPLACE avoids replacing even an empty concurrent dir.
            libc=ctypes.CDLL(None,use_errno=True)
            rename=libc.renameat2
            rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
            rename.restype=ctypes.c_int
            if rename(-100,os.fsencode(temp),-100,os.fsencode(final),1)!=0:
                errno=ctypes.get_errno();raise OSError(errno,os.strerror(errno))
            fd=os.open(base,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
            return manifest
        finally:
            if temp.exists():shutil.rmtree(temp) # only this process's unpublished nonce dir
    finally:os.close(lock)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('check','local-stage'))
    args=parser.parse_args()
    try:
        if args.command=='check':authority(ROOT);validate(ROOT);print('PASS: local evidence bindings only; no deployment')
        else:print(json.dumps(stage(ROOT),sort_keys=True))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('BLOCKED:',str(exc),file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(main())
