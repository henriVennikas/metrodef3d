"""Recompute scanner-axis scale statistics from the fourteen saved scan records.
Run from any directory. Writes scanner_summary.json and scanner_summary.csv.
"""
from pathlib import Path
import csv, json, statistics
ROOT = Path(__file__).resolve().parent
rows = []
for path in sorted((ROOT / 'scanner_scans').glob('*/metrics.json')):
    m = json.loads(path.read_text())
    s = m['spans']
    x = statistics.mean(s[k]['certified_mm'] * 1000 / s[k]['observed_px'] for k in ('A1_top','A2_bottom'))
    y = statistics.mean(s[k]['certified_mm'] * 1000 / s[k]['observed_px'] for k in ('A3_left','A4_right'))
    assert abs(x-m['calibrated_scale']['x_um_per_px']) < 1e-10
    assert abs(y-m['calibrated_scale']['y_um_per_px']) < 1e-10
    rotation = m['orientation']['rotation_cw_applied']
    if rotation in (90,270): x,y = y,x
    rows.append(dict(scan=path.parent.name, rotation_cw=rotation, scanner_x_um_per_px=x,
                     scanner_y_um_per_px=y, affine_rms_um=m['affine_residual_um']['rms_radial']))
assert len(rows) == 14
summary = {'n_scans':len(rows), 'statistics':{}, 'applied_mm_per_pixel':[0.010066935,0.010012375],
           'uncertainty_note':'Sample SD and affine residuals are not expanded measurement uncertainty. Certificate tolerances are not stated calibration uncertainties.'}
for key in ('scanner_x_um_per_px','scanner_y_um_per_px','affine_rms_um'):
    vals=[r[key] for r in rows]
    summary['statistics'][key]=dict(mean=statistics.mean(vals),sample_sd=statistics.stdev(vals),minimum=min(vals),maximum=max(vals))
for i,key in enumerate(('scanner_x_um_per_px','scanner_y_um_per_px')):
    assert abs(summary['statistics'][key]['mean']/1000-summary['applied_mm_per_pixel'][i]) < 5e-10
(ROOT/'scanner_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with (ROOT/'scanner_summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(summary,indent=2))
