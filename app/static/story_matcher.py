"""Deterministic, bounded headline clustering. No network or model dependencies."""
from array import array
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

MATCHER_VERSION = 'local-v2'
# Verified publisher-brand aliases; source: https://krny.com/contact-us/ (2026-10-02).
PUBLISHER_ALIASES = {'krny.com': {'y102'}}
TRACKING = {'fbclid', 'gclid', 'dclid', 'msclkid', 'mc_cid', 'mc_eid'}
STOPWORDS = {'a', 'an', 'and', 'the', 'of', 'for', 'in', 'at', 'on', 'to', 'with', 'by', 'is', 'as', 'its'}
# Common headline words are not protected names; person/place/company changes are.
ENTITY_NON_NAMES = STOPWORDS | set('new latest former first last next today tomorrow yesterday rare joint together makes make made bought acquired purchases purchased shares share announced announces celebrates celebrate opening opens open brings wins win major minor information press release news national world community state business mining public project senior local most more best powerful emotional tribute honors honor changes change hints phase growth now son daughter mother father parents top greatest historic wonderful special year years season court allows continue continues tour award winning actress actor singer film movie music play hospital school garden cities city countries country president minister council company group celebrity movie tv live'.split())
NEGATION = {'no', 'not', 'never', 'without', 'neither', 'nor', 'cannot'}
RECURRING = re.compile(r'\b(of the day|daily|weekly|monthly|news roundup|news digest|live updates|full details and when)\b')


def plain(value):
    return unicodedata.normalize('NFKC', html.unescape(str(value or ''))).casefold()


def publisher_names(row):
    """Brand aliases must be evidenced by this row's source or URL hostname."""
    source = plain(row.get('source_name')).removeprefix('www.')
    try:
        host = urlsplit(str(row.get('url') or '')).hostname or ''
    except ValueError:
        host = ''
    names = set(PUBLISHER_ALIASES.get(source, set()))
    for value in (source, host):
        labels = plain(value).removeprefix('www.').split('.')
        # Brand/station labels, excluding public suffixes and generic parent labels.
        for label in labels[:-1] if len(labels) > 1 else labels:
            key = re.sub(r'[^\w]', '', label)
            if len(key) >= 3 and key not in {'iheart', 'news', 'radio', 'com', 'org', 'net'}:
                names.add(key.removeprefix('the'))
    return names


def title_key(row):
    title = plain(row.get('title'))
    names = publisher_names(row)
    for separator in (' | ', ' - ', ' – ', ' — '):
        # A verified publisher can be followed by a marketing tagline.
        pieces = title.split(separator)
        for index in range(1, len(pieces)):
            compact = re.sub(r'[^\w]', '', pieces[index]).removeprefix('the')
            if compact in names:
                title = separator.join(pieces[:index])
                break
        head, sep, tail = title.rpartition(separator)
        tail_key = re.sub(r'[^\w]', '', tail).removeprefix('www')
        source_key = re.sub(r'[^\w]', '', plain(row.get('source_name'))).removeprefix('www')
        brand_keys = {tail_key.removeprefix('the')}
        for band in ('fm', 'am'):
            if tail_key.endswith(band):
                brand_keys.add(tail_key[:-len(band)].removeprefix('the'))
        # Call signs/frequency brands must occur in this hostname. Removing station
        # descriptors allows WRMF / 97.9 WRMF and WMEQ / NewsTalk WMEQ to agree.
        letters = re.sub(r'[\d_]', '', tail_key)
        letters = re.sub(r'^(newstalk|newsradio|radio|always|am|fm)', '', letters)
        letters = re.sub(r'(fm|am)$', '', letters)
        host_letters = {re.sub(r'(fm|am)$', '', re.sub(r'[\d_]', '', name)) for name in names}
        canonical_tail = re.sub(r'^(newstalk|newsradio|radio|always)', '', tail_key)
        canonical_tail = re.sub(r'(fm|am)$', '', canonical_tail)
        compact_match = any(canonical_tail == re.sub(r'(fm|am)$', '', name) or
                            (len(name) >= 4 and canonical_tail.startswith(name) and canonical_tail[len(name):].isdigit())
                            for name in names)
        station = any(len(name) >= 4 and letters.removeprefix('the') == name.removeprefix('the') for name in host_letters)
        nbc = any(name.startswith('nbc') for name in names) and bool(re.fullmatch(r'nbc\d{0,2}[a-z]{3,}', tail_key))
        if sep and (tail_key == source_key or names & brand_keys or station or nbc or compact_match):
            title = head
    # Retain the meaning of contracted negation before removing punctuation.
    title = re.sub(r"n['’]t\b", ' not', title)
    return ' '.join(re.sub(r'[^\w\s]', ' ', title).split())


