"""Reproducible local selection, calibration and held-out evaluation."""
import os
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from pathlib import Path
import argparse, csv, hashlib, json, platform, time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from PIL import Image
from skimage.draw import polygon
from pipeline import TARGETS, predict, geometry

HERE = Path(__file__).resolve().parent

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, obj): Path(p).write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')
def read(p): return json.loads(Path(p).read_text())

def metadata_paths(root):
    index = {}
    for p in Path(root).glob('*/json/*.json'):
        if p.stem.isdigit():
            seed = int(p.stem)
            if seed in index: raise ValueError(f'Duplicate seed {seed}')
            index[seed] = p
    return index


def load(path):
    meta = read(path)
    cap = next(c for c in meta['outputs']['captures'] if c['capture_id'] == 'perspective-area')
    root = Path(path).parent.parent
    # Paths are rebased to the corresponding immutable run chunk.
    rgb = np.asarray(Image.open(root/'img'/Path(cap['image']).name).convert('RGB'))
    with np.load(root/'pixel_scale'/Path(cap['pixel_scale_sidecar']).name) as f:
        sx, sy = f['scale_x_mm_per_px'], f['scale_y_mm_per_px']
        if not np.all(f['valid_surface']):raise ValueError('Invalid scale surface')
    truth = read(root/'visible_defect'/Path(cap['visible_defect_sidecar']).name)
    if rgb.shape != (1024, 1024, 3):raise ValueError('Unexpected native resolution')
    return rgb, sx, sy, truth


def oracle_mask(truth, shape):
    mask = np.zeros(shape, bool)
    vertices = np.asarray(truth['visible_polygon_pixels'])
    if len(vertices) >= 3:
        # Generator pixel coordinates lie on pixel edges (0..W), centres at +0.5.
        rr, cc = polygon(vertices[:, 1]-.5, vertices[:, 0]-.5, shape)
        mask[rr, cc] = True
    return mask


def worker(task):
    seed, path, configs, oracle = task
    start=time.perf_counter();rgb,sx,sy,truth=load(path);rows=[]
    for config in configs:
        a, d = predict(rgb,sx,sy,config)
        row=dict(seed=seed, candidate=config['id'], **{t+'_actual':truth['measurands'][t] for t in TARGETS},
                 **{t+'_mu':a[t] for t in TARGETS}, **d)
        rows.append(row)
    if oracle:
        a,d=geometry(oracle_mask(truth,sx.shape),sx,sy,configs[0])
        rows.append(dict(seed=seed,candidate='reference_mask_diagnostic',
           **{t+'_actual':truth['measurands'][t] for t in TARGETS}, **{t+'_mu':a[t] for t in TARGETS}, **d))
    return rows,time.perf_counter()-start


def execute(seeds, index, configs, out, oracle=False, workers=4):
    if out.exists():raise FileExistsError(f'Will not overwrite {out}')
    out.parent.mkdir(parents=True,exist_ok=True)
    tasks=[(int(s),str(index[int(s)]),configs,oracle) for s in seeds]
    rows=[];timings=[];start=time.perf_counter()
    with out.open('w') as f, ProcessPoolExecutor(max_workers=workers) as pool:
        for i,(part,elapsed) in enumerate(pool.map(worker,tasks),1):
            rows.extend(part);timings.append(elapsed)
            for row in part:f.write(json.dumps(row,allow_nan=False)+'\n')
            f.flush()
            if i%16==0 or i==len(seeds):print(f'{out.stem}: {i}/{len(seeds)} ({time.perf_counter()-start:.1f}s)',flush=True)
    dump(out.with_suffix('.timing.json'),dict(wall_seconds=time.perf_counter()-start,
         summed_worker_seconds=sum(timings),workers=workers,n=len(seeds),oracle=oracle))
    return rows


def metrics(rows, bounds=None, floors=None):
    result=[]
    for j,t in enumerate(TARGETS):
        actual=np.array([r[t+'_actual'] for r in rows]);pred=np.array([r[t+'_mu'] for r in rows]);error=pred-actual;pos=actual>0
        r=dict(target=t,n=len(rows),n_positive=int(pos.sum()),unit='mm2' if t=='crack_area' else 'mm',
               mae=float(abs(error).mean()),rmse=float(np.sqrt((error**2).mean())),bias=float(error.mean()),
               mare_percent=float(100*(abs(error[pos])/actual[pos]).mean()) if pos.any() else None,
               r2=float(1-(error**2).sum()/((actual-actual.mean())**2).sum()) if actual.var()>0 else None)
        if bounds:
            lo=np.maximum(0,pred-bounds[t]);hi=pred+bounds[t]
            score=hi-lo+40*(np.maximum(lo-actual,0)+np.maximum(actual-hi,0))
            r.update(coverage_percent=float(100*((actual>=lo)&(actual<=hi)).mean()),
                     mean_interval_width=float((hi-lo).mean()),residual_radius=bounds[t],
                     relative_interval_score_percent=float(100*np.mean(score/np.maximum(abs(actual),floors[j]))))
        result.append(r)
    return result


