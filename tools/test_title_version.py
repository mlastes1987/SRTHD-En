"""Version parsing, native title tile orientation, and preservation checks."""
import unittest
from PIL import Image,ImageDraw
from title_version import stamp,screen,number


class TitleTests(unittest.TestCase):
    def test_version_numbers_and_channels(self):
        self.assertEqual(number('0.1.3-vita-preview'),'0.1.3')
        self.assertEqual(number('1.2.0'),'1.2.0')
        for value in ['../1.2.3','v1.2','test','1.2.3\n']:
            with self.assertRaises(ValueError):number(value)

    def test_label_uses_two_lines_inset_and_native_rotated_tile(self):
        font=Image.new('L',(4096,1120),0)
        draw=ImageDraw.Draw(font)
        for y in range(0,1120,32):
            for x in range(0,4096,32):draw.rectangle((x+4,y+3,x+25,y+28),fill=255)
        original=Image.new('RGBA',(1024,1024),(20,35,60,255))
        result,report=stamp(original,'0.1.3-vita-preview',font)
        self.assertEqual(report['lines'],['pk87','eng v0.1.3'])
        bounds=report['screen_bounds']
        self.assertGreaterEqual(bounds[0],1024)
        self.assertLessEqual(bounds[2],1234)
        self.assertLessEqual(bounds[3],678)
        self.assertGreaterEqual(bounds[1],620)
        self.assertEqual(result.crop((0,0,1024,720)).tobytes(),original.crop((0,0,1024,720)).tobytes())
        self.assertEqual(screen(result).crop(bounds).getchannel('R').getextrema()[1],255)
        self.assertEqual(screen(result).crop((0,0,1024,720)).tobytes(),screen(original).crop((0,0,1024,720)).tobytes())


if __name__=='__main__':unittest.main()
