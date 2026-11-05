"""Exercise install upgrades, original restoration, and all-file preflight."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.target=self.root/'PCSG00260'
        (self.target/'sce_sys').mkdir(parents=True)
        (self.target/'sce_sys/param.sfo').write_bytes(b'test')
        self.paths=['eboot.bin','DATA/kurodata/KDataVITA.cpk']
        self.originals={p:('Original '+p).encode() for p in self.paths}
        for p,data in self.originals.items():
            dst=self.target/p;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)

    def manifest(self,version):
        rows=[]
        for i,p in enumerate(self.paths):
            out=self.root/(str(version)+'-'+str(i)+'.bin')
            out.write_bytes(('Translation '+str(version)+' '+p).encode())
            rows.append(dict(path=p,output=str(out),
                source_sha256=hashlib.sha256(self.originals[p]).hexdigest(),
                output_sha256=hashlib.sha256(out.read_bytes()).hexdigest()))
        path=self.root/('manifest-'+str(version)+'.json')
        path.write_text(json.dumps(dict(title_id='PCSG00260',files=rows)))
        return path,rows

    def run_installer(self,manifest,*args):
        return subprocess.run([sys.executable,'tools/vita_install.py','--target',str(self.target),
                               '--manifest',str(manifest),*args],capture_output=True,text=True)

    def test_upgrade_keeps_originals_and_restore_is_exact(self):
        first,_=self.manifest(1);self.assertEqual(self.run_installer(first).returncode,0)
        second,rows=self.manifest(2);result=self.run_installer(second)
        self.assertEqual(result.returncode,0,result.stderr)
        for e in rows:
            self.assertEqual((self.target/e['path']).read_bytes(),Path(e['output']).read_bytes())
            self.assertEqual((self.target/'.srw-vita-english/original'/e['path']).read_bytes(),self.originals[e['path']])
        result=self.run_installer(second,'--restore');self.assertEqual(result.returncode,0,result.stderr)
        for p in self.paths:self.assertEqual((self.target/p).read_bytes(),self.originals[p])

    def test_unknown_second_file_prevents_all_writes(self):
        manifest,_=self.manifest(1)
        (self.target/self.paths[1]).write_bytes(b'Unrecognized modification')
        result=self.run_installer(manifest)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((self.target/self.paths[0]).read_bytes(),self.originals[self.paths[0]])
        self.assertFalse((self.target/'.srw-vita-english').exists())

    def test_migration_checks_explicit_earlier_manifest(self):
        old,rows=self.manifest(1)
        for e in rows:
            original=self.target/'.srw-vita-english/original'/e['path']
            original.parent.mkdir(parents=True,exist_ok=True)
            original.write_bytes(self.originals[e['path']])
            (self.target/e['path']).write_bytes(Path(e['output']).read_bytes())
        new,_=self.manifest(2)
        result=self.run_installer(new,'--upgrade-from',str(old))
        self.assertEqual(result.returncode,0,result.stderr)

    def test_packaged_relative_payload_paths_resolve_from_manifest(self):
        manifest,rows=self.manifest(1)
        for e in rows:e['output']=Path(e['output']).relative_to(manifest.parent).as_posix()
        manifest.write_text(json.dumps(dict(title_id='PCSG00260',files=rows)))
        result=self.run_installer(manifest)
        self.assertEqual(result.returncode,0,result.stderr)
        for e in rows:
            self.assertEqual((self.target/e['path']).read_bytes(),(manifest.parent/e['output']).read_bytes())


if __name__=='__main__':unittest.main()
