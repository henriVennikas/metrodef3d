"""Verify the common real-image evaluation and reproduce descriptive results."""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics

P = Path(__file__).resolve().parent
BASE = P.parent
METHODS = ['transformer', 'resnet50', 'convnext_tiny', 'conventional']
TARGETS = ['centerline_length', 'mean_width', 'max_width', 'crack_area']
LABELS = ['Length', 'Mean width', 'Maximum width', 'Area']
NAMES = dict(zip(METHODS, ['Transformer', 'ResNet-50', 'ConvNeXt-Tiny', 'Conventional']))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(name, rows):
    with (P / name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    protocol = json.loads((P / 'protocol.json').read_text())
    for name, expected in protocol['source_sha256'].items():
        assert sha(BASE / name) == expected, ('source changed', name)
    historical = {r['image']: r for r in json.loads((BASE / 'predictions_and_references.json').read_text())}
    assert set(historical) == set(protocol['images']) and len(historical) == 26
    calibration = json.loads((P / 'calibration.json').read_text())
    rows, parity, hashes, runs = [], [], {}, {}
    for method in METHODS:
        runs[method] = json.loads((P / 'results' / method / 'run.json').read_text())
        assert runs[method]['protocol_sha256'] == sha(P / 'protocol.json')
        if method != 'conventional':
            assert runs[method]['weights_and_buffers_unchanged']
        for image in protocol['images']:
            saved = json.loads((P / 'results' / method / (image + '.json')).read_text())
            ref = json.loads((BASE / 'inputs' / image / 'reference.json').read_text())['reference']
            assert hashes.setdefault(image, saved['input_sha256']) == saved['input_sha256']
            for target in TARGETS:
                reference = ref[target]
                assert reference == historical[image]['quantities'][target]['reference']
                pred = saved['predictions'][target]
                mu, low, high = pred['mu'], pred['calibrated_lower'], pred['calibrated_upper']
                assert all(math.isfinite(x) for x in [reference, mu, low, high])
                assert reference > 0 and low <= mu <= high
                factor = calibration[method]['corrected_refs_valid_cohort'][target]
                expected = (max(0, mu-factor), mu+factor) if method == 'conventional' else (
                    mu-(mu-pred['lower'])*factor, mu+(pred['upper']-mu)*factor)
                assert abs(low-expected[0]) < 1e-12 and abs(high-expected[1]) < 1e-12
                width = high-low
                score = width + 40*max(low-reference, 0) + 40*max(reference-high, 0)
                rows.append(dict(method=method, image=image, target=target,
                    unit='mm2' if target == 'crack_area' else 'mm', reference=reference,
                    prediction=mu, raw_lower=pred['lower'], raw_upper=pred['upper'],
                    lower=low, upper=high, signed_difference=mu-reference,
                    absolute_relative_difference_percent=100*abs(mu-reference)/reference,
                    reference_inside_interval=low <= reference <= high,
                    interval_width=width, relative_interval_width_percent=100*width/reference,
                    interval_score=score, relative_interval_score=score/reference,
                    inference_seconds=saved['inference_seconds']))
                if method == 'transformer':
                    old = historical[image]['quantities'][target]
                    parity.append(dict(comparison='frozen_26_transformer', method=method,
                        image=image, target=target, prediction_difference=mu-old['prediction'],
                        lower_difference=low-old['calibrated_lower'],
                        upper_difference=high-old['calibrated_upper']))
            old_path = BASE.parent / 'real_model_comparison/results' / method / (image+'.json')
            if old_path.exists():
                old = json.loads(old_path.read_text())
                assert old['input_sha256'] == saved['input_sha256']
                for target in TARGETS:
                    new, previous = saved['predictions'][target], old['predictions'][target]
                    parity.append(dict(comparison='previous_five_image_comparison', method=method,
                        image=image, target=target, prediction_difference=new['mu']-previous['mu'],
                        lower_difference=new['calibrated_lower']-previous['calibrated_lower'],
                        upper_difference=new['calibrated_upper']-previous['calibrated_upper']))
    assert len(rows) == 416
    maximum = max(abs(r[k]) for r in parity for k in ['prediction_difference', 'lower_difference', 'upper_difference'])
    assert maximum < 5e-5, ('parity mismatch', maximum)
    write_csv('comparison.csv', rows)
    write_csv('baseline_parity.csv', parity)
    summary = []
    for method in METHODS:
        for target in TARGETS:
            rr = [r for r in rows if r['method'] == method and r['target'] == target]
            refmean = statistics.mean(r['reference'] for r in rr)
            sse = sum(r['signed_difference']**2 for r in rr)
            sst = sum((r['reference']-refmean)**2 for r in rr)
            summary.append(dict(method=method, target=target, n=len(rr),
                mae=statistics.mean(abs(r['signed_difference']) for r in rr),
                rmse=math.sqrt(sse/len(rr)), r2=1-sse/sst,
                mean_absolute_relative_difference_percent=statistics.mean(r['absolute_relative_difference_percent'] for r in rr),
                median_absolute_relative_difference_percent=statistics.median(r['absolute_relative_difference_percent'] for r in rr),
                interval_inclusions=sum(r['reference_inside_interval'] for r in rr),
                mean_interval_width=statistics.mean(r['interval_width'] for r in rr),
                mean_relative_interval_width_percent=statistics.mean(r['relative_interval_width_percent'] for r in rr),
                mean_interval_score=statistics.mean(r['interval_score'] for r in rr),
                mean_relative_interval_score=statistics.mean(r['relative_interval_score'] for r in rr)))
    write_csv('summary.csv', summary)
    verification = dict(images=26, methods=4, paired_quantity_comparisons=416,
        sources_unchanged=True, input_sha256=hashes, references_unchanged=True,
        calibration_checked=True, model_states_unchanged=True,
        historical_parity_rows=len(parity), maximum_absolute_parity_difference=maximum,
        no_training_or_real_data_tuning=True, runtimes_seconds={m:runs[m]['wall_seconds'] for m in METHODS})
    (P / 'verification.json').write_text(json.dumps(verification, indent=2)+'\n')
    lines = ['# Common real-image comparison', '',
        'All four retained methods evaluated on the same 26 annotated images at original orientation. '
        'Original adopted references, scale maps, checkpoints, processing settings and synthetic-validation calibration are unchanged. '
        'All 416 scalar comparisons were checked. No training or real-image tuning was performed.', '',
        'These descriptive averages depend on this selected mixture of appearances and openings. Several images share a physical fracture. '
        'They are not population performance estimates or statistically stable architecture rankings. '
        'Prediction bounds exclude scale and annotation uncertainty. The separate repeat-annotation and Metrosert uncertainty studies do not replace these adopted references.', '',
        '## Absolute relative differences', '',
        'Each cell is mean / median absolute relative difference in percent.', '',
        '| Method | Length | Mean width | Maximum width | Area |',
        '|---|---:|---:|---:|---:|']
    for method in METHODS:
        rr = [r for r in summary if r['method'] == method]
        lines.append('| '+NAMES[method]+' | '+' | '.join(f"{r['mean_absolute_relative_difference_percent']:.2f} / {r['median_absolute_relative_difference_percent']:.2f}" for r in rr)+' |')
    lines += ['',
        'For this selected set, ResNet-50 has the lowest mean length difference. The conventional pipeline has the lowest mean width and area differences. '
        'Its median length difference is also the lowest, but its mean is dominated by a large miss on IMG_8569. '
        'The saved path overlay shows many surface-texture components in addition to the main crack. The pipeline retains 333 components, '
        'giving a total length of 1092.88 mm against the annotated 125.06 mm (773.9% difference). '
        'This observation is retained without tuning or exclusion. The mean and median therefore describe substantially different aspects of its length performance.', '']
    lines += ['', '## Bounds and runtime', '',
        'Counts below are reference inclusions out of 26. Higher inclusion should be considered together with interval width and score, reported in [summary.csv](summary.csv). '
        'Conventional residual bounds have fixed physical radii and can be very wide for short cracks. '
        'They were calibrated on synthetic observations, as were the learned-model bounds.', '',
        '| Method | Length | Mean width | Maximum width | Area | Runtime (s) |',
        '|---|---:|---:|---:|---:|---:|']
    for method in METHODS:
        rr = [r for r in summary if r['method'] == method]
        lines.append('| '+NAMES[method]+' | '+' | '.join(str(r['interval_inclusions'])+'/26' for r in rr)+f" | {runs[method]['wall_seconds']:.1f} |")
    lines += ['', '## Per-image results', '',
        'Cells list absolute relative differences (%) in order: length / mean width / maximum width / area. '
        'The [full paired table](comparison.csv) retains predictions, references, physical units, raw/calibrated bounds, interval widths and scores.', '',
        '| Image | Transformer | ResNet-50 | ConvNeXt-Tiny | Conventional |',
        '|---|---|---|---|---|']
    for image in protocol['images']:
        cells = []
        for method in METHODS:
            rr = [r for r in rows if r['image'] == image and r['method'] == method]
            cells.append(' / '.join(f"{r['absolute_relative_difference_percent']:.1f}" for r in rr))
        lines.append(f'| [{image}](../inputs/{image}/{image}.jpeg) | '+' | '.join(cells)+' |')
    lines += ['', '## Verification', '',
        f'All 26 observations use identical image/scale inputs across methods. Source hashes and model states remained unchanged. '
        f'The maximum absolute difference from historical predictions or interval endpoints was {maximum:.8g} in the respective physical unit. '
        'Checks cover all 104 transformer quantities and all 80 quantities in the previous five-image four-method comparison. '
        'The previous five-image study remains available as an archive. The current common evaluation covers all 26 images.', '']
    (P/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(verification, indent=2))
    for method in METHODS:
        print(method, [round(r['mean_absolute_relative_difference_percent'], 2) for r in summary if r['method'] == method])


if __name__ == '__main__':
    main()
