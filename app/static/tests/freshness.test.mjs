import test from 'node:test';
import assert from 'node:assert/strict';
import {createFreshnessMonitor} from '../feed.mjs';
const maxAge = 36 * 60 * 60 * 1000;
function fixture(age=0) {
  const edition = {as_of:'2026-10-01',latest_data_at:'2026-10-01T00:00:00Z'};
  let time = Date.parse(edition.latest_data_at) + age, next=0;
  const timers=new Map(), listeners=new Map(), changes=[];
  const document={visibilityState:'visible',addEventListener:(name, fn)=>listeners.set(name,fn)};
  const monitor=createFreshnessMonitor({document, now:()=>time,
    onChange:(stale, data)=>changes.push([stale, data]),
    setTimeout:(fn, delay)=>{timers.set(++next,{fn,delay});return next;},
    clearTimeout:id=>timers.delete(id)});
  return {edition, monitor, timers, changes, document,
    advance:ms=>{time+=ms;}, visibility:state=>{document.visibilityState=state;listeners.get('visibilitychange')();}};
}
test('an open edition becomes stale just after 36 hours without a reload',()=>{
  const f=fixture(maxAge-1000);f.monitor.update(f.edition);
  assert.equal(f.changes.at(-1)[0],false);
  const timer=[...f.timers.values()][0];assert.equal(timer.delay,1001);
  f.advance(timer.delay);timer.fn();
  assert.equal(f.changes.at(-1)[0],true);assert.equal(f.timers.size,0);
});
test('returning to a hidden tab reevaluates age without background timers',()=>{
  const f=fixture();f.monitor.update(f.edition);f.visibility('hidden');
  assert.equal(f.timers.size,0);f.advance(maxAge+1);f.visibility('visible');
  assert.equal(f.changes.at(-1)[0],true);assert.equal(f.timers.size,0);
});
test('a refreshed edition clears the warning and replaces the prior timer',()=>{
  const f=fixture(maxAge+1);f.monitor.update(f.edition);
  assert.equal(f.changes.at(-1)[0],true);
  const newer={as_of:'2026-10-02',latest_data_at:'2026-10-02T12:00:00Z'};
  f.monitor.update(newer);assert.equal(f.changes.at(-1)[0],false);
  f.monitor.update(newer);assert.equal(f.timers.size,1);
});
test('date-only manifests and invalid timestamps fail safely',()=>{
  const f=fixture(maxAge);f.monitor.update({as_of:'2026-10-01'});
  assert.equal(f.changes.at(-1)[0],false);assert.equal([...f.timers.values()][0].delay,1);
  f.monitor.update({as_of:'2026-10-01',latest_data_at:'invalid'});
  assert.equal(f.changes.at(-1)[0],true);assert.equal(f.timers.size,0);
});
