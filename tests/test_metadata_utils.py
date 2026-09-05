import os
import shutil
import tempfile
import unittest

from mutagen.id3 import ID3
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image

from metadata_utils import set_audio_metadata


class TestMetadataUtils(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mp3_path = os.path.join(self.temp_dir.name, 'test.mp3')
        self.m4a_path = os.path.join(self.temp_dir.name, 'test.m4a')
        self.jpg_path = os.path.join(self.temp_dir.name, 'test_cover.jpg')
        self.png_path = os.path.join(self.temp_dir.name, 'test_cover.png')

        # Copy dummy audio files
        fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
        shutil.copy(os.path.join(fixtures_dir, 'dummy.mp3'), self.mp3_path)
        shutil.copy(os.path.join(fixtures_dir, 'dummy.m4a'), self.m4a_path)

        # Create dummy image files
        Image.new('RGB', (10, 10), color='red').save(self.jpg_path, 'JPEG')
        Image.new('RGB', (10, 10), color='blue').save(self.png_path, 'PNG')

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_set_metadata_mp3(self):
        set_audio_metadata(
            self.mp3_path,
            title='Test Title MP3',
            artist='Test Artist MP3',
            album='Test Album MP3',
            artwork_path=self.jpg_path
        )

        tags = ID3(self.mp3_path)
        self.assertEqual(tags.get('TIT2').text[0], 'Test Title MP3')
        self.assertEqual(tags.get('TPE1').text[0], 'Test Artist MP3')
        self.assertEqual(tags.get('TALB').text[0], 'Test Album MP3')

        apic = tags.getall('APIC')[0]
        self.assertEqual(apic.mime, 'image/jpeg')
        self.assertEqual(apic.type, 3) # front cover
        with open(self.jpg_path, 'rb') as f:
            self.assertEqual(apic.data, f.read())

    def test_set_metadata_m4a_png(self):
        set_audio_metadata(
            self.m4a_path,
            title='Test Title M4A',
            artist='Test Artist M4A',
            album='Test Album M4A',
            artwork_path=self.png_path
        )

        audio = MP4(self.m4a_path)
        self.assertEqual(audio.tags['\xa9nam'][0], 'Test Title M4A')
        self.assertEqual(audio.tags['\xa9ART'][0], 'Test Artist M4A')
        self.assertEqual(audio.tags['\xa9alb'][0], 'Test Album M4A')

        covr = audio.tags['covr'][0]
        self.assertEqual(covr.imageformat, MP4Cover.FORMAT_PNG)
        with open(self.png_path, 'rb') as f:
            self.assertEqual(bytes(covr), f.read())

    def test_set_metadata_missing_file(self):
        # Should not crash if file doesn't exist
        missing_path = os.path.join(self.temp_dir.name, 'missing.mp3')
        set_audio_metadata(missing_path, title='Title')
        self.assertFalse(os.path.exists(missing_path))

if __name__ == '__main__':
    unittest.main()