def url_key(value):
    try:
        parts = urlsplit(str(value or ''))
        if parts.scheme.lower() not in ('http', 'https') or not parts.hostname:
            return ''
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.casefold().startswith('utm_') and k.casefold() not in TRACKING]
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path,
                           urlencode(query), ''))
    except ValueError:
        return ''


def syndication_slugs(row):
    """Corroborate copies using long story slugs, never generic paths/query IDs."""
    normalized = url_key(row.get('url'))
    if not normalized or urlsplit(normalized).query:
        return frozenset()
    headline = frozenset(title_key(row).split()) - STOPWORDS
    result = set()
    for part in unquote(urlsplit(normalized).path).split('/'):
        part = re.sub(r'\.(html?|aspx?)$', '', plain(part))
        part = re.sub(r'^(?:\d{4}-\d{2}-\d{2}-|\d{6,}-)', '', part)
        part = re.sub(r'-\d{7,}$', '', part)
        slug = ' '.join(re.sub(r'[^\w\s]', ' ', part).split())
        tokens = frozenset(slug.split()) - STOPWORDS
        if (len(slug.split()) >= 6 and len(tokens) >= 4 and not RECURRING.search(slug)
                and len(tokens & headline)/len(tokens) >= .75):
            result.add(slug)
    return frozenset(result)


def syndication_identity(row):
    """The same dated producer path on iHeart stations identifies one item."""
    normalized = url_key(row.get('url'))
    parts = urlsplit(normalized)
    host = parts.hostname or ''
    if (host == 'iheart.com' or host.endswith('.iheart.com')) and not parts.query:
        if re.search(r'/content/\d{4}-\d{2}-\d{2}-[^/]+/?$', parts.path):
            return 'iheart.com:' + parts.path.rstrip('/')
    return ''


def entity_tokens(row):
    normalized_tokens = frozenset(title_key(row).split())
    words = re.findall(r"[^\W_]+(?:['’][^\W_]+)?", str(row.get('title') or ''))
    names = set()
    for word in words:
        if word[0].isupper():
            normalized = plain(word).replace('’', "'").removesuffix("'s")
            if normalized not in ENTITY_NON_NAMES and not normalized.isdigit() and normalized in normalized_tokens:
                names.add(normalized)
    return frozenset(names)


def entity_clash(a, b):
    """Avoid template matches when both headlines name different entities."""
    left = a['entities'] - b['entities']
    right = b['entities'] - a['entities']
    # A possessive missing its apostrophe is a spelling variant, not a new name.
    left = {x for x in left if x.removesuffix('s') not in {y.removesuffix('s') for y in right}}
    right = {x for x in right if x.removesuffix('s') not in {y.removesuffix('s') for y in a['entities'] - b['entities']}}
    if ''.join(sorted(left)) == ''.join(sorted(right)):
        return False
    return bool(left and right)


def character_similarity(left, right):
    # Dice measures shared character evidence without double-penalizing a short
    # added phrase; the token Jaccard test still guards overall headline overlap.
    return 2*len(set(left) & set(right))/(len(left)+len(right)) if left or right else 0


def timestamp(row):
    value = row.get('published_at') or row.get('ingested_at') or row['serving_date']
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp()


def rank(row):
    return (float(row.get('happy_factor') or 0), timestamp(row), str(row['article_id']))


def features(row):
    title = title_key(row)
    tokens = frozenset(title.split())
    generic = len(title.split()) <= 2 or bool(RECURRING.search(title))
    return {'title': title, 'identity': syndication_identity(row), 'slugs': syndication_slugs(row), 'entities': entity_tokens(row), 'tokens': tokens, 'generic': generic,
            'numbers': tuple(re.findall(r'\d+', title)),
            'negation': tokens & NEGATION,
            # Three Unicode code points fit losslessly in 63 bits. Packed storage
            # keeps full-edition matching well below the publisher memory limit.
            'grams': array('Q', sorted({(ord(title[i]) << 42) | (ord(title[i+1]) << 21) | ord(title[i+2])
                                       for i in range(max(0, len(title)-2))})),
            'url': url_key(row.get('url')), 'time': timestamp(row),
            'language': plain(row.get('language') or 'und')}


