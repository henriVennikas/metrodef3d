from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
P=Path(__file__).resolve().parent;d=json.loads((P/'results.json').read_text());cs=d['cases'];(P/'figures').mkdir(exist_ok=True)
fig,axes=plt.subplots(1,2,figsize=(10,4.5),sharey=True)
for ax,ident in zip(axes,['IMG_8184','IMG_8162']):
 c=cs[ident];v=[r['values']['mean_width'] for r in c['annotations']];m=c['transformer_comparison']['mean_width']
 ax.axhspan(m['calibrated_lower'],m['calibrated_upper'],color='#df8b3c',alpha=.18,label='Synthetic-calibrated prediction bounds')
 ax.axhline(m['prediction'],color='#b46020',ls='--',lw=1.5,label='Retained transformer prediction')
 ax.scatter([0],[v[0]],marker='D',s=55,color='#626d7a',label='Adopted original')
 ax.plot(range(1,5),v[1:],'o-',color='#15638a',lw=1.5,label='Four new passes')
 ax.set_xticks(range(5),['Original','1','2','3','4']);ax.set_title(ident);ax.set_xlabel('Annotation pass');ax.grid(axis='y',alpha=.2);ax.set_ylim(.88,1.50)
axes[0].set_ylabel('Annotation-derived mean width (mm)')
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=2,fontsize=9,frameon=False)
fig.suptitle('Mean width across repeated annotations',fontsize=14);fig.subplots_adjust(bottom=.25,top=.84,wspace=.13)
fig.savefig(P/'figures/mean_width_passes.png',dpi=180);fig.savefig(P/'figures/mean_width_passes.pdf');plt.close(fig)
# Overlay uses original pixel coordinates, without modifying any source image.
colors=['#f1d34f','#16bbda','#ed6b44','#83c441','#cd75e0']
fig,axes=plt.subplots(2,2,figsize=(9,9))
for row,ident in enumerate(['IMG_8184','IMG_8162']):
 photo=np.asarray(Image.open(P/'inputs'/ident/(ident+'.jpeg')).convert('RGB'))
 anns=[json.loads((P/'inputs'/ident/f'annotation_{i}.json').read_text()) for i in range(5)]
 center=np.array(next(a['points'] for a in anns[0]['annotations'] if a['kind']=='centreline'));mid=center[len(center)//2]
 for col,ax in enumerate(axes[row]):
  ax.imshow(photo)
  for i,a in enumerate(anns):
   p=np.array(next(t['points'] for t in a['annotations'] if t['kind']=='boundary'));p=np.vstack([p,p[0]])
   ax.plot(p[:,0],p[:,1],color=colors[i],alpha=.85,lw=.8 if col==0 else 1.1,label='Original' if i==0 else f'Pass {i}')
  if col:ax.set_xlim(mid[0]-180,mid[0]+180);ax.set_ylim(mid[1]+180,mid[1]-180)
  ax.set_title(ident+(' · full image' if col==0 else ' · centre detail'));ax.axis('off')
fig.legend(*axes[0,0].get_legend_handles_labels(),loc='lower center',ncol=5,frameon=False);fig.tight_layout(rect=(0,.045,1,1));fig.savefig(P/'figures/boundary_overlays.png',dpi=170);plt.close(fig)
lines=['# Repeated annotation comparison: IMG_8184 and IMG_8162','',
'Four new boundary/centreline annotations per image are compared with the adopted original, using one fixed original inference scale and the unchanged reference calculations. No model inference or reference replacement is made in this study.','',
'![Mean width across passes](figures/mean_width_passes.png)','',
'## Mean width','',
'| Image | Five-annotation mean (mm) | Sample SD (mm) | Relative SD (%) | Four-new-only mean (mm) | Four-new-only SD (mm) |',
'|---|---:|---:|---:|---:|---:|']
for ident,c in cs.items():
 f=c['five'];n=c['four_new'];lines.append(f"| {ident} | {f['mean'][1]:.4f} | {f['sample_sd'][1]:.4f} | {f['relative_sd_percent'][1]:.2f} | {n['mean'][1]:.4f} | {n['sample_sd'][1]:.4f} |")
lines+=['','IMG_8579 is the previous completed repeated-annotation study. Its values here use the prior fixed image scale for comparison. The separate Metrosert-based uncertainty example remains unchanged.','',
'## Variability across all four quantities','',
'Sample standard deviations divided by the five-annotation means, in percent:','',
'| Image | Length | Mean width | Maximum width | Area |','|---|---:|---:|---:|---:|']
for ident,c in cs.items():lines.append('| '+ident+' | '+' | '.join(f'{v:.2f}' for v in c['five']['relative_sd_percent'])+' |')
lines+=['','## Interpretation','',
'IMG_8184 has closely grouped new width annotations (0.987–1.010 mm), with the original at 0.934 mm. The four new passes have a width SD of 0.0103 mm, compared with 0.0305 mm when the earlier original is included. The difference between sessions is therefore material.','',
'IMG_8162 shows progressive widening across the four new passes: 1.162, 1.271, 1.337 and 1.432 mm. Area also increases, while new centreline lengths remain close (SD 0.0364 mm). The operator reports varying starting location and tracing direction between passes. The ordered values are reported descriptively and are not treated as proof of dependence or independence.','',
'The observations support reporting image-specific annotation variability. They do not establish a general uncertainty for all cracks or prove that surface type caused the differences. The within-operator SD describes the observed spread, not absolute annotation accuracy or common boundary bias.','',
'For a hypothetical mean of independent repeats, s/√5 is 0.01365 mm for IMG_8184 and 0.06210 mm for IMG_8162 mean width. These are conditional calculations, not validated uncertainty values for the two means. The reduction applies only to a mean formed under independent-repeat assumptions. The [individual-reference uncertainty study](../reference_uncertainty/README.md) uses the full observed annotation covariance without this reduction.','',
'## Comparison with retained predictions','',
'The five-annotation mean is a sensitivity analysis, not a replacement for the adopted image reference. Predictions and synthetic-validation bounds are unchanged. Interval inclusion does not demonstrate real-domain coverage.','',
'| Image | Quantity | Five-annotation mean | Prediction | Bounds | Difference from mean (%) | Mean within bounds |','|---|---|---:|---:|---|---:|---|']
for ident in ['IMG_8184','IMG_8162']:
 for target,v in cs[ident]['transformer_comparison'].items():lines.append(f"| {ident} | {target} | {v['repeat_mean']:.4f} | {v['prediction']:.4f} | [{v['calibrated_lower']:.4f}, {v['calibrated_upper']:.4f}] | {v['signed_difference_from_mean_percent']:+.2f} | {'yes' if v['mean_within_bounds'] else 'no'} |")
lines+=['','## Geometry checks and provenance','',
'All ten boundary polygons have no detected self-intersections. Interior sampled centreline stations remain within their boundary polygons. Recalculated original values match their retained references to 10⁻⁹ in the respective physical units. Native photograph coordinates and a common homography are used within each image. Width probes are not substituted for polygon-derived mean width.','',
'One new trace (IMG_8184 pass 2) retains an “in-progress” UI status, but has a finished boundary, a finished centreline and no unfinished points. It is included following the author’s completion confirmation; no source metadata was edited. All other new traces are marked complete.','',
'The adopted originals and new passes have different session histories and earlier prediction exposure. They are not a fully blinded study. All passes are retained, including those with less favourable prediction agreement.','',
'![Boundary overlays](figures/boundary_overlays.png)','',
'## Reproduction','',
'Run `python3 analyze.py` to regenerate `results.json`, then `python3 make_report.py` to regenerate this report and the figures. Dependencies: NumPy, Pillow and Matplotlib. The fixed homographies, frozen annotations, original photographs and retained prediction vectors are in `inputs/`. `input_checksums.json` verifies the input copies. The geometry code uses 0.05 mm width-station spacing and a 1 mm tangent window, matching the existing reference procedure.','',
'Complete per-pass values, covariance matrices, single-annotation SD, conditional uncertainty of the mean, and the four-new-only sensitivity are saved in `results.json`. The [Metrosert uncertainty example](../uncertainty_example/README.md) documents the calibration chain separately. No files have been published.']
(P/'README.md').write_text('\n'.join(lines)+'\n')
print('Report and figures generated.')
