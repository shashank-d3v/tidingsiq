import test from 'node:test';
import assert from 'node:assert/strict';
import {createAnalytics} from '../analytics.mjs';

function fixture(overrides={}) {
  const sent=[],timers=new Map(),listeners=new Map();let sequence=0;
  const env={window:{location:{hostname:'example.run.app',search:''}},document:{visibilityState:'visible',addEventListener:(n,f)=>listeners.set(n,f)},
    navigator:{},crypto:{randomUUID:()=> '01234567-89ab-cdef-0123-456789abcdef'},
    fetch:(url,options)=>{sent.push({url,options});return Promise.resolve();},
    setTimeout:f=>{timers.set(++sequence,f);return sequence;},clearTimeout:n=>timers.delete(n),...overrides};
  return {env,sent,timers,listeners,analytics:createAnalytics(env)};
}
const context={view:'brief',days:7};
test('successful load is counted once; visibility gates engagement and interactions do not duplicate it',()=>{
  const f=fixture();f.analytics.start(context);f.analytics.start(context);
  assert.equal(f.sent.length,1);
  f.env.document.visibilityState='hidden';f.listeners.get('visibilitychange')();assert.equal(f.timers.size,0);
  f.analytics.activity(context);assert.equal(f.sent.length,1);
  f.env.document.visibilityState='visible';f.listeners.get('visibilitychange')();[...f.timers.values()][0]();
  f.analytics.interaction('article_click',context);f.analytics.interaction('article_click',context);
  assert.deepEqual(f.sent.map(x=>x.url.split('/')[4]),['page_view','engaged','article_click','article_click']);
});
test('privacy signals, automation and explicit exclusion prevent all requests',()=>{
  for(const override of [{navigator:{doNotTrack:'1'}},{navigator:{globalPrivacyControl:true}},
    {navigator:{webdriver:true}},{window:{location:{hostname:'localhost',search:''}}},
    {window:{location:{hostname:'example.run.app',search:'?analytics=off'}}}]) {
    const f=fixture(override);f.analytics.start(context);f.analytics.interaction('article_click',context);assert.equal(f.sent.length,0);
  }
});
test('dimensions are bounded, payload excludes content and requests omit credentials',()=>{
  const f=fixture();f.analytics.start({view:'private search',days:999,title:'private title',url:'https://publisher.test/secret'});
  assert.equal(f.sent[0].url,'/events/v1/0123456789abcdef0123456789abcdef/page_view/brief/7');
  assert.equal(f.sent[0].options.credentials,'omit');assert.equal(f.sent[0].options.referrerPolicy,'no-referrer');
  assert.equal(f.sent[0].options.cache,'no-store');assert.equal(f.sent[0].options.body,undefined);
  for(let i=0;i<100;i++)f.analytics.interaction('article_click',context);assert.equal(f.sent.length,50);
});
test('collection failures never fail the UI',()=>{
  const f=fixture({fetch:()=>{throw new Error('offline');}});assert.doesNotThrow(()=>f.analytics.start(context));
});
