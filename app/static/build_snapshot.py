"""Build public static serving files from an existing eligible-feed JSON export."""
import argparse
from datetime import date, timedelta
import gzip
import hashlib
import json
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location('story_matcher', Path(__file__).with_name('story_matcher.py'))
matcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(matcher)
FIELDS = ('article_id', 'serving_date', 'published_at', 'source_name', 'language',
          'mentioned_country_name', 'title', 'url', 'tone_score', 'happy_factor', 'ingested_at')


def build(source, output, as_of):
    rows = json.loads(source.read_text())
    clean = []
    seen = set()
    for row in rows:
        if row['article_id'] in seen:
            raise ValueError('Duplicate article ID in export')
        seen.add(row['article_id'])
        item = {key: row.get(key) for key in FIELDS}
        date.fromisoformat(item['serving_date'])
        for key in ('tone_score', 'happy_factor'):
            item[key] = float(item[key]) if item[key] is not None else None
        clean.append(item)
    lower = (as_of - timedelta(days=30)).isoformat()
    clean = [row for row in clean if lower <= row['serving_date'] <= as_of.isoformat()]
    clean, audit = matcher.cluster(clean)
    repeated, repeated_audit = matcher.cluster(list(reversed(clean)))
    if clean != repeated or audit != repeated_audit:
        raise ValueError('Non-deterministic story assignments')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'story-audit.json').write_text(json.dumps(audit, ensure_ascii=False, sort_keys=True))
    manifest = {'schema_version': 1, 'as_of': as_of.isoformat(),
                'source': 'Saved eligible Gold export', 'ranges': {}, **audit['metrics']}
    for days in (7, 30):
        lower = (as_of - timedelta(days=days)).isoformat()
        subset = [row for row in clean if lower <= row['serving_date'] <= as_of.isoformat()]
        payload = json.dumps(subset, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        digest = hashlib.sha256(payload).hexdigest()[:16]
        filename = f'feed-{days}d-{digest}.json'
        compressed = gzip.compress(payload, compresslevel=6, mtime=0)
        (output / filename).write_bytes(payload)
        (output / (filename + '.gz')).write_bytes(compressed)
        manifest['ranges'][str(days)] = {'file': filename, 'rows': len(subset),
                                       'article_count': len(subset), 'story_count': len({r['story_id'] for r in subset}),
                                       'bytes': len(payload), 'gzip_bytes': len(compressed)}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Existing eligible-only JSON export; never queries the warehouse')
    parser.add_argument('--as-of', type=date.fromisoformat, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'data')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.as_of), indent=2))
