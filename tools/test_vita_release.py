"""Check rePatch layout, private-path removal, and packaging preflight."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from vita_release import package,sha


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.rows=[]
        for path,data in [('eboot.bin',b'SCE\0test executable'),('DATA/kurodata/KDataVITA.cpk',b'CPK test archive')]:
            src=self.root/'private build with spaces'/path
            src.parent.mkdir(parents=True,exist_ok=True);src.write_bytes(data)
            self.rows.append(dict(path=path,output=str(src),source_sha256='a'*64,output_sha256=sha(data)))
        self.manifest=self.root/'build.json'
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(dict(title_id='PCSG00260',runtime_tested=False,files=self.rows)))

    def test_zip_is_self_contained_and_has_only_two_game_files(self):
        folder,path=package(self.manifest,'0.1.0-vita-preview',self.root/'release')
        self.assertIn('Vita-PCSG00260',path.name)
        self.assertTrue(path.name.endswith('-rePatch.zip'))
        with zipfile.ZipFile(path) as z:
            self.assertEqual(set(z.namelist()),{'README-PLAYTEST.txt','manifest.json','SHA256SUMS.txt',
                'rePatch/PCSG00260/eboot.bin','rePatch/PCSG00260/DATA/kurodata/KDataVITA.cpk'})
            public=z.read('manifest.json').decode()
            self.assertNotIn('private build with spaces',public)
            m=json.loads(public)
            self.assertFalse(m['hardware_tested']);self.assertFalse(m['runtime_tested'])
            for row in m['files']:
                self.assertEqual(sha(z.read(row['output'])),row['output_sha256'])
                self.assertTrue((folder/row['output']).is_file())

    def test_hash_mismatch_does_not_create_release(self):
        Path(self.rows[0]['output']).write_bytes(b'SCE\0changed build')
        with self.assertRaises(ValueError):package(self.manifest,'test',self.root/'release')
        self.assertFalse((self.root/'release').exists())

    def test_unexpected_file_or_unsafe_version_is_rejected(self):
        self.rows[1]['path']='sce_sys/param.sfo';self.save()
        with self.assertRaises(ValueError):package(self.manifest,'test',self.root/'release')
        with self.assertRaises(ValueError):package(self.manifest,'../test',self.root/'release')


if __name__=='__main__':unittest.main()
