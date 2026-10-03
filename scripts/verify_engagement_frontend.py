"""Verify a public or loopback frontend without creating audience events.

Reserved all-f page identifiers are excluded by analyse_traffic.py.
"""
import argparse
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def verify(base):
    event = '/events/v1/' + 'f' * 32
    paths = {'/': 200, '/_stcore/health': 410,
             '/_stcore/host-config': 410, '/_stcore/stream': 410,
             '/analytics.mjs': 200, '/data/manifest.json': 200,
             event + '/page_view/brief/7': 204,
             event + '/article_click/pulse/30': 204,
             event + '/page_view/brief/999': 404,
             event + '/page_view/brief/7?search=secret': 400,
             '/.env': 404, '/_audit/story-audit.json': 404}
    # Cloud Run's frontend handles /healthz upstream. Test nginx health locally.
    if urlsplit(base).hostname in {'localhost', '127.0.0.1', '::1'}:
        paths['/healthz'] = 200
    results = []
    for path, expected in paths.items():
        request = urllib.request.Request(base.rstrip('/') + path, headers={'User-Agent': 'TidingsIQ-release-check/1'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                actual = response.status
                headers = response.headers
                body = response.read()
        except urllib.error.HTTPError as error:
            actual, headers, body = error.code, error.headers, error.read()
        assert actual == expected, (path, actual, expected)
        if path.startswith('/_stcore/'):
            assert headers['Cache-Control'] == 'public, max-age=86400'
        if path.startswith(event) and actual == 204:
            assert headers['Cache-Control'] == 'no-store'
            assert not body
        if path == '/':
            assert b'private measurement' in body and b'Privacy Control' in body
        if path == '/data/manifest.json':
            manifest = json.loads(body)
            assert manifest['schema_version'] == 1
            for entry in manifest['ranges'].values():
                with urllib.request.urlopen(base.rstrip('/') + '/data/' + entry['file'], timeout=30) as feed:
                    assert len(json.load(feed)) == entry['rows']
        results.append({'path': path, 'status': actual})
    request = urllib.request.Request(base.rstrip('/') + event + '/page_view/brief/7', method='POST')
    try:
        urllib.request.urlopen(request, timeout=30)
        raise AssertionError('POST unexpectedly accepted')
    except urllib.error.HTTPError as error:
        assert error.code == 405
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base')
    args = parser.parse_args()
    print(json.dumps(verify(args.base), indent=2))
