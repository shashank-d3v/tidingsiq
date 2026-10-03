"""Evaluate fixed matching rules against separately reviewed headline pairs."""
import argparse
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('matcher',Path(__file__).with_name('story_matcher.py'))
matcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(matcher)

def evaluate(path):
    data=json.loads(path.read_text());tp=fp=fn=tn=0;misses=[]
    for pair in data['pairs']:
        rows,audit=matcher.cluster([pair['a'],pair['b']])
        predicted=audit['metrics']['story_count']==1
        expected=pair['same_story']
        tp+=predicted and expected;fp+=predicted and not expected
        fn+=not predicted and expected;tn+=not predicted and not expected
        if predicted!=expected:misses.append({'expected':expected,'a':pair['a']['title'],'b':pair['b']['title']})
    precision=tp/(tp+fp) if tp+fp else 0
    recall=tp/(tp+fn) if tp+fn else 0
    return {'matcher_version':matcher.MATCHER_VERSION,'pairs':len(data['pairs']),
            'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn,
            'precision':precision,'recall':recall,'target_met':precision>=.90 and recall>=.95,
            'limitations':data['description'],'errors':misses}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,default=Path(__file__).parent/'tests/fixtures/story_pairs.json')
    args=parser.parse_args();print(json.dumps(evaluate(args.fixture),ensure_ascii=False,indent=2))
