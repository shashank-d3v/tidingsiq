import {PAGE_SIZE, escapeHTML as esc, safeURL, rangeRows, selectRows, summary, scoreBand, createFreshnessMonitor} from './feed.mjs';
import {createAnalytics} from './analytics.mjs';
const analytics=createAnalytics();
const $ = id => document.getElementById(id);
const number = value => new Intl.NumberFormat('en-US').format(value);
const languageNames = new Intl.DisplayNames(['en'], {type:'language'});
const languageLabel = code => {if (!code || code==='und') return 'Unknown language'; try {return languageNames.of(code);} catch {return code.toUpperCase();}};
const state = {days:7, language:'', country:'', search:'', sort:'high', page:1};
const cache = new Map();
let manifest, rows = [], revision = 0, ready = false;
const view = () => ['brief','pulse','methodology'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'brief';
const prettyDate = day => new Date(`${day}T00:00:00Z`).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});
const freshness = createFreshnessMonitor({document, onChange(stale, edition) {
  $('freshness-status').hidden = !stale;
  $('freshness-status').textContent = `This loaded edition is from ${prettyDate(edition.as_of)}. Reload the page to check for a newer update.`;
}});
function notice(message, error=false) {
  $('load-status').hidden = !message;
  $('load-status').classList.toggle('error',error);
  $('load-status').replaceChildren(document.createTextNode(message));
  if(error){const retry=document.createElement('button');retry.textContent='Try again';retry.className='retry';retry.addEventListener('click',()=>start());$('load-status').append(retry);}
}
async function fetchJSON(url) {
  const response = await fetch(url);
  if(!response.ok) throw new Error(`Snapshot request failed (${response.status})`);
  return response.json();
}
async function loadRange() {
  const ticket = ++revision;
  const key = state.days===30 ? '30':'7';
  notice(cache.has(key)?'':'Loading the news feed…');
  ready=false;
  $('data-views').hidden=true;
  try {
    if(!cache.has(key)) {
      const entry=manifest.ranges[key];
      if(!/^feed-(7|30)d-[a-f0-9]+\.json$/.test(entry.file)) throw new Error('Invalid snapshot filename');
      const data=await fetchJSON(`./data/${entry.file}`);
      if(!Array.isArray(data)||data.length!==entry.rows||data.some(r=>typeof r.article_id!=='string'||typeof r.title!=='string'||!Number.isFinite(r.happy_factor))) throw new Error('Invalid snapshot data');
      if(manifest.matcher_version && (data.some(r=>typeof r.story_id!=='string'||!/^[a-f0-9]{64}$/.test(r.story_id)) || new Set(data.map(r=>r.story_id)).size!==entry.story_count)) throw new Error('Invalid story assignments');
      cache.set(key,data);
    }
    if(ticket!==revision)return;
    rows=cache.get(key);ready=true;
    state.page=1;
    updateOptions();notice('');render();analytics.start({view:view(),days:state.days});
  }catch(error){if(ticket===revision){notice('The news feed could not be loaded. Please try again.',true);console.error(error);}}
}
function updateOptions(){
  const scope=rangeRows(rows,state.days,manifest.as_of);
  for(const [id,key,label,all] of [['language','language',languageLabel,'All languages'],['country','mentioned_country_name',x=>x,'All geographies']]){
    const values=[...new Set(scope.map(r=>r[key]||(id==='language'?'und':'Unknown')))].sort((a,b)=>label(a).localeCompare(label(b)));
    if(!values.includes(state[id]))state[id]='';
    $(id).innerHTML=`<option value="">${all}</option>`+values.map(value=>`<option value="${esc(value)}">${esc(label(value))}</option>`).join('');
    $(id).value=state[id];
  }
}
function card(row){
  const url=safeURL(row.url), title=esc(row.title||'Untitled article');
  return `<article class="card"><div class="card-top"><span class="source">${esc(row.source_name||'Unknown source')}</span><span class="score score-${scoreBand(row.happy_factor)}" title="Happy Factor: a ranking signal, not an editorial rating" aria-label="Happy Factor ${row.happy_factor.toFixed(1)} out of 100">Happy Factor <strong>${row.happy_factor.toFixed(1)}</strong></span></div><h3>${url?`<a class="headline" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${title}</a>`:title}</h3><div class="tags"><span class="tag">${esc(languageLabel(row.language))}</span><span class="tag">Mentions ${esc(row.mentioned_country_name||'unknown geography')}</span></div><div class="card-bottom"><span>${prettyDate((row.published_at||row.serving_date).slice(0,10))}</span>${url?`<a class="read-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Read ${title} at the publisher (opens a new tab)">Read story <span>↗</span></a>`:'Source unavailable'}</div></article>`;
}
function bars(entries){
  const max=Math.max(...entries.map(([,n])=>n),1);
  return entries.map(([label,count])=>`<div class="bar-row"><span>${esc(label)}</span><div class="bar-track"><div class="bar-fill" style="width:${100*count/max}%"></div></div><span class="bar-number">${number(count)}</span></div>`).join('');
}
function pulse(selected){
  if(!selected.length){$('pulse-view').innerHTML='<div class="empty"><h3>No stories in this selection.</h3><p>Try a wider window or reset your filters.</p></div>';return;}
  const countries=new Map(), days=new Map(), buckets=[['65–69',0],['70–79',0],['80–89',0],['90–100',0]];
  for(const r of selected){const country=r.mentioned_country_name||'Unknown';countries.set(country,(countries.get(country)||0)+1);days.set(r.serving_date,(days.get(r.serving_date)||0)+1);buckets[r.happy_factor<70?0:r.happy_factor<80?1:r.happy_factor<90?2:3][1]++;}
  const dates=[];for(let offset=state.days;offset>=0;offset--){const d=new Date(`${manifest.as_of}T00:00:00Z`);d.setUTCDate(d.getUTCDate()-offset);const key=d.toISOString().slice(0,10);dates.push([key,days.get(key)||0]);}
  const max=Math.max(...dates.map(([,n])=>n),1);
  $('pulse-view').innerHTML=`<div class="chart-panel"><h3>A little perspective, by day.</h3><p>Eligible stories by serving date in this selection. These counts reflect eligible stories in this feed, not all news published that day.</p><div class="daily-chart" role="img" aria-label="${esc(dates.map(([d,n])=>`${d}: ${n} stories`).join('; '))}">${dates.map(([d,n],i)=>`<div class="day-column" title="${esc(prettyDate(d))}: ${number(n)} stories"><div class="day-bar" style="height:${100*n/max}px"></div><span class="day-label">${dates.length<10||i%5===0?d.slice(8):'·'}</span></div>`).join('')}</div></div><div class="chart-grid"><div class="chart-panel"><h3>Places in the stories</h3><p>Top five mentioned geographies</p>${bars([...countries].sort((a,b)=>b[1]-a[1]).slice(0,5))}</div><div class="chart-panel"><h3>The optimism spectrum</h3><p>Stories by Happy Factor band</p>${bars(buckets)}</div></div>`;
}
function render(){
  const current=view();
  analytics.context({view:current,days:state.days});
  document.querySelectorAll('[data-view]').forEach(a=>{if(a.dataset.view===current)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  $('methodology-view').hidden=current!=='methodology';
  $('data-views').hidden=current==='methodology'||!ready;
  $('hero-kicker').textContent=current==='pulse'?'THE BIGGER PICTURE':current==='methodology'?'BEHIND THE BRIEF':'YOUR DAILY DOSE OF PERSPECTIVE';
  $('hero-title').innerHTML=current==='pulse'?'A world of<br>possibility<span class="green">.</span>':current==='methodology'?'A brighter lens.<br>An open process<span class="green">.</span>':'Good things are<br>happening<span class="green">.</span>';
  $('hero-description').textContent=current==='pulse'?'Explore the places and patterns in your news selection.':current==='methodology'?'Understand the signals, the choices, and the limitations.':'Discover the stories that bring a little more optimism. Thoughtfully ranked. Yours to explore.';
  if(!manifest||current==='methodology')return;
  const selected=selectRows(rows,state,manifest.as_of), s=summary(selected);
  $('stats').innerHTML=[['STORIES IN VIEW',number(s.count),'Eligible stories','▤'],['AVG HAPPY FACTOR',s.average===null?'—':s.average.toFixed(1),'On a scale of 0–100','✦'],['NEWS SOURCES',number(s.sources),'Different perspectives','◎'],['GEOGRAPHIES',number(s.countries),'Places mentioned','↗']].map(([label,value,note,symbol])=>`<div class="stat"><span class="stat-label">${label}</span><span class="stat-symbol" aria-hidden="true">${symbol}</span><div class="stat-value">${value}</div><span class="stat-note">${note}</span></div>`).join('');
  const pages=Math.max(1,Math.ceil(selected.length/PAGE_SIZE));state.page=Math.min(state.page,pages);
  $('results-title').textContent=current==='pulse'?'Patterns worth noticing.':'Worth a little of your time.';
  $('result-count').textContent=`${number(selected.length)} stories · ${state.days}-day window through ${prettyDate(manifest.as_of)} · UTC dates`;
  $('brief-view').hidden=current!=='brief';$('pulse-view').hidden=current!=='pulse';
  if(current==='pulse')pulse(selected);
  else{
    $('cards').innerHTML=selected.length?selected.slice((state.page-1)*PAGE_SIZE,state.page*PAGE_SIZE).map(card).join(''):'<div class="empty"><h3>A fresh perspective awaits.</h3><p>No stories match these filters. Try another search or reset your selection.</p></div>';
    $('page-label').textContent=`Page ${state.page} of ${number(pages)}`;
    $('previous').disabled=state.page===1;$('next').disabled=state.page===pages;
  }
}
$('range').addEventListener('change',e=>{state.days=Number(e.target.value);analytics.interaction('range_change',{view:view(),days:state.days});loadRange();});
for(const id of ['language','country','sort'])$(id).addEventListener('change',e=>{state[id]=e.target.value;state.page=1;render();analytics.activity({view:view(),days:state.days});});
$('search').addEventListener('input',e=>{state.search=e.target.value;state.page=1;render();analytics.activity({view:view(),days:state.days});});
$('reset').addEventListener('click',()=>{Object.assign(state,{days:7,language:'',country:'',search:'',sort:'high',page:1});$('range').value='7';$('search').value='';$('sort').value='high';loadRange();});
for(const [id,delta]of [['previous',-1],['next',1]])$(id).addEventListener('click',()=>{state.page+=delta;render();analytics.activity({view:view(),days:state.days});$('results-title').scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});});
window.addEventListener('hashchange',()=>{render();analytics.interaction('view_change',{view:view(),days:state.days});});
$('cards').addEventListener('click',e=>{if(e.target.closest('a.headline,a.read-link'))analytics.interaction('article_click',{view:view(),days:state.days});});
async function start(){
  notice('Preparing your brief…');
  try{
    manifest=await fetchJSON('./data/manifest.json');
    cache.clear();
    if(manifest.schema_version!==1||!/^\d{4}-\d{2}-\d{2}$/.test(manifest.as_of))throw new Error('Invalid snapshot manifest');
    $('edition-date').textContent=`DATA UPDATED · ${prettyDate(manifest.as_of).toUpperCase()}`;
    $('footer-date').textContent=`Data updated · ${prettyDate(manifest.as_of)}`;
    freshness.update(manifest);
    $('snapshot-explanation').textContent=`This feed contains data through ${prettyDate(manifest.as_of)}. The “Data updated” date comes from the feed itself and changes when newer data is published. The feed is prepared in editions, so browsing does not change its data date. Searching, filtering, and changing pages explore the same edition.`;
    await loadRange();
  }catch(error){notice('The news feed is temporarily unavailable. Please try again shortly.',true);console.error(error);}
}
render();start();
