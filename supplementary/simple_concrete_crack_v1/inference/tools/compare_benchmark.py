"""Compare actual release inference with the archived benchmark, without fitting."""
import argparse,csv,json
from pathlib import Path
import numpy as np
from metrodef_models.evaluation import metrics


def compare(model_dir, run_dir, reference_dir):
    cfg=json.loads((model_dir/'config.json').read_text())
    status=json.loads((run_dir/'status.json').read_text())
    if not status['full_test_partition']:
        raise ValueError('A partial smoke run cannot reproduce the benchmark')
    rows=list(csv.DictReader((run_dir/'predictions.csv').open()))
    ref=list(csv.DictReader((reference_dir/'test_predictions.csv').open()))
    if [(x['seed'],x['stream']) for x in rows] != [(x['seed'],x['stream']) for x in ref]:
        raise ValueError('Test identities/order differ')
    for t in cfg['targets']:
        if [float(x[t+'_actual']) for x in rows]!=[float(x[t+'_actual']) for x in ref]:
            raise ValueError(f'Geometric references differ: {t}')
    calculated=metrics(rows,cfg); expected=metrics(ref,cfg)
    report={'model':cfg['model_id'],'samples':len(rows),'paired_references_exact':True,
            'original_precision':'CUDA bfloat16 autocast; float32 denormalisation',
            'run_environment':json.loads((run_dir/'environment.json').read_text()),
            'interpretation':'Numerical comparison, not a new training run. Cross-device and precision differences are reported, not hidden behind a pass threshold.',
            'targets':{}}
    for j,t in enumerate(cfg['targets']):
        delta=np.array([float(x[t+'_mu'])-float(y[t+'_mu']) for x,y in zip(rows,ref)])
        report['targets'][t]={'prediction_difference':{'max_abs':float(abs(delta).max()),'mean_abs':float(abs(delta).mean()),'bitwise_equal_count':int((delta==0).sum())},
            'metrics':{k:{'original':expected[j][k],'release':calculated[j][k],'difference':calculated[j][k]-expected[j][k]} for k in calculated[j] if k not in ['target','unit'] and calculated[j][k] is not None}}
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-dir',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=compare(a.model_dir,a.run,a.reference)
    with a.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    for target,result in report['targets'].items():
        m=result['metrics'];print(target,'MARE original/release',m['positive_mare_percent'],'coverage',m['coverage_percent'])
