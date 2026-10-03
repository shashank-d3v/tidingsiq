import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('traffic', Path(__file__).parents[1] / 'analyse_traffic.py')
traffic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(traffic)


class TrafficTests(unittest.TestCase):
    def event(self, name, page='a' * 32, status=204):
        return {'jsonPayload': {'event_schema': 'tidingsiq-engagement-v1', 'page_id': page,
                               'event': name, 'view': 'brief', 'days': '7', 'status': status}}

    def test_reserved_invalid_and_orphan_events_do_not_inflate_rates(self):
        events = [self.event('page_view'), self.event('page_view'), self.event('engaged'),
                  self.event('engaged'), self.event('article_click'),
                  self.event('article_click'), self.event('page_view', 'f' * 32),
                  self.event('page_view', status=400), self.event('engaged', 'b' * 32),
                  self.event('article_click', 'b' * 32)]
        result = traffic.analyse([], events)
        self.assertEqual(result['measured_page_loads'], 1)
        self.assertEqual(result['engaged_page_loads'], 1)
        self.assertEqual(result['page_loads_with_article_click'], 1)
        self.assertEqual(result['article_click_events'], 2)
        self.assertEqual(result['engagement_rate'], 1)

    def test_empty_rates_are_unknown_and_addresses_are_not_disclosed(self):
        rows = [{'httpRequest': {'requestUrl': 'https://example.run.app/', 'userAgent': 'Mozilla/5.0',
                                 'remoteIp': '192.0.2.1', 'responseSize': 100}},
                {'httpRequest': {'requestUrl': 'https://example.run.app/_stcore/health'}}]
        result = traffic.analyse(rows, [])
        self.assertIsNone(result['engagement_rate'])
        self.assertEqual(result['legacy_endpoint_requests'], 1)
        self.assertEqual(result['browser_like_homepage_distinct_addresses'], 1)
        self.assertNotIn('192.0.2.1', str(result))


if __name__ == '__main__':
    unittest.main()
