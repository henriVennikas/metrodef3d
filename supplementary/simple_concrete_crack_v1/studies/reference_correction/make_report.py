"""Summarize versioned reference corrections and frozen-prediction impact."""
import os,csv,json,hashlib
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/metrodef-correction-mpl');os.environ.setdefault('XDG_CACHE_HOME','/tmp/metrodef-reference-cache')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent
TARGETS=['centerline_length','mean_width','max_width','crack_area'];NAMES=['Length','Mean width','Maximum width','Area'];METHODS=['transformer','resnet50','convnext_tiny','conventional'];LABELS=['Transformer','ResNet-50','ConvNeXt-Tiny','Conventional']

def main():
 regen=json.loads((HERE/'regeneration.json').read_text());fixed=[r for r in regen['rows'] if r['corrected']];inputs=json.loads((HERE/'original_sidecar_hashes.json').read_text());b=list(csv.DictReader((HERE/'benchmark_comparison.csv').open()));cal=json.loads((HERE/'calibration_comparison.json').read_text());overlay=HERE/'overlay'
 patches=[];manifest={}
 for r in fixed:
  seed=r['seed'];path=overlay/'visible_defect'/f'{seed}.json';data=json.loads(path.read_text());prov=data['correction_provenance']
  manifest[str(seed)]=dict(file=f'visible_defect/{seed}.json',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),original_sidecar=prov['original_sidecar'],original_sha256=r['original_sha256'],original_metadata_sha256=r['original_metadata_sha256'],components=r['components'])
  for t in TARGETS:patches.append(dict(seed=seed,partition=r['partition'],target=t,original=r['original'][t],original_replayed=r['same_runtime_original'][t],corrected=r['corrected_measurands'][t],change=r['corrected_measurands'][t]-r['original'][t],topology_only_change=r['corrected_measurands'][t]-r['same_runtime_original'][t],relative_change_percent=100*(r['corrected_measurands'][t]/r['original'][t]-1) if r['original'][t] else None))
 (overlay/'manifest.json').write_text(json.dumps(dict(version='component-aware-2',dataset='MetroDef3D Simple Concrete Crack Dataset v1.0',date='2026-11-07',read_only_originals=True,sidecar_count=len(fixed),corrections=manifest),indent=2)+'\n')
 with (HERE/'reference_changes.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(patches[0]));w.writeheader();w.writerows(patches)
 table=['| Method | Length MARE (%) | Mean-width MARE (%) | Maximum-width MARE (%) | Area MARE (%) |','|---|---:|---:|---:|---:|']
 interval=['| Method | Quantity | Original coverage (%) | Corrected, fixed bounds (%) | Corrected, recalibrated (%) | Original / new mean width | Original / new normalized score (%) |','|---|---|---:|---:|---:|---:|---:|']
 def row(m,mode,t):return next(r for r in b if r['method']==m and r['mode']==mode and r['target']==t)
 for m,label in zip(METHODS,LABELS):
  table.append('| '+label+' | '+' | '.join(f"{float(row(m,'original',t)['mare_percent']):.2f} → {float(row(m,'corrected_fixed_calibration',t)['mare_percent']):.2f}" for t in TARGETS)+' |')
  for t,n in zip(TARGETS,NAMES):
   a=row(m,'original',t);f=row(m,'corrected_fixed_calibration',t);c=row(m,'corrected_recalibrated_valid_cohort',t)
   interval.append(f"| {label} | {n} | {float(a['coverage_percent']):.2f} | {float(f['coverage_percent']):.2f} | {float(c['coverage_percent']):.2f} | {float(a['mean_interval_width']):.4f} / {float(c['mean_interval_width']):.4f} | {float(a['normalized_interval_score_percent']):.2f} / {float(c['normalized_interval_score_percent']):.2f} |")
 drift={t:max(abs(r['original'][t]-r['same_runtime_original'][t]) for r in regen['rows']) for t in TARGETS}
 ranking={t:[r['method'] for r in sorted([row(m,'corrected_fixed_calibration',t) for m in METHODS],key=lambda r:float(r['mare_percent']))] for t in TARGETS}
 assert all(ranking[t][0]=='transformer' for t in TARGETS)
 summary=dict(date='2026-11-07',correction_version='component-aware-2',corrected_count=len(fixed),partition_counts=regen['partition_counts'],test_count=1494,positive_test_count=1493,changed_test_references=26,model_weights_unchanged=True,predictions_unchanged=True,training_labels_used_by_retained_models='original v1',classical_selection='original tuning labels; settings unchanged',recalibration='separate validation-only analysis; known-invalid seed 551 excluded, with same-cohort controls',same_runtime_replay_max_drift=drift,ranking_by_mare=ranking,regeneration_seconds=regen['seconds'],published=False)
 (HERE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 text=f'''# Reference correction and benchmark impact

7 November 2026. **Local correction overlay. The original dataset, predictions, weights and published results are preserved.**

## Corrected export and reference version

Generator 0.1.1 uses visible-defect schema 2 and `reference_export_revision=component-aware-2`. The Blender exporter records half-open component ranges and calculates length within each component, without connecting across invisible segments. Mean width remains visible polygon area divided by the summed visible length. Station-profile extrema retain their construction definition.

If an opening polygon is visible but no centreline station is visible, area is retained and missing width/depth extrema are `null`. Mean width is `null` when visible length is zero. Explicit validity flags distinguish these cases from a genuinely empty observation with defined zero quantities. The preview fallback and overlay viewer also respect disconnected components. Projection, clipping thresholds, coordinate rounding and polygon-area arithmetic remain unchanged, so the small numerical conditioning discrepancies from the earlier verification have not been represented as fixed.

The 72 independent analytical/stress fixtures now execute without exceptions. All 65 ordinary fixture measurands are unchanged. The exit/re-entry fixture has two components and exported length 115.175100 mm (analytical value 115.175111 mm) instead of 138.032242 mm. Three previous empty-profile exceptions produce explicit undefined quantities. The existing generator tests and new component regression tests pass. The earlier failing verification is preserved separately.

## Dataset correction

A broader scan of all 10,000 original sidecars selected 142 candidates using original source-segment gaps and consecutive boundary intersections, with no fractional-gap threshold. The production-camera replay confirms disconnected visible components in all 142: **92 training, 24 validation and 26 test observations**. Seed 6861, previously unconfirmed by the ideal-camera audit, is now resolved using the actual Blender camera. Its length changes from 114.251014 to 92.664450 mm. Multi-component cases also expose short gaps missed by the earlier conservative subtraction audit.

Corrected sidecars are written only under `overlay/visible_defect/`, with original hashes, source-metadata hashes, old quantities and same-runtime original-export quantities. The overlay manifest identifies every replacement. Unlisted observations continue to use their unchanged original sidecars. The original metadata files still contain original references; consumers must explicitly select the overlay rather than mix old embedded values with corrected sidecars.

Replaying the old exporter in the current Blender runtime shows small differences from archived exports. Maximum absolute replay differences over 150 candidate/control observations are {drift['centerline_length']:.6f} mm length, {drift['mean_width']:.6f} mm mean width, {drift['max_width']:.6f} mm maximum width and {drift['crack_area']:.6f} mm² area. `reference_changes.csv` separates this replay difference from the topology-only change measured with both exporters in the same runtime. The full corrected sidecars retain regenerated values rather than silently combining parts from different executions. No images or pixel-scale maps were regenerated.

## Point predictions: before and after

All central predictions are identical to the saved benchmark outputs. Test identities remain the same 1494 observations. MARE uses the same 1493 positive references. Entries below show **original → corrected reference** results.

{chr(10).join(table)}

Length and mean-width MARE decrease for all three learned systems. Conventional length MARE also decreases, while its mean-width MARE increases slightly. Maximum-width and area MARE are unchanged at two decimals. The transformer retains the lowest MARE for every quantity. This remains a comparison of the retained runs, not a statistically established architecture ranking.

## Interval performance

Three distinct comparisons are preserved:

1. Original references and original calibration: reproduces the saved benchmark metrics and calibration factors.
2. Corrected references with the same calibrated bounds: isolates the reference change at fixed prediction intervals.
3. Corrected references with validation-only recalibration: keeps raw network outputs and conventional estimates fixed, but refits interval expansion factors or residual radii from corrected validation references.

Learned-model recalibration excludes the previously documented invalid validation seed 551, leaving 1493 observations. The complete table also contains same-cohort recalibration including that seed solely to isolate label correction, and an old-reference valid-cohort control. It therefore does not attribute the cohort adjustment to the topology fix. No test observations are excluded. The conventional pipeline retains its original disjoint 1237-case residual-calibration subset, which already excluded 551, and its original selected settings.

{chr(10).join(interval)}

For the transformer, unchanged bounds increase length coverage from 95.18% to 95.78%. Recalibration reduces its mean length-interval width from 10.48 to 8.99 mm, with test coverage 94.31%. Thus improved reference agreement need not increase coverage after bounds are narrowed. Mean-width coverage is 93.51% after recalibration. These remain empirical synthetic-population results, not guaranteed per-observation or field coverage.

## Interpretation and limits

The reference correction does not overturn the main comparison. Some measurement predictions agree better with the corrected geometry than with the original erroneous labels. That observation does not establish what retraining would achieve.

The learned weights, training normalization, selected checkpoints and auxiliary supervision were obtained with the original labels. The conventional settings were selected using the original tuning references. This study reevaluates those fixed systems and separately recalibrates their bounds; it is not a retrained benchmark. Ninety-two corrected training observations and 24 corrected validation observations may affect future training or selection. Training-derived interval-score floors remain frozen to isolate the comparison. Newly calibrated intervals must not be described as part of the original frozen model release without a new calibration identifier.

New references use their six-decimal physical values. Unchanged learned-model references retain the original CSV float32 representation. The original metrics reproduce exactly before correction; the earlier audit bounds the original float32 conversion differences. All per-observation predictions, references, bounds and full-precision aggregate metrics are saved.

The original benchmark tables and historical studies are preserved by this impact assessment. Corrected-reference comparisons and validation recalibration are reported separately. Training and checkpoint selection remain based on the original references.

## Artifacts

- `overlay/manifest.json`, `overlay/visible_defect/`: additive versioned reference overlay and provenance.
- `load_overlay.py`: explicit read-only selection of corrected or original references.
- `reference_changes.csv`, `regeneration.json`: every old/new quantity, component count and same-runtime comparison.
- `benchmark_comparison.csv`: point and interval metrics under all comparison modes.
- `calibration_comparison.json`: original, corrected and cohort-control factors/radii.
- `predictions/`: corrected-reference test tables with fixed or recalibrated bounds.
- `fixture_results/`, `fixture_regression.log`: corrected export regression outputs.
- `candidate_screen.json`, `original_sidecar_hashes.json`, `original_metadata_hashes.json`: original input identities and hashes.
- `source_manifest.json`, `corrected_export.py`, `code/`: exact implementation used and staged source files.
- `protocol.json`, `benchmark_verification.json`, `verification.json`: frozen analysis decisions and verification.

No changes have been published and no model training was launched.
'''
 (HERE/'REPORT.md').write_text(text)
 fig,axes=plt.subplots(2,2,figsize=(9,5.8),layout='constrained')
 for ax,t,name in zip(axes.flat,TARGETS,NAMES):
  y=np.arange(4);a=[float(row(m,'original',t)['mare_percent']) for m in METHODS];c=[float(row(m,'corrected_fixed_calibration',t)['mare_percent']) for m in METHODS]
  ax.barh(y-.15,a,height=.28,color='#a8b4c1',label='Original references');ax.barh(y+.15,c,height=.28,color='#356c9b',label='Corrected references');ax.set_yticks(y,LABELS);ax.invert_yaxis();ax.set(title=name,xlabel='MARE (%)');ax.grid(axis='x',alpha=.15)
 axes[0,0].legend(fontsize=7);fig.savefig(HERE/'benchmark_impact.png',dpi=180);plt.close(fig)
 print(chr(10).join(table))
if __name__=='__main__':main()
