"""Native banner geometry and fixed-row save prompt regression checks."""
import json,struct,unittest
from pathlib import Path
from vita_ui import team_banner


def chunk(tag,payload):return tag.encode()+struct.pack('<I',len(payload))+payload


class BannerSafety(unittest.TestCase):
    def fixture(self):
        raw=bytearray(b'SSAD'+bytes(28));values={}
        for pane,properties in [('part 4',{'POSX':219000,'SCAX':1000,'SCAY':1000}),
                                ('part 5',{'TRAN':1000})]:
            raw+=chunk('NAME',pane.encode()+b'\0')
            for tag,value in properties.items():
                values[(pane,tag)]=len(raw)+24
                raw+=chunk(tag,struct.pack('<8i',1,10000,1,0,value,1,0,0))
        return bytes(raw),values

    def test_team_label_center_scale_and_duplicate_suffix(self):
        raw,offsets=self.fixture();result=team_banner(raw)
        expected=bytearray(raw)
        for key,value in [(('part 4','POSX'),271000),(('part 4','SCAX'),1600),
                          (('part 4','SCAY'),1600),(('part 5','TRAN'),0)]:
            struct.pack_into('<i',expected,offsets[key],value)
        self.assertEqual(result,bytes(expected))

    def test_unknown_or_missing_properties_rejected(self):
        raw,offsets=self.fixture();bad=bytearray(raw)
        struct.pack_into('<i',bad,offsets[('part 4','SCAX')],1200)
        with self.assertRaises(ValueError):team_banner(bytes(bad))
        with self.assertRaises(ValueError):team_banner(raw[:-40])

    def test_save_prompt_stays_on_one_native_row(self):
        root=Path(__file__).parent
        override=json.loads((root/'vita_text_overrides.json').read_text(encoding='utf8'))['0x122f20']
        self.assertEqual(override['english'],'Saving progress on this map.')
        metrics=json.loads((root/'vita_font_metrics.json').read_text())
        self.assertLessEqual(sum(int(metrics[c]['advance']*38+metrics[c]['adjust_px'])
                                 for c in override['english']),800)


if __name__=='__main__':unittest.main()
