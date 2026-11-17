"""Metrics from frozen predictions, including zero-reference observations."""
import numpy as np


def metrics(rows, config):
    result = []
    for j, t in enumerate(config['targets']):
        a, m, l, u = [np.array([float(r[t+'_'+s]) for r in rows]) for s in ['actual', 'mu', 'lower', 'upper']]
        if not all(np.isfinite(x).all() for x in [a, m, l, u]):
            raise ValueError('Nonfinite benchmark values')
        e = m-a
        positive = a > 0
        factor = config['interval_scales'][t]
        lo, hi = m-(m-l)*factor, m+(u-m)*factor
        score = hi-lo+40*(np.maximum(lo-a, 0)+np.maximum(a-hi, 0))
        ss = np.sum((a-a.mean())**2)
        result.append(dict(target=t, unit='mm2' if t == 'crack_area' else 'mm', n=len(a),
            n_positive=int(positive.sum()), mae=float(np.mean(abs(e))),
            rmse=float(np.sqrt(np.mean(e*e))), r2=float(1-np.sum(e*e)/ss) if ss else None,
            positive_mare_percent=float(100*np.mean(abs(e[positive])/a[positive])) if positive.any() else None,
            signed_bias=float(e.mean()), raw_coverage_percent=float(100*np.mean((l<=a)&(a<=u))),
            raw_mean_interval_width=float(np.mean(u-l)), calibration_scale=factor,
            coverage_percent=float(100*np.mean((lo<=a)&(a<=hi))),
            mean_interval_width=float(np.mean(hi-lo)),
            relative_interval_score_percent=float(100*np.mean(score/np.maximum(abs(a),config['relative_floors'][j])))))
    return result
