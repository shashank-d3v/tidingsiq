"""Summarize exported Cloud Run request and engagement logs without exposing IPs.

Input is JSON from gcloud logging read --format=json. Output is aggregate JSON.
Dates are UTC half-open boundaries. No cloud queries or production writes occur.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

EVENTS = {'page_view', 'engaged', 'article_click', 'view_change', 'range_change'}
RESERVED = {'0' * 32, 'f' * 32}


def analyse(requests, events):
    paths = Counter(urlsplit(row.get('httpRequest', {}).get('requestUrl', '')).path for row in requests)
    roots = [row for row in requests if urlsplit(row.get('httpRequest', {}).get('requestUrl', '')).path == '/']
    browser = [row for row in roots if 'Mozilla/' in row.get('httpRequest', {}).get('userAgent', '')
               and not re.search('bot|headless|crawler|spider', row['httpRequest'].get('userAgent', ''), re.I)]
    accepted = []
    for row in events:
        data = row.get('jsonPayload', {})
        if (data.get('event_schema') == 'tidingsiq-engagement-v1'
            and re.fullmatch('[a-f0-9]{32}', data.get('page_id', ''))
            and data['page_id'] not in RESERVED and data.get('event') in EVENTS
            and data.get('view') in {'brief', 'pulse', 'methodology'}
            and str(data.get('days')) in {'1', '3', '7', '30'} and str(data.get('status')) == '204'):
            accepted.append(data)
    pages = {x['page_id'] for x in accepted if x['event'] == 'page_view'}
    engaged = {x['page_id'] for x in accepted if x['event'] == 'engaged'} & pages
    clickers = {x['page_id'] for x in accepted if x['event'] == 'article_click'} & pages
    return {'request_count': len(requests), 'homepage_requests': len(roots),
            'browser_like_homepage_requests': len(browser),
            'browser_like_homepage_distinct_addresses': len({x['httpRequest'].get('remoteIp') for x in browser if x['httpRequest'].get('remoteIp')}),
            'legacy_endpoint_requests': sum(n for path, n in paths.items() if path.startswith('/_stcore/')),
            'websocket_upgrades': sum(x.get('httpRequest', {}).get('status') == 101 for x in requests),
            'response_bytes_proxy': sum(int(x.get('httpRequest', {}).get('responseSize', 0)) for x in requests),
            'measured_page_loads': len(pages), 'engaged_page_loads': len(engaged),
            'page_loads_with_article_click': len(clickers),
            'article_click_events': sum(x['event'] == 'article_click' and x['page_id'] in pages for x in accepted),
            'engagement_rate': len(engaged) / len(pages) if pages else None,
            'article_click_rate': len(clickers) / len(pages) if pages else None,
            'events_by_view': dict(Counter(x['view'] for x in accepted)),
            'limitations': 'Page-lifetime IDs are not people or returning readers. Browser-like requests may include bots/self/QA. Events can be forged or blocked. Response bytes are not an egress invoice.'}


def load(path, start, end):
    rows = json.loads(Path(path).read_text()) if path else []
    def timestamp(row):
        return datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
    return [row for row in rows if (start is None or timestamp(row) >= start) and (end is None or timestamp(row) < end)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests', required=True)
    parser.add_argument('--events')
    parser.add_argument('--start', help='Inclusive UTC date, YYYY-MM-DD')
    parser.add_argument('--end', help='Exclusive UTC date, YYYY-MM-DD')
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc) if args.start else None
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc) if args.end else None
    print(json.dumps(analyse(load(args.requests, start, end), load(args.events, start, end)), indent=2))
