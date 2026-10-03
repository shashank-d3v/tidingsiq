import gzip
import importlib.util
import json
from datetime import date
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('static_builder', Path(__file__).parents[1] / 'build_snapshot.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class SnapshotTests(unittest.TestCase):
    def test_ranges_compression_and_public_field_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.json'
            output = Path(folder) / 'data'
            source.write_text(json.dumps([
                {'article_id':str(i), 'serving_date':day, 'happy_factor':'75.25', 'tone_score':'4',
                 'title':f'Café {i} opens', 'url':f'https://example.com/{i}', 'private_field':'must not ship'}
                for i,day in enumerate(['2026-08-29','2026-08-30','2026-09-21','2026-09-22','2026-09-29','2026-09-30'])]))
            manifest = builder.build(source, output, date(2026,9,29))
            self.assertEqual(manifest['ranges']['7']['rows'],2)
            self.assertEqual(manifest['ranges']['30']['rows'],4)
            for entry in manifest['ranges'].values():
                raw=(output / entry['file']).read_bytes()
                zipped=(output / (entry['file']+'.gz')).read_bytes()
                self.assertEqual(gzip.decompress(zipped),raw)
                self.assertEqual(entry['gzip_bytes'],len(zipped))
                row=json.loads(raw)[0]
                self.assertEqual(row['happy_factor'],75.25)
                self.assertNotIn('private_field',row)
            self.assertEqual(builder.build(source,output,date(2026,9,29)),manifest)

    def test_duplicate_articles_fail_before_writing_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.json'
            source.write_text(json.dumps([{'article_id':'same','serving_date':'2026-09-29'}]*2))
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                builder.build(source,Path(folder)/'data',date(2026,9,29))
            self.assertFalse((Path(folder)/'data/manifest.json').exists())

    def test_syndicated_headlines_collapse_before_counts_and_compression(self):
        title = "The 2026 Victoria's Secret Fashion Show Reveals All-Women Lineup"
        base = {'serving_date':'2026-09-29', 'title':title, 'language':'en',
                'happy_factor':100, 'tone_score':4, 'published_at':'2026-09-29T10:00:00Z'}
        copies = [{**base, 'article_id':str(i), 'source_name':source,
                   'url':f'https://station{i}.{source}/story'}
                  for i,source in enumerate(['iheart.com','iheart.com','americantop40.com'])]
        copies[0]['title'] = title.upper().replace("'", '’') + '  '
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.json';output=Path(folder)/'data'
            source.write_text(json.dumps(copies))
            manifest=builder.build(source,output,date(2026,9,30))
            for entry in manifest['ranges'].values():
                self.assertEqual(entry['rows'],3)
                self.assertEqual(entry['story_count'],1)
                rows=json.loads(gzip.decompress((output/(entry['file']+'.gz')).read_bytes()))
                self.assertEqual(rows[0]['article_id'],'2')
            source.write_text(json.dumps(list(reversed(copies))))
            self.assertEqual(builder.build(source,output,date(2026,9,30)),manifest)

    def test_assignments_shared_across_ranges_with_old_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.json';output=Path(tmp)/'data'
            source.write_text(json.dumps([
                {'article_id':'old','serving_date':'2026-09-10','title':'Community celebrates opening a new garden','happy_factor':99},
                {'article_id':'new','serving_date':'2026-09-29','title':'Community celebrates opening a new garden','happy_factor':80}]))
            manifest=builder.build(source,output,date(2026,9,29))
            feeds={days:json.loads((output/entry['file']).read_text()) for days,entry in manifest['ranges'].items()}
            self.assertEqual(len(feeds['7']),1)
            self.assertEqual(feeds['7'][0]['story_id'],feeds['30'][0]['story_id'])
            self.assertEqual(manifest['ranges']['30']['story_count'],1)
            self.assertEqual(manifest['ranges']['30']['article_count'],2)

    def test_different_days_languages_and_generic_outlets_are_preserved(self):
        base={'article_id':'a','serving_date':'2026-09-29','title':'Daily news',
              'source_name':'one.com','language':'en','happy_factor':80}
        rows=[base,{**base,'article_id':'b','source_name':'two.com'},
              {**base,'article_id':'c','serving_date':'2026-09-28'},
              {**base,'article_id':'d','language':'fr'}]
        self.assertEqual(builder.matcher.cluster(rows)[1]['metrics']['story_count'],4)
        self.assertEqual(builder.matcher.cluster(rows+[{**base,'article_id':'e'}])[1]['metrics']['story_count'],5)

if __name__ == '__main__':
    unittest.main()