def similarity(left, right):
    if not isinstance(left, (set, frozenset)):
        left, right = set(left), set(right)
    return len(left & right) / len(left | right) if left or right else 0


def match(a, b, lower, upper):
    if a['language'] != b['language']:
        return None
    if a['url'] and a['url'] == b['url']:
        return 'url'
    if a['identity'] and a['identity'] == b['identity']:
        return 'syndication_identity'
    if a['generic'] or b['generic']:
        return None
    if a['title'] == b['title']:
        return 'exact_title'
    span = max(upper, b['time']) - min(lower, b['time'])
    if (a['slugs'] & b['slugs'] and span <= 72 * 3600
            and a['numbers'] == b['numbers'] and a['negation'] == b['negation']):
        return 'syndication_slug'
    if (min(len(a['title'].split()), len(b['title'].split())) < 4
            or min(len(a['tokens'] - STOPWORDS), len(b['tokens'] - STOPWORDS)) < 4
            or span > 72 * 3600
            or a['numbers'] != b['numbers'] or a['negation'] != b['negation']
            or entity_clash(a, b)
            or re.search(r'\b(jobs|coupon codes|major and minor information)\b', a['title']+' '+b['title'])):
        return None
    if similarity(a['tokens'], b['tokens']) >= .72 and character_similarity(a['grams'], b['grams']) >= .85:
        return 'fuzzy'
    return None


def cluster(rows):
    """Return copied rows with story IDs and a private, reproducible audit."""
    ordered = sorted(rows, key=rank, reverse=True)
    clusters = []
    urls, titles, tokens, slugs, identities = (defaultdict(set) for _ in range(5))
    result, reasons = [], Counter()
    for row in ordered:
        f = features(row)
        language = f['language']
        candidates = set(urls[(language, f['url'])]) if f['url'] else set()
        if f['identity']:
            candidates.update(identities[(language, f['identity'])])
        if not f['generic']:
            for slug in f['slugs']:
                candidates.update(slugs[(language, slug)])
            candidates.update(titles[(language, f['title'])])
            for token in f['tokens']:
                candidates.update(tokens[(language, token)])
        chosen, reason = None, 'anchor'
        for index in sorted(candidates):
            c = clusters[index]
            reason_match = match(c['features'], f, c['lower'], c['upper'])
            if reason_match and c.get('has_bounded') and max(c['upper'], f['time']) - min(c['lower'], f['time']) > 72 * 3600:
                reason_match = None
            if reason_match:
                chosen, reason = index, reason_match
                break
        if chosen is None:
            chosen = len(clusters)
            story_id = hashlib.sha256(f"{MATCHER_VERSION}:{row['article_id']}".encode()).hexdigest()
            clusters.append({'story_id': story_id, 'anchor_id': row['article_id'],
                             'features': f, 'lower': f['time'], 'upper': f['time'], 'members': []})
            if f['url']:
                urls[(language, f['url'])].add(chosen)
            if f['identity']:
                identities[(language, f['identity'])].add(chosen)
            if not f['generic']:
                for slug in f['slugs']:
                    slugs[(language, slug)].add(chosen)
                titles[(language, f['title'])].add(chosen)
                if len(f['title'].split()) >= 4:
                    for token in f['tokens']:
                        tokens[(language, token)].add(chosen)
        c = clusters[chosen]
        c['lower'], c['upper'] = min(c['lower'], f['time']), max(c['upper'], f['time'])
        c['members'].append({'article_id': row['article_id'], 'reason': reason})
        c['has_bounded'] = c.get('has_bounded', False) or reason in {'fuzzy', 'syndication_slug'}
        reasons[reason] += 1
        result.append({**row, 'story_id': c['story_id']})
    metrics = {'matcher_version': MATCHER_VERSION, 'article_count': len(rows),
               'story_count': len(clusters), 'suppression_ratio': 1-len(clusters)/len(rows) if rows else 0,
               'exact_match_count': reasons['url']+reasons['exact_title'], 'fuzzy_match_count': reasons['fuzzy'], 'syndication_match_count': reasons['syndication_slug']+reasons['syndication_identity'],
               'largest_cluster': max((len(c['members']) for c in clusters), default=0)}
    audit = {'metrics': metrics, 'clusters': [{k: c[k] for k in ('story_id', 'anchor_id', 'members')} for c in clusters]}
    return result, audit
