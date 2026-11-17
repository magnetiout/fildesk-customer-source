#!/usr/bin/env python3
"""Synthetic fixtures test rejection/binding/control flow, NOT real signed releases."""
import copy, datetime, hashlib, importlib.util, json, pathlib, subprocess, sys, tempfile, unittest
from unittest import mock
SCRIPTS=pathlib.Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import distribution_gate as gate
spec=importlib.util.spec_from_file_location('trusted_release',SCRIPTS/'trusted-release.py')
manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)

def sha(data):return hashlib.sha256(data).hexdigest()

class Distribution(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        for p in ('reports','config','artifacts/customer','artifacts/operator'):(self.root/p).mkdir(parents=True)
        self.artifact=b'UNIT TEST DUMMY - NOT A WINDOWS EXE OR SIGNED ARTIFACT'
        (self.root/'artifacts/customer/FilDesk.exe').write_bytes(self.artifact)
        self.digest=sha(self.artifact)
        self.put('config/trusted-distribution.json',{'schema_version':1,'expected_publisher':'CN=Unit Fixture Legal Entity'})
        self.candidate={'artifacts':{'customer':{'path':'artifacts/customer/FilDesk.exe','version':'1.2.3','sha256':self.digest,'profile':'customer'},'operator':{'sha256':sha(b'operator fixture')}}}
        self.candidate['artifacts']['customer'].update(source={'root':'1'*40,'client':'2'*40,'server':'3'*40},lock_sha256='4'*64)
        self.put('reports/windows-release-candidate.json',self.candidate)
        self.signed={'sha256':self.digest,'profile':'customer','signature_status':'Valid','trusted_public_ca':True,'publisher':'CN=Unit Fixture Legal Entity'}
        self.put('reports/signed-distribution.json',self.signed)
        self.verification={'schema_version':1,'kind':'fildesk-trusted-download-verification','execution':'windows-device','sha256':self.digest,'signature_status':'Valid','publisher':self.signed['publisher'],'code_signing_eku_valid':True,'signer_root_thumbprint':'A'*40,'timestamp_root_thumbprint':'B'*40,'signtool_sha256':'c'*64,'timestamp_present':True,'signer_chain_valid':True,'timestamp_chain_valid':True,'signtool_exit_code':0,'tester_id':'unit-person-one','windows_build':'10.0.22631','tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        self.record={'schema_version':1,'kind':'fildesk-trusted-distribution','version':'1.2.3','profile':'customer','sha256':self.digest,'artifact_path':'artifacts/customer/FilDesk.exe','public_name':gate.NAME,'url':gate.HOST+'/fildesk/releases/1.2.3/'+gate.NAME}
        self.record.update(source=self.candidate['artifacts']['customer']['source'],lock_sha256='4'*64)
        self.refresh()
    def tearDown(self):self.tmp.cleanup()
    def put(self,path,obj):
        raw=(json.dumps(obj,sort_keys=True)+'\n').encode();(self.root/path).write_bytes(raw);return sha(raw)
    def refresh(self):
        vs=self.put('reports/verification.json',self.verification)
        review={'schema_version':1,'kind':'fildesk-distribution-review','decision':'approve','sha256':self.digest,'verification_sha256':vs,'public_ca_verified':True,'rfc3161_verified':True,'reviewer':'unit-person-two'}
        rs=self.put('reports/review.json',review)
        self.record.update(windows_verification={'path':'reports/verification.json','sha256':vs},review={'path':'reports/review.json','sha256':rs})
        self.put('reports/trusted-distribution.json',self.record)
    def reject(self):self.assertTrue(gate.check(self.root))
    def test_synthetic_binding_only(self):self.assertEqual(gate.check(self.root),[])
    def test_missing(self):
        (self.root/'reports/trusted-distribution.json').unlink();self.reject()
    def test_public_url_variants(self):
        for url in (self.record['url']+'?download=1',self.record['url'].replace('https:','http:'),self.record['url'].replace('downloads.','evil.'),self.record['url'].replace('/fildesk/releases/','/releases/'),self.record['url']+'#x'):
            with self.subTest(url=url):
                self.put('reports/trusted-distribution.json',dict(self.record,url=url));self.reject()
    def test_version_traversal(self):
        for version in ('../1.2.3','1.2.3/other','1.2.3\n','latest','1.2.3%2fno'):
            self.put('reports/trusted-distribution.json',dict(self.record,version=version));self.reject()
    def test_wrong_profile_and_operator_alias(self):
        self.put('reports/trusted-distribution.json',dict(self.record,profile='operator'));self.reject()
        self.put('reports/trusted-distribution.json',dict(self.record,artifact_path='artifacts/operator/FilDesk.exe'));self.reject()
        self.put('reports/trusted-distribution.json',self.record)
        self.candidate['artifacts']['operator']['sha256']=self.digest
        self.put('reports/windows-release-candidate.json',self.candidate);self.reject()
    def test_changed_artifact(self):
        (self.root/'artifacts/customer/FilDesk.exe').write_bytes(b'changed');self.reject()
    def test_symlink_artifact(self):
        artifact=self.root/'artifacts/customer/FilDesk.exe';artifact.rename(artifact.with_suffix('.bin'));artifact.symlink_to('FilDesk.bin');self.reject()
    def test_symlink_parent(self):
        p=self.root/'artifacts/customer';p.rename(self.root/'artifacts/real');p.symlink_to('real',target_is_directory=True);self.reject()
    def test_evidence_paths(self):
        for path in ('../verification.json','reports/../config/x','/reports/x','reports//verification.json','reports/./verification.json'):
            record=copy.deepcopy(self.record);record['windows_verification']['path']=path;self.put('reports/trusted-distribution.json',record);self.reject()
    def test_duplicate_and_oversize_json(self):
        p=self.root/'reports/trusted-distribution.json'
        p.write_text('{"schema_version":1,"schema_version":1}');self.reject()
        p.write_text(' '* (2*1024*1024+1));self.reject()
    def test_stale_future_and_naive(self):
        now=datetime.datetime.now(datetime.timezone.utc)
        for dt in (now-datetime.timedelta(days=31),now+datetime.timedelta(days=1),now.replace(tzinfo=None)):
            self.verification['tested_at']=dt.isoformat();self.refresh();self.reject()
    def test_signature_requirements(self):
        for key,value in (('code_signing_eku_valid',False),('signature_status','UnknownError'),('timestamp_present',False),('signer_chain_valid',False),('timestamp_chain_valid',False),('signtool_exit_code',1),('execution','linux-fixture')):
            previous=self.verification[key];self.verification[key]=value;self.refresh();self.reject();self.verification[key]=previous
    def test_legal_publisher_unconfigured(self):
        self.put('config/trusted-distribution.json',{'schema_version':1,'expected_publisher':'UNVERIFIED'});self.reject()
    def test_evidence_tamper(self):
        (self.root/'reports/verification.json').write_text('{}');self.reject()
    def test_self_review_rejected(self):
        review=json.loads((self.root/'reports/review.json').read_text());review['reviewer']=self.verification['tester_id']
        self.record['review']['sha256']=self.put('reports/review.json',review);self.put('reports/trusted-distribution.json',self.record);self.reject()
    def test_public_ca_review_required(self):
        review=json.loads((self.root/'reports/review.json').read_text());review['public_ca_verified']=False
        self.record['review']['sha256']=self.put('reports/review.json',review);self.put('reports/trusted-distribution.json',self.record);self.reject()
    def test_gate_failure_no_stage(self):
        with mock.patch.object(manager,'authority',side_effect=ValueError('blocked')):
            with self.assertRaises(ValueError):manager.stage(self.root)
        self.assertFalse((self.root/'build').exists())
    def test_local_stage_dummy_and_immutable(self):
        with mock.patch.object(manager,'authority') as authority:
            result=manager.stage(self.root);self.assertFalse(result['publicly_published']);self.assertEqual(authority.call_count,2)
            final=self.root/'build/distribution-staging/1.2.3'
            self.assertEqual((final/gate.NAME).read_bytes(),self.artifact)
            with self.assertRaisesRegex(ValueError,'already exists'):manager.stage(self.root)
            self.assertEqual((final/gate.NAME).read_bytes(),self.artifact)
    def test_post_copy_gate_failure_rolls_back_only_nonce(self):
        base=self.root/'build/distribution-staging';base.mkdir(parents=True,mode=0o700);(self.root/'build').chmod(0o700)
        old=base/'0.9.0';old.mkdir();(old/'preserve').write_text('untouched')
        with mock.patch.object(manager,'authority',side_effect=[None,ValueError('late blocker')]) as authority:
            with self.assertRaisesRegex(ValueError,'late blocker'):manager.stage(self.root)
            self.assertEqual(authority.call_count,2)
        self.assertEqual((old/'preserve').read_text(),'untouched');self.assertFalse((base/'1.2.3').exists());self.assertEqual(list(base.glob('.prepare-*')),[])
    def test_staging_symlink_rejected(self):
        (self.root/'elsewhere').mkdir();(self.root/'build').symlink_to('elsewhere',target_is_directory=True)
        with mock.patch.object(manager,'authority'):
            with self.assertRaises(ValueError):manager.stage(self.root)
        self.assertEqual(list((self.root/'elsewhere').iterdir()),[])
    def test_actual_authority_subprocess_blocks(self):
        # Actual subprocess, deliberate failing authority; no synthetic PASS authority.
        (self.root/'scripts').mkdir();(self.root/'scripts/release-gate.py').write_text('raise SystemExit(1)')
        with self.assertRaises(ValueError):manager.stage(self.root)
        self.assertFalse((self.root/'build').exists())

    def test_source_and_lock_binding(self):
        for key,value in (('source',{'root':'a'*40}),('lock_sha256','f'*64)):
            self.put('reports/trusted-distribution.json',dict(self.record,**{key:value}));self.reject()
    def test_verification_tool_and_chain_metadata(self):
        for key in ('signtool_sha256','signer_root_thumbprint','timestamp_root_thumbprint'):
            previous=self.verification[key];self.verification[key]='';self.refresh();self.reject();self.verification[key]=previous
    def test_boolean_exit_code_is_not_integer_zero(self):
        self.verification['signtool_exit_code']=False;self.refresh();self.reject()
    def test_post_copy_receipt_change_rejected(self):
        original=manager.validate
        def changed(root):
            record,artifact=original(root)
            if changed.calls:record=dict(record,url='changed-after-gate')
            changed.calls+=1;return record,artifact
        changed.calls=0
        with mock.patch.object(manager,'authority'),mock.patch.object(manager,'validate',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'receipt changed'):manager.stage(self.root)
        base=self.root/'build/distribution-staging'
        self.assertFalse((base/'1.2.3').exists());self.assertEqual(list(base.glob('.prepare-*')),[])
    def test_no_replace_race_and_existing_directory_preserved(self):
        calls=0
        def authority(root):
            nonlocal calls
            calls+=1
            if calls==2:
                final=root/'build/distribution-staging/1.2.3';final.mkdir();(final/'owner').write_text('external-owner')
        with mock.patch.object(manager,'authority',side_effect=authority):
            with self.assertRaisesRegex(ValueError,'destination appeared'):manager.stage(self.root)
        self.assertEqual((self.root/'build/distribution-staging/1.2.3/owner').read_text(),'external-owner')
    def test_rfc3161_review_required(self):
        review=json.loads((self.root/'reports/review.json').read_text());review['rfc3161_verified']=False
        self.record['review']['sha256']=self.put('reports/review.json',review);self.put('reports/trusted-distribution.json',self.record);self.reject()
    def test_empty_artifact_rejected(self):
        (self.root/'artifacts/customer/FilDesk.exe').write_bytes(b'');self.reject()
    def test_missing_source_not_equal_missing_candidate(self):
        del self.record['source'];del self.candidate['artifacts']['customer']['source']
        self.put('reports/windows-release-candidate.json',self.candidate);self.put('reports/trusted-distribution.json',self.record);self.reject()
    def test_staging_lock_symlink_rejected(self):
        base=self.root/'build/distribution-staging';base.mkdir(parents=True,mode=0o700);(self.root/'build').chmod(0o700)
        target=self.root/'untouched';target.write_text('preserve');(base/'.stage.lock').symlink_to(target)
        with mock.patch.object(manager,'authority'):
            with self.assertRaises(OSError):manager.stage(self.root)
        self.assertEqual(target.read_text(),'preserve')

if __name__=='__main__':unittest.main()
