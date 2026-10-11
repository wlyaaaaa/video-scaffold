import json
import tempfile
import unittest
from pathlib import Path
from pipeline.image_jobs import generate, literal


class ImageJobTests(unittest.TestCase):
    def test_windows_paths_roundtrip_and_unexpanded_paths_fail(self):
        output = r'E:\video\art\ferret\brand\2026\test.png'
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, 'images.json')
            source.write_text(json.dumps({'source': 'AI 分镜派单', 'repository': r'E:\video-scaffold',
                'images': [{'name': 'test-v01', 'purpose': '技术测试', 'prompt': '提示',
                            'references': [output], 'output': output}]}), encoding='utf-8')
            result = generate(source, Path(tmp, 'jobs'))[0]
            self.assertEqual(result.read_text(encoding='utf-8').count(output), 3)
            self.assertFalse(any(ord(c) < 32 and c != '\n' for c in result.read_text(encoding='utf-8')))
            with self.assertRaises(FileExistsError): generate(source, result.parent)
        for invalid in ['E:\vbroken.png', 'E:\2026\test.png', r'E:\art\$name.png', r'E:\art\{name}.png']:
            with self.assertRaises(ValueError): literal(invalid)
