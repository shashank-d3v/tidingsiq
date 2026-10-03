import importlib.util
from pathlib import Path
import unittest
import json

spec=importlib.util.spec_from_file_location('matcher',Path(__file__).parents[1]/'story_matcher.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def row(i,title,**extra):
    return {'article_id':str(i),'title':title,'serving_date':'2026-10-01','language':'en','source_name':'example.com','happy_factor':80,**extra}

class MatcherTests(unittest.TestCase):
    def count(self,rows):return m.cluster(rows)[1]['metrics']['story_count']
    def test_syndication_across_days_and_short_titles(self):
        rows=[row(i,'Edmunds ranks the best SUVs for parents',source_name=f'{i}.com',serving_date=f'2026-09-{25+i:02}') for i in range(6)]
        self.assertEqual(self.count(rows),1)
        self.assertEqual(m.cluster(rows),m.cluster(list(reversed(rows))))
    def test_confirmed_live_exact_copies(self):
        rows=json.loads((Path(__file__).parent/'fixtures/exact_copies.json').read_text())
        self.assertEqual(len(rows),6)
        self.assertEqual(self.count(rows),1)

    def test_normalization_and_suffix(self):
        self.assertEqual(m.title_key(row(1,'Hope &amp; Joy Opens — example.com')),'hope joy opens')
        self.assertEqual(m.title_key(row(1,'Hope Opens — Another publisher')),'hope opens another publisher')
        self.assertEqual(self.count([row(1,'Children’s new school opens today'),row(2,"Children's NEW school opens today!")]),1)
    def test_verified_alias_and_dated_syndication_identity(self):
        title='Community celebrates opening a new school today'
        self.assertEqual(m.title_key(row(1,title+' | Y102',source_name='krny.com')),title.lower())
        self.assertIn('y102',m.title_key(row(1,title+' | Y102',source_name='other.com')))
        a=row('a',title+' | Different branding 95.3',url='https://one.iheart.com/content/2026-09-01-community-celebrates-opening-a-new-school-today/',serving_date='2026-09-01')
        b=row('b',title,url='https://two.iheart.com/content/2026-09-01-community-celebrates-opening-a-new-school-today/',serving_date='2026-09-20')
        self.assertEqual(self.count([a,b]),1)
        self.assertEqual(self.count([a,{**b,'url':b['url'].replace('2026-09-01','2026-09-20')}]),2)

    def test_slug_does_not_erase_numbers_query_ids_or_negation(self):
        a=row('a','Volunteers build 2025 new community school today',url='https://a.com/volunteers-build-2025-new-community-school-today')
        b=row('b','Volunteers build 2026 new community school today',url='https://b.com/volunteers-build-2026-new-community-school-today')
        self.assertEqual(self.count([a,b]),2)
        self.assertEqual(self.count([row('a','News',url='https://a.com/article?id=1'),row('b','News',url='https://a.com/article?id=2')]),2)
        a=row('a','Volunteers build new community school today',url='https://a.com/volunteers-build-new-community-school-today')
        b=row('b','Volunteers do not build new community school today',url='https://b.com/volunteers-build-new-community-school-today')
        self.assertEqual(self.count([a,b]),2)

    def test_different_named_entities_and_tv_schedules_stay_separate(self):
        pairs=[('Award-winning Architects Continue Australian Tour In Adelaide','Award-winning Architects Continue Australian Tour In Melbourne'),
               ("Breakfast on BBC News: full details and when it's on","Breakfast on BBC Two HD: full details and when it's on")]
        for a,b in pairs:self.assertEqual(self.count([row('a',a),row('b',b)]),2)

    def test_reviewed_quality_targets(self):
        path=Path(__file__).parents[1]/'evaluate_story_matching.py'
        spec=importlib.util.spec_from_file_location('eval_matcher',path)
        evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)
        for fixture in ('story_pairs.json','story_pairs_holdout.json','story_pairs_validation.json'):
            with self.subTest(fixture=fixture):
                result=evaluation.evaluate(Path(__file__).parent/'fixtures'/fixture)
                self.assertGreaterEqual(result['precision'],.90)
                self.assertGreaterEqual(result['recall'],.95)

    def test_station_suffix_requires_hostname_evidence(self):
        station=row(1,'Community school opens today | Sunny 102.3 FM',source_name='iheart.com',url='https://sunny1023.iheart.com/content/story/')
        self.assertEqual(m.title_key(station),'community school opens today')
        self.assertIn('sunny',m.title_key({**station,'url':'https://other.iheart.com/content/story/'}))
        self.assertEqual(m.title_key(row(1,'School opens today | The Courier',source_name='thecourier.com.au')),'school opens today')

    def test_fuzzy_cluster_cannot_be_extended_past_72_hours(self):
        a='Local volunteers celebrate opening the new community garden today'
        b='Local volunteers celebrate opening a new community garden today'
        rows=[row('z',a),row('y',b,serving_date='2026-09-30'),row('x',a,serving_date='2026-09-27')]
        self.assertEqual(self.count(rows),2)

    def test_url_preserves_identity(self):
        self.assertEqual(m.url_key('https://EXAMPLE.com/News?id=1&utm_source=x#top'),'https://example.com/News?id=1')
        for other in ['https://example.com/news?id=1','https://example.com/News?id=2']:
            self.assertNotEqual(m.url_key(other),m.url_key('https://example.com/News?id=1'))
        self.assertEqual(self.count([row(1,'News',url='https://example.com/a'),row(2,'Updated',url='https://example.com/a?utm_source=x')]),1)
    def test_generic_recurring_language_and_developments(self):
        for a,b in [('Daily news','Daily news'),("The top photos of the day by AP's photojournalists", "The top photos of the day by AP's photojournalists"),('School opens in 2025','School opens in 2026'),('School wins 10 awards today','School wins 11 awards today'),('New school opens today','New school not opens today'),('Council approves new community school','Council rejects new community school')]:
            with self.subTest(a=a,b=b):self.assertEqual(self.count([row(1,a),row(2,b)]),2)
        self.assertEqual(self.count([row(1,'Community garden opens today'),row(2,'Community garden opens today',language='fr')]),2)
    def test_fuzzy_and_window(self):
        a='Local volunteers celebrate opening the new community garden today'
        b='Local volunteers celebrate opening a new community garden today'
        self.assertEqual(self.count([row(1,a),row(2,b)]),1)
        self.assertEqual(self.count([row(1,a),row(2,b,serving_date='2026-09-27')]),2)
    def test_no_transitive_chain(self):
        # Pairwise lexical changes: anchor A matches B, B matches C, A cannot match C.
        a='Local volunteers celebrate opening the new community garden today'
        b='Local volunteers celebrate opening a new community garden today'
        c='Local volunteers celebrate opening a new community gardens today'
        fa,fb,fc=[m.features(row(i,t)) for i,t in enumerate([a,b,c])]
        self.assertEqual(m.match(fa,fb,fa['time'],fa['time']),'fuzzy')
        self.assertEqual(m.match(fb,fc,fb['time'],fb['time']),'fuzzy')
        self.assertIsNone(m.match(fa,fc,fa['time'],fa['time']))
        result,_=m.cluster([row('z',a),row('y',b),row('x',c)])
        self.assertEqual(len({r['story_id'] for r in result}),2)

if __name__=='__main__':unittest.main()
