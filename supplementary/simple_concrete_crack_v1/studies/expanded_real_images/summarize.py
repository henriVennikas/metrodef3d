"""Recompute the descriptive overview from the frozen prediction/reference values."""
from pathlib import Path
import json,statistics,collections,math
P=Path(__file__).resolve().parent
rows=json.loads((P/'predictions_and_references.json').read_text())
assert len(rows)==26 and len({r['image'] for r in rows})==26
assert collections.Counter(r['group'] for r in rows)=={'field':6,'controlled_tile':20}
lines=['# Frozen real-image results','', '[Current comparison of all four methods on all 26 images](all_methods/REPORT.md). This table preserves the transformer overview.','',
'Original orientation, retained transformer, fixed corrected synthetic-validation interval factors. Each row uses the adopted single annotation. Values below are absolute relative differences in percent, not a population estimate or an acceptance classification.','',
'| Image | Source | Length | Mean width | Maximum width | Area | References within bounds |',
'|---|---|---:|---:|---:|---:|---:|']
for r in rows:
 q=r['quantities']
 for t,v in q.items():
  err=100*abs(v['prediction']-v['reference'])/v['reference']
  assert math.isclose(err,v['absolute_relative_error_percent'],abs_tol=1e-10)
  assert v['covered']==(v['calibrated_lower']<=v['reference']<=v['calibrated_upper'])
 vals=[q[t]['absolute_relative_error_percent'] for t in ['centerline_length','mean_width','max_width','crack_area']]
 lines.append('| [%s](%s) | %s | %s | %s/4 |'%(r['image'],r['photo'],r['group'], ' | '.join(f'{v:.2f}' for v in vals),sum(v['covered'] for v in q.values())))
(P/'RESULTS.md').write_text('\n'.join(lines)+'\n')
rotation=json.loads((P/'rotation/all_predictions.json').read_text())
assert len(rotation)==168
pairs=collections.defaultdict(list)
for r in rotation:pairs[r['domain'],r['model'],r['id']].append(r)
assert all({r['angle_clockwise'] for r in rr}=={0,90,180,-90} for rr in pairs.values())
computed=collections.defaultdict(list)
for (domain,model,image),rr in pairs.items():
 for target in rr[0]['reference']:
  ref=rr[0]['reference'][target];assert all(r['reference'][target]==ref for r in rr)
  values=[r['predictions'][target]['mu'] for r in rr]
  computed[domain,model,target].append((100*(max(values)-min(values))/ref,image))
for r in json.loads((P/'rotation/rotation_range_summary.json').read_text()):
 values=computed[r['domain'],r['model'],r['target']]
 assert math.isclose(statistics.mean(v[0] for v in values),r['mean_range_percent'],abs_tol=1e-9)
 assert math.isclose(max(v[0] for v in values),r['max_range_percent'],abs_tol=1e-9)
print('Verified: 26 original-orientation observations, 104 quantity comparisons, 168 rotation outputs, 24 rotation summaries.')
