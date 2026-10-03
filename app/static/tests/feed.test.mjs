import test from 'node:test';
import assert from 'node:assert/strict';
import {rangeRows,selectRows,summary,safeURL,escapeHTML} from '../feed.mjs';
const row=(id,day,score=80,extra={})=>({article_id:id,serving_date:day,happy_factor:score,title:'School opens',source_name:'news.test',language:'en',mentioned_country_name:'India',...extra});
const state={days:7,language:'',country:'',search:'',sort:'high'};
test('UTC cutoff is inclusive and future dates are excluded',()=>{
 const rows=[row('a','2026-09-21'),row('b','2026-09-22'),row('c','2026-09-29'),row('d','2026-09-30')];
 assert.deepEqual(rangeRows(rows,7,'2026-09-29').map(r=>r.article_id),['b','c']);
});
test('combined filters and case insensitive source search',()=>{
 const rows=[row('a','2026-09-29'),row('b','2026-09-29',90,{language:'fr'}),row('c','2026-09-29',90,{mentioned_country_name:'Canada'})];
 assert.deepEqual(selectRows(rows,{...state,language:'en',country:'India',search:'NEWS.TEST'},'2026-09-29').map(r=>r.article_id),['a']);
});
test('unknown language and geography are filterable',()=>{
 const rows=[row('a','2026-09-29',80,{language:null,mentioned_country_name:null})];
 assert.equal(selectRows(rows,{...state,language:'und',country:'Unknown'},'2026-09-29').length,1);
});
test('score order preserves date and ID tie breaks without mutating input',()=>{
 const rows=[row('a','2026-09-28',90),row('b','2026-09-29',90),row('c','2026-09-29',70)];
 assert.deepEqual(selectRows(rows,state,'2026-09-29').map(r=>r.article_id),['b','a','c']);
 assert.deepEqual(selectRows(rows,{...state,sort:'low'},'2026-09-29').map(r=>r.article_id),['c','b','a']);
 assert.equal(rows[0].article_id,'a');
});
test('no results is a valid summary',()=>assert.deepEqual(summary([]),{count:0,average:null,sources:0,countries:0}));
test('unsafe article links and injected HTML are rejected or escaped',()=>{
 for(const url of ['javascript:alert(1)','data:text/html,test','file:///etc/passwd','/relative','https://user:pass@example.com'])assert.equal(safeURL(url),'');
 assert.equal(safeURL('https://example.com/news'),'https://example.com/news');
 assert.equal(escapeHTML('<img src=x onerror="alert(1)">'),'&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
});
test('same-score ties use publication timestamp, with ingestion fallback',()=>{
 const rows=[row('z','2026-09-29',90,{published_at:'2026-09-29 00:00:00'}),row('a','2026-09-29',90,{published_at:null,ingested_at:'2026-09-29 04:00:00'}),row('b','2026-09-29',90,{published_at:'2026-09-29T02:00:00Z'})];
 assert.deepEqual(selectRows(rows,state,'2026-09-29').map(r=>r.article_id),['a','b','z']);
});
test('group after filters; representative independent of display sort',()=>{
 const rows=[row('a','2026-09-28',95,{story_id:'s',source_name:'first',mentioned_country_name:'Canada'}),row('b','2026-09-29',80,{story_id:'s',source_name:'second'}),row('c','2026-09-29',85,{story_id:'other'})];
 for(const sort of ['high','low'])assert.equal(selectRows(rows,{...state,sort},'2026-09-29').find(r=>r.story_id==='s').article_id,'a');
 for(const filter of [{country:'India'},{search:'second'},{days:0}])assert.equal(selectRows(rows,{...state,...filter},'2026-09-29').find(r=>r.story_id==='s').article_id,'b');
 assert.equal(summary(selectRows(rows,state,'2026-09-29')).count,2);
});
test('six syndicated articles render once in every supported range',()=>{
 const rows=Array.from({length:6},(_,i)=>row(String(i),'2026-10-01',80,{story_id:'edmunds',title:'Edmunds ranks the best SUVs for parents'}));
 for(const days of [1,3,7,30])assert.equal(selectRows(rows,{...state,days},'2026-10-02').length,1);
});
