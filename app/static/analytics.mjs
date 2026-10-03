// Same-origin, page-lifetime measurement. No cookies or persistent visitor ID.
export function createAnalytics({window:w=window, document:d=document, navigator:n=navigator,
  crypto:c=crypto, fetch:send=fetch, setTimeout:later=setTimeout, clearTimeout:cancel=clearTimeout}={}) {
  const disabled = n.webdriver || n.globalPrivacyControl || n.doNotTrack==='1' ||
    w.doNotTrack==='1' || !w.location.hostname.endsWith('.run.app') ||
    new URLSearchParams(w.location.search).get('analytics')==='off';
  let id, started=false, engaged=false, timer, count=0;
  let context={view:'brief',days:7};
  if(!disabled) { try { id=c.randomUUID().replaceAll('-',''); } catch { /* fail closed */ } }
  function event(name, next=context) {
    context=next;
    if(!id || count>=50 || !['page_view','engaged','article_click','view_change','range_change'].includes(name))return;
    const view=['brief','pulse','methodology'].includes(context.view)?context.view:'brief';
    const days=[1,3,7,30].includes(context.days)?context.days:7;
    count++;
    try { Promise.resolve(send(`/events/v1/${id}/${name}/${view}/${days}`, {
      method:'GET',credentials:'omit',cache:'no-store',keepalive:true,referrerPolicy:'no-referrer'
    })).catch(()=>{}); } catch { /* measurement must never interrupt browsing */ }
  }
  function engage() {
    if(!started || engaged || d.visibilityState!=='visible')return;
    engaged=true;cancel(timer);event('engaged');
  }
  function visibility() {
    cancel(timer);
    if(started && !engaged && d.visibilityState==='visible')timer=later(engage,10000);
  }
  if(id)d.addEventListener('visibilitychange',visibility);
  return {
    start(next) { context=next;if(started)return;started=true;event('page_view');visibility(); },
    context(next) { context=next; },
    activity(next) { context=next;engage(); },
    interaction(name,next) { context=next;if(!started)return;engage();event(name); }
  };
}
