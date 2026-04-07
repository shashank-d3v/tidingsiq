/* @bruin
name: gold.positive_feed_guardrail_terms
type: bq.sql
connection: bigquery-default

materialization:
  type: table

columns:
  - name: term
    type: string
    checks:
      - name: not_null
  - name: rule_class
    type: string
    checks:
      - name: not_null
  - name: match_scope
    type: string
    checks:
      - name: not_null
  - name: is_active
    type: boolean
    checks:
      - name: not_null
  - name: notes
    type: string
@bruin */

with terms as (
  select * from unnest([
    struct('obit' as term, 'deny_hard' as rule_class, 'token' as match_scope, true as is_active, 'Obituary shorthand' as notes),
    ('obituary', 'deny_hard', 'token', true, 'Explicit obituary term'),
    ('death', 'deny_hard', 'token', true, 'Death-related title term'),
    ('dead', 'deny_hard', 'token', true, 'Death-related title term'),
    ('dies', 'deny_hard', 'token', true, 'Death-related title term'),
    ('killed', 'deny_hard', 'token', true, 'Fatal violence term'),
    ('kill', 'deny_hard', 'token', true, 'Fatal violence term'),
    ('murder', 'deny_hard', 'token', true, 'Severe crime term'),
    ('murdered', 'deny_hard', 'token', true, 'Severe crime term'),
    ('suicide', 'deny_hard', 'token', true, 'Self-harm term'),
    ('rape', 'deny_hard', 'token', true, 'Severe crime term'),
    ('terrorist', 'deny_hard', 'token', true, 'Severe violence term'),
    ('terrorism', 'deny_hard', 'token', true, 'Severe violence term'),
    ('bombing', 'deny_hard', 'token', true, 'Severe violence term'),
    ('crash', 'deny_hard', 'token', true, 'Severe accident term'),
    ('crashed', 'deny_hard', 'token', true, 'Severe accident term'),
    ('stabbing', 'deny_hard', 'token', true, 'Severe violence term'),
    ('stabbed', 'deny_hard', 'token', true, 'Severe violence term'),

    ('attack', 'deny_soft', 'token', true, 'Risky harm/conflict term'),
    ('attacked', 'deny_soft', 'token', true, 'Risky harm/conflict term'),
    ('blast', 'deny_soft', 'token', true, 'Risky incident term'),
    ('blasts', 'deny_soft', 'token', true, 'Risky incident term'),
    ('bomb', 'deny_soft', 'token', true, 'Risky incident term'),
    ('bombs', 'deny_soft', 'token', true, 'Risky incident term'),
    ('explosion', 'deny_soft', 'token', true, 'Risky incident term'),
    ('explosions', 'deny_soft', 'token', true, 'Risky incident term'),
    ('war', 'deny_soft', 'token', true, 'Conflict term'),
    ('warfare', 'deny_soft', 'token', true, 'Conflict term'),
    ('conflict', 'deny_soft', 'token', true, 'Conflict term'),
    ('clashes', 'deny_soft', 'token', true, 'Conflict term'),
    ('riot', 'deny_soft', 'token', true, 'Civil unrest term'),
    ('riots', 'deny_soft', 'token', true, 'Civil unrest term'),
    ('unrest', 'deny_soft', 'token', true, 'Civil unrest term'),
    ('injured', 'deny_soft', 'token', true, 'Injury term'),
    ('injury', 'deny_soft', 'token', true, 'Injury term'),
    ('injuries', 'deny_soft', 'token', true, 'Injury term'),
    ('wounded', 'deny_soft', 'token', true, 'Injury term'),
    ('hostage', 'deny_soft', 'token', true, 'Crisis term'),
    ('arrest', 'deny_soft', 'token', true, 'Crime or investigation term'),
    ('arrested', 'deny_soft', 'token', true, 'Crime or investigation term'),
    ('probe', 'deny_soft', 'token', true, 'Investigation term'),
    ('scandal', 'deny_soft', 'token', true, 'Negative topic term'),
    ('fraud', 'deny_soft', 'token', true, 'Negative topic term'),
    ('scam', 'deny_soft', 'token', true, 'Negative topic term'),
    ('corruption', 'deny_soft', 'token', true, 'Negative topic term'),
    ('fire', 'deny_soft', 'token', true, 'Disaster term'),
    ('wildfire', 'deny_soft', 'token', true, 'Disaster term'),
    ('flood', 'deny_soft', 'token', true, 'Disaster term'),
    ('earthquake', 'deny_soft', 'token', true, 'Disaster term'),
    ('hurricane', 'deny_soft', 'token', true, 'Disaster term'),
    ('cyclone', 'deny_soft', 'token', true, 'Disaster term'),
    ('tornado', 'deny_soft', 'token', true, 'Disaster term'),
    ('disaster', 'deny_soft', 'token', true, 'Disaster term'),
    ('outbreak', 'deny_soft', 'token', true, 'Health crisis term'),
    ('epidemic', 'deny_soft', 'token', true, 'Health crisis term'),
    ('pandemic', 'deny_soft', 'token', true, 'Health crisis term'),
    ('robbery', 'deny_soft', 'token', true, 'Crime term'),
    ('theft', 'deny_soft', 'token', true, 'Crime term'),
    ('shooting', 'deny_soft', 'token', true, 'Violence term'),
    ('shootings', 'deny_soft', 'token', true, 'Violence term'),
    ('gunfire', 'deny_soft', 'token', true, 'Violence term'),
    ('shelling', 'deny_soft', 'token', true, 'Conflict term'),
    ('missile', 'deny_soft', 'token', true, 'Conflict term'),
    ('missiles', 'deny_soft', 'token', true, 'Conflict term'),
    ('evacuation', 'deny_soft', 'token', true, 'Disruption term'),
    ('evacuate', 'deny_soft', 'token', true, 'Disruption term'),
    ('toxic', 'deny_soft', 'token', true, 'Hazard term'),
    ('poisoning', 'deny_soft', 'token', true, 'Hazard term'),
    ('panic', 'deny_soft', 'token', true, 'Crisis term'),

    ('rescue', 'allow', 'token', true, 'Positive recovery term'),
    ('rescued', 'allow', 'token', true, 'Positive recovery term'),
    ('recovery', 'allow', 'token', true, 'Positive recovery term'),
    ('recovered', 'allow', 'token', true, 'Positive recovery term'),
    ('relief', 'allow', 'token', true, 'Positive aid term'),
    ('aid', 'allow', 'token', true, 'Positive aid term'),
    ('charity', 'allow', 'token', true, 'Positive civic term'),
    ('donation', 'allow', 'token', true, 'Positive civic term'),
    ('donate', 'allow', 'token', true, 'Positive civic term'),
    ('fundraiser', 'allow', 'token', true, 'Positive civic term'),
    ('scholarship', 'allow', 'token', true, 'Positive opportunity term'),
    ('award', 'allow', 'token', true, 'Positive recognition term'),
    ('awarded', 'allow', 'token', true, 'Positive recognition term'),
    ('breakthrough', 'allow', 'token', true, 'Positive progress term'),
    ('heal', 'allow', 'token', true, 'Positive health term'),
    ('healing', 'allow', 'token', true, 'Positive health term'),
    ('cure', 'allow', 'token', true, 'Positive health term'),
    ('cured', 'allow', 'token', true, 'Positive health term'),
    ('save', 'allow', 'token', true, 'Positive recovery term'),
    ('saved', 'allow', 'token', true, 'Positive recovery term'),
    ('peace', 'allow', 'token', true, 'Positive diplomacy term'),
    ('ceasefire', 'allow', 'token', true, 'Positive diplomacy term'),
    ('community', 'allow', 'token', true, 'Positive civic term'),
    ('volunteer', 'allow', 'token', true, 'Positive civic term'),
    ('support', 'allow', 'token', true, 'Positive civic term'),
    ('celebration', 'allow', 'token', true, 'Positive civic term'),
    ('win', 'allow', 'token', true, 'Positive achievement term'),
    ('wins', 'allow', 'token', true, 'Positive achievement term'),
    ('victory', 'allow', 'token', true, 'Positive achievement term'),
    ('reunion', 'allow', 'token', true, 'Positive social term'),
    ('free', 'allow', 'token', true, 'Positive accessibility term'),

    ('brings community together', 'allow', 'phrase', true, 'Positive community phrase'),
    ('free family fun', 'allow', 'phrase', true, 'Positive community phrase'),
    ('wins award', 'allow', 'phrase', true, 'Positive recognition phrase'),
    ('peace talks', 'allow', 'phrase', true, 'Positive diplomacy phrase'),
    ('relief effort', 'allow', 'phrase', true, 'Positive civic phrase'),
    ('recovery effort', 'allow', 'phrase', true, 'Positive civic phrase'),
    ('charity event', 'allow', 'phrase', true, 'Positive civic phrase'),
    ('fundraiser for', 'allow', 'phrase', true, 'Positive civic phrase'),
    ('rescued from', 'allow', 'phrase', true, 'Positive recovery phrase'),
    ('saved by', 'allow', 'phrase', true, 'Positive recovery phrase')
  ])
)

select
  term,
  rule_class,
  match_scope,
  is_active,
  notes
from terms
