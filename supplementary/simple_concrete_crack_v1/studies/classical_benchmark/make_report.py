"""Summarize frozen outputs; no parameter changes or prediction fitting."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/metrodef-classical-mpl')
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/metrodef-classical-cache')
from pathlib import Path
import argparse,csv,json,hashlib
import numpy as np
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pipeline import TARGETS, predict
from run_benchmark import read, dump, metrics, metadata_paths, load, oracle_mask

HERE=Path(__file__).resolve().parent
REF=HERE.parent/'model_benchmark'

def rows(p):
    with Path(p).open() as f:return list(csv.DictReader(f))


def main():
    global REF
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--reference', type=Path, default=REF)
    args=parser.parse_args()
    REF=args.reference
    selected=read(HERE/'selected.json');protocol=read(HERE/'protocol.json')
    raw=rows(HERE/'results/test_predictions.csv')
    classic=[{k:(float(v) if k.endswith(('_actual','_mu','_lower','_upper')) else v) for k,v in r.items()} for r in raw]
    reference=rows(REF/'transformer/test_predictions.csv')
    original={int(r['seed']):r for r in reference}
    assert set(original)==set(map(int,protocol['test_seeds']))=={int(r['seed']) for r in classic}
    diffs={t:max(abs(r[t+'_actual']-float(original[int(r['seed'])][t+'_actual'])) for r in classic) for t in TARGETS}
    assert all(np.isclose(r[t+'_actual'], float(original[int(r['seed'])][t+'_actual']), rtol=1e-7, atol=1e-6) for r in classic for t in TARGETS), diffs
    names={'centerline_length':'Length','mean_width':'Mean width','max_width':'Maximum width','crack_area':'Area'}
    compare=[]
    for model in ['transformer','resnet50','convnext_tiny']:
        rr=rows(REF/model/'test_predictions.csv')
        assert {int(r['seed']) for r in rr}==set(original)
        for r in rr:
            for t in TARGETS:assert abs(float(r[t+'_actual'])-float(original[int(r['seed'])][t+'_actual']))<2e-5
        mm=metrics([{t+s:float(r[t+s]) for t in TARGETS for s in ['_actual','_mu']} for r in rr])
        compare.extend([dict(model=model,**m) for m in mm])
    mm=read(HERE/'results/test_metrics.json');oracle=read(HERE/'results/reference_mask_metrics.json')
    compare.extend([dict(model='classical',**m) for m in mm])
    compare.extend([dict(model='reference_mask_diagnostic',**m) for m in oracle])
    fields=['model','target','n','n_positive','unit','mae','rmse','bias','mare_percent','r2']
    with (HERE/'comparison.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(compare)
    # Independent metric recomputation from exported CSV, including zero-reference seed.
    for expected,actual in zip(mm,metrics(classic,read(HERE/'calibration.json')['radii'],protocol['relative_floors'])):
        for key in ['mae','rmse','mare_percent','r2','coverage_percent','relative_interval_score_percent']:
            assert np.isclose(expected[key],actual[key],atol=1e-10),key
    zero=[int(r['seed']) for r in classic if all(r[t+'_actual']==0 for t in TARGETS)]
    assert zero==[1625]
    empty=[int(r['seed']) for r in classic if r['centerline_length_mu']==0]
    verification=dict(test_identity_exact=True,reference_max_difference_vs_float32_csv=diffs,
        zero_reference_seeds=zero,empty_prediction_seeds=empty,exported_metrics_recomputed=True,
        frozen_sources_intact=all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h for n,h in selected['source_sha256'].items()),
        selection_calibration_test_disjoint=not(set(protocol['tune_seeds'])&set(protocol['calibration_seeds']) or set(protocol['test_seeds'])&(set(protocol['tune_seeds'])|set(protocol['calibration_seeds']))))
    verification['frozen_protocol_intact'] = hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest() == selected['protocol_sha256']
    assert verification['frozen_sources_intact'] and verification['frozen_protocol_intact']
    dump(HERE/'verification.json',verification)
    labels=['Transformer','ResNet-50','ConvNeXt-Tiny','Classical']
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for ax,t in zip(axes.flat,TARGETS):
        vals=[next(r['mare_percent'] for r in compare if r['target']==t and r['model']==m) for m in ['transformer','resnet50','convnext_tiny','classical']]
        bars=ax.bar(labels,vals,color=['#237a9f','#7e8d53','#976cab','#cc772d'])
        ax.bar_label(bars,fmt='%.2f',padding=3);ax.set_title(names[t]);ax.set_ylabel('MARE (%)');ax.set_ylim(0,max(vals)*1.2);ax.tick_params(axis='x',rotation=15)
    fig.suptitle('Common synthetic test partition: 1493 positive references\nOriginal retained neural predictions; frozen classical pipeline')
    fig.savefig(HERE/'comparison.png',dpi=160);plt.close(fig)
    # QA cases are explicitly post-evaluation diagnostics: first six + six worst.
    score=lambda r:np.mean([abs(r[t+'_mu']-r[t+'_actual'])/max(r[t+'_actual'],protocol['relative_floors'][j]) for j,t in enumerate(TARGETS)])
    worst=sorted(classic,key=score,reverse=True)[:6]
    qa=classic[:6]+[r for r in worst if r not in classic[:6]]
    index=metadata_paths(args.dataset)
    qa_dir=HERE/'qa';qa_dir.mkdir(exist_ok=True)
    summary=[]
    for r in qa:
        seed=int(r['seed']);rgb,sx,sy,truth=load(index[seed]);a,d=predict(rgb,sx,sy,selected['config'],True)
        im=Image.fromarray(rgb);im.thumbnail((400,400))
        overlay=rgb.astype(float);mask=d['mask'];ref=oracle_mask(truth,sx.shape)
        # Cyan reference pixels, orange segmentation; overlap blends both.
        overlay[ref]=overlay[ref]*.55+np.array([0,190,255])*.45
        overlay[mask]=overlay[mask]*.55+np.array([255,115,0])*.45
        ov=Image.fromarray(np.clip(overlay,0,255).astype('uint8'));dr=ImageDraw.Draw(ov)
        for path in d['paths']:dr.line([tuple(pt) for pt in path],fill=(255,0,180),width=2)
        ov.thumbnail((400,400));canvas=Image.new('RGB',(800,465),'white');canvas.paste(im,(0,0));canvas.paste(ov,(400,0));dr=ImageDraw.Draw(canvas)
        dr.text((8,405),f'Seed {seed} | cyan reference mask; orange segmented mask; magenta path',fill='black')
        dr.text((8,425),'Ref / estimate: '+', '.join(f'{names[t]} {r[t+"_actual"]:.3f}/{r[t+"_mu"]:.3f}' for t in TARGETS),fill='black')
        canvas.save(qa_dir/f'{seed}.jpg',quality=90)
        summary.append(dict(seed=seed,role='first six test IDs' if r in classic[:6] else 'largest floored normalized absolute errors',mean_absolute_error_normalized_by_reference_or_training_floor_percent=100*score(r)))
    dump(qa_dir/'selection.json',summary)
    table=['| Method | Length MARE (%) | Mean-width MARE (%) | Max-width MARE (%) | Area MARE (%) |','|---|---:|---:|---:|---:|']
    for model,label in [('transformer','Transformer'),('resnet50','ResNet-50'),('convnext_tiny','ConvNeXt-Tiny'),('classical','Classical image-only'),('reference_mask_diagnostic','Reference-mask diagnostic')]:
        table.append('| '+label+' | '+' | '.join(f"{next(r['mare_percent'] for r in compare if r['model']==model and r['target']==t):.2f}" for t in TARGETS)+' |')
    interval=['| Quantity | MAE | RMSE | Bias | Residual radius | Test coverage (%) | Mean bound width |','|---|---:|---:|---:|---:|---:|---:|']
    for r in mm:interval.append('| '+names[r['target']]+' ('+r['unit']+') | '+' | '.join(f"{r[k]:.4g}" for k in ['mae','rmse','bias','residual_radius','coverage_percent','mean_interval_width'])+' |')
    timing={s:read(HERE/f'results/{s}.timing.json') for s in ['tuning','calibration','test']}
    text='''# Classical image-processing baseline: frozen test results

Study results, 6 November 2026.

The same 1494 synthetic test identities were evaluated, including the zero-reference seed 1625. MARE uses 1493 positive references. The neural results below are the original retained benchmark predictions, not newly trained models. Test results have not been used to adjust the classical pipeline.

## Point predictions

'''+ '\n'.join(table)+'''\n
The reference-mask diagnostic receives privileged geometric information. It isolates the geometric extraction stage and is not an image-only competitor or an independent validation of the generator.

## Classical errors and empirical bounds

'''+ '\n'.join(interval)+f'''\n
The selected configuration is `{selected['config']['id']}`. Selection used 256 validation cases. Residual radii use a separate 1237 validation cases. Seed 551 was excluded from validation under the development instructions, leaving the original test partition unchanged. Bounds are symmetric empirical absolute-residual bounds clipped at zero, rather than learned observation-dependent bounds. Their coverage does not include physical measurement-chain uncertainty or imply coverage on real photographs.

There were **{len(empty)} empty predictions** in the common test partition. All predictions and references, including failures and the zero-reference case, are retained in `results/`.

## Development record and limitations

The first local-brightness implementation gave very large validation errors on broad dark rendered regions. Its complete settings, code and results are retained in `development/iteration_1_local_brightness/`. Before any test evaluation, the same tuning subset was used to compare Gaussian and morphological-closing background estimates with a minimum contrast condition. The final selection searched 32 configurations. This makes the tuning subset a development resource, not an independent performance estimate. The residual-calibration and test sets were not used for algorithm development.

The estimator assumes simple elongated components. It traces one dominant path per component, may confuse texture or dark surface regions with cracks, and can omit small or fragmented regions. Maximum width uses image-derived normals and can differ from construction-normal widths. Rasterization and skeletonization remain visible even with the reference mask. Directional scale maps are treated as locally orthogonal; perspective shear is not encoded by those sidecars. These assumptions must accompany the comparison. Large dark rendered regions observed during development also warrant a separate image-quality review. Disagreement with a construction reference does not alone establish whether an individual case is a segmentation failure or a rendering/reference mismatch. No new test exclusions were introduced.

The baseline demonstrates a reproducible conventional pipeline on common images and references. It does not establish the performance of all classical algorithms, or a general model ranking. Real-image application remains a separate next step.

## Runtime and verification

- Parameter selection: {timing['tuning']['wall_seconds']:.1f} s for 256 images x 32 configurations.
- Residual calibration: {timing['calibration']['wall_seconds']:.1f} s for 1237 images.
- Test plus reference-mask diagnostic: {timing['test']['wall_seconds']:.1f} s for 1494 paired evaluations.
- Four local CPU workers; no GPU, paid compute or neural training. Wall times include data loading and computation. They are not directly comparable with earlier GPU inference timings.
- Exact test identity agreement and reference agreement within float32 rounding tolerance verified against the retained model CSVs.
- Metrics recomputed from exported CSVs; frozen source hashes and split disjointness verified.
- `qa/` shows the first six test IDs and the largest-error cases, explicitly chosen after evaluation for diagnosis. They illustrate diagnostic cases rather than a representative performance sample.

See `README.md` for the method, assumptions, citations and reproduction commands, and `verification.json` for numerical checks.
'''
    (HERE/'REPORT.md').write_text(text)
    print('\n'.join(table));print(json.dumps(verification,indent=2))

if __name__=='__main__':main()
