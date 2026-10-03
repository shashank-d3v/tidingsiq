import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('production',Path(__file__).parents[1]/'build_production.py')
production=importlib.util.module_from_spec(spec)
spec.loader.exec_module(production)

class ProductionBuildTests(unittest.TestCase):
    def fixture(self,root):
        for name in (*production.ASSETS,'Dockerfile','nginx.conf'):
            (root/name).write_text('public asset')
        (root/'serve.py').write_text('development server')
        (root/'data').mkdir()
        (root/'data/manifest.json').write_text('old preview data')
        (root/'.env').write_text('private configuration')
    def test_only_allowlisted_assets_enter_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            with patch.object(production,'__file__',str(root/'build_production.py')):
                production.build(root/'output')
            files={str(p.relative_to(root/'output')) for p in (root/'output').rglob('*') if p.is_file()}
            self.assertEqual(files,{*('public/'+name for name in production.ASSETS),'Dockerfile','nginx.conf'})
    def test_preview_content_blocks_build_before_output_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            for marker in ['Local preview','127.0.0.1','2026-09-29','app/static/README.md']:
                (root/'app.mjs').write_text(marker)
                with patch.object(production,'__file__',str(root/'build_production.py')),self.assertRaises(ValueError):
                    production.build(root/'output')
                self.assertFalse((root/'output').exists())