def export_csv(path,rows,bounds=None):
    values=[]
    for row in rows:
        r=dict(row)
        if bounds:
            for t in TARGETS:r[t+'_lower']=max(0,r[t+'_mu']-bounds[t]);r[t+'_upper']=r[t+'_mu']+bounds[t]
        values.append(r)
    with Path(path).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','pilot','tune','calibrate','test'])
    ap.add_argument('--dataset',required=True);ap.add_argument('--split',required=True);ap.add_argument('--model-config',required=True)
    ap.add_argument('--workers',type=int,default=4);args=ap.parse_args()
    out=HERE/'results';out.mkdir(exist_ok=True)
    split=read(args.split);index=metadata_paths(args.dataset);config=read(args.model_config)
    if args.stage=='prepare':
        if (HERE/'protocol.json').exists():raise FileExistsError('Protocol already exists')
        valid=[s for s in split['val'] if s!=551]
        rng=np.random.default_rng(20261106);shuffle=rng.permutation(valid).tolist()
        base=dict(min_contrast=.02,min_area_px=32,min_path_px=20,min_elongation=3.,path_smoothing_sigma_px=2.)
        configs=[]
        for method in ['gaussian', 'closing']:
            for sigma in [15.,31.]:
                for ratio in [.2,.35,.5,.65]:
                    for closing in [0,1]:
                        configs.append(dict(id=f'{method}_s{int(sigma)}_r{ratio}_c{closing}',background_method=method,sigma_px=sigma,dark_ratio=ratio,closing_radius_px=closing,**base))
        protocol=dict(dataset_name='Simple Concrete Crack Dataset v1.0',stream='perspective-area',
          original_split_sha256=digest(args.split),original_model_config_sha256=digest(args.model_config),
          validation_exclusion=[551],tune_seeds=sorted(shuffle[:256]),calibration_seeds=sorted(shuffle[256:]),
          test_seeds=split['test'],pilot_seeds=split['train'][:12],candidates=configs,
          selection='minimum mean of four positive-reference MARE values; tie by candidate id',
          residual_bounds='per-target 0.95 empirical higher quantile of absolute residuals on reserved validation; lower bound clipped to zero',
          relative_floors=config['relative_floors'],created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
          platform=platform.platform(),local_paths=dict(dataset=args.dataset,split=args.split))
        # Ensure the benchmark normalisation floors match TARGETS ordering.
        assert config['targets']==TARGETS
        dump(HERE/'protocol.json',protocol);print('Protocol created, no evaluation performed.');return
    protocol=read(HERE/'protocol.json')
    assert digest(args.split)==protocol['original_split_sha256']
    if args.stage=='pilot':
        rows=execute(protocol['pilot_seeds'],index,[protocol['candidates'][10]],out/'pilot.jsonl',True,args.workers)
        dump(out/'pilot_metrics.json',{c:metrics([r for r in rows if r['candidate']==c]) for c in sorted({r['candidate'] for r in rows})});return
    if args.stage=='tune':
        rows=execute(protocol['tune_seeds'],index,protocol['candidates'],out/'tuning.jsonl',False,args.workers)
        scores=[]
        for c in protocol['candidates']:
            m=metrics([r for r in rows if r['candidate']==c['id']]);scores.append(dict(id=c['id'],score=float(np.mean([v['mare_percent'] for v in m])),metrics=m))
        scores.sort(key=lambda s:(s['score'],s['id']));dump(out/'tuning_summary.json',scores)
        best=next(c for c in protocol['candidates'] if c['id']==scores[0]['id'])
        dump(HERE/'selected.json',dict(config=best,selection_score=scores[0]['score'],protocol_sha256=digest(HERE/'protocol.json'),
             source_sha256={n:digest(HERE/n) for n in ['pipeline.py','run_benchmark.py']},
             frozen_before_calibration_and_test_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
        print('Selected',best['id'],scores[0]['score']);return
    selected=read(HERE/'selected.json')
    for n,h in selected['source_sha256'].items():
        if digest(HERE/n)!=h:raise ValueError('Frozen source changed: '+n)
    if args.stage=='calibrate':
        rows=execute(protocol['calibration_seeds'],index,[selected['config']],out/'calibration.jsonl',False,args.workers)
        radii={t:float(np.quantile([abs(r[t+'_mu']-r[t+'_actual']) for r in rows],.95,method='higher')) for t in TARGETS}
        dump(HERE/'calibration.json',dict(radii=radii,n=len(rows),selected_sha256=digest(HERE/'selected.json'),
             frozen_before_test_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
        dump(out/'calibration_metrics.json',metrics(rows,radii,protocol['relative_floors']));export_csv(out/'calibration_predictions.csv',rows,radii);return
    calibration=read(HERE/'calibration.json')
    assert calibration['selected_sha256']==digest(HERE/'selected.json')
    rows=execute(protocol['test_seeds'],index,[selected['config']],out/'test.jsonl',True,args.workers)
    image=[r for r in rows if r['candidate']!='reference_mask_diagnostic'];oracle=[r for r in rows if r['candidate']=='reference_mask_diagnostic']
    dump(out/'test_metrics.json',metrics(image,calibration['radii'],protocol['relative_floors']))
    dump(out/'reference_mask_metrics.json',metrics(oracle))
    export_csv(out/'test_predictions.csv',image,calibration['radii']);export_csv(out/'reference_mask_predictions.csv',oracle)
    print(json.dumps(read(out/'test_metrics.json'),indent=2))

if __name__=='__main__':main()
