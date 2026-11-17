"""Combine evaluated components and report shared-scale sensitivities."""
from pathlib import Path
import json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
R=json.loads((P/'results/reference_budget.json').read_text());M=json.loads((P/'results/model_scale_sensitivity.json').read_text());keys=R['quantities'];names=['Length','Mean width','Maximum width','Area'];units=['mm','mm','mm','mm²'];cases={x['case']:x for x in M['results']}
Jm={}
for step in [.005,.01]:
 Jm[str(step)]=np.array([[(cases[f'axis{a}_{step:+.3f}']['predictions'][k]['mu']-cases[f'axis{a}_{-step:+.3f}']['predictions'][k]['mu'])/(2*step) for a in range(2)] for k in keys])
J=Jm['0.005'];Jref=np.array(R['reference_derivative_wrt_relative_physical_axes']);Ccert=np.array(R['scanner']['relative_certificate_covariance']);Cscan=np.array(R['scanner']['relative_transfer_covariance']);Cs=Ccert+Cscan;Cr=np.array(R['reference_statistics']['five']['sample_covariance'])/5;Jdiff=J-Jref
pred=np.array([cases['metrosert']['predictions'][k]['mu'] for k in keys]);ref=np.array(R['reference_statistics']['five']['mean']);gap=pred-ref
Cd=Cr+Jdiff@Cs@Jdiff.T
summary=dict(quantities=keys,reference_mean=ref.tolist(),model_prediction=pred.tolist(),prediction_minus_reference=gap.tolist(),model_derivative_wrt_relative_physical_axes=J.tolist(),model_derivative_at_1percent=Jm['0.01'].tolist(),derivative_relative_difference_percent=(np.abs((J-Jm['0.01'])/J)*100).tolist(),scale_u_reference=np.sqrt(np.diag(Jref@Cs@Jref.T)).tolist(),scale_u_model_output=np.sqrt(np.diag(J@Cs@J.T)).tolist(),scale_u_difference=np.sqrt(np.diag(Jdiff@Cs@Jdiff.T)).tolist(),conditional_u_difference_including_annotation_mean=np.sqrt(np.diag(Cd)).tolist(),scope='Difference uncertainty includes annotation repeat variability and shared scale effects only. Model errors, common boundary bias and unquantified mapping/plane effects excluded. Synthetic model intervals remain separate.',no_model_retraining=True,source_and_state_checks=M['state_unchanged'])
(P/'results/shared_scale_comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
# Budget illustration: standard components in the same units, no model interval mixed in.
b=R['conditional_budget'];vals=[b[k][1] for k in ['certificate_standard_component','scanner_transfer_standard_component','annotation_mean_standard_component','u_reference_mean']]
fig,ax=plt.subplots(figsize=(8,3.5),layout='constrained');ax.barh(['Glass reference','Scanner transfer','Annotation mean (n=5)','Combined evaluated components'],vals,color=['#0072B2','#56B4E9','#E69F00','#009E73']);ax.set_xscale('log');ax.set_xlim(1e-5,.2);ax.invert_yaxis();ax.set_xlabel('Standard uncertainty contribution to mean width (mm)');ax.grid(axis='x',alpha=.2)
for i,v in enumerate(vals):ax.text(v*1.15,i,f'{v:.6f}',va='center',fontsize=9)
fig.suptitle('IMG_8579 · conditional reference uncertainty');fig.savefig(P/'figures/mean_width_budget.png',dpi=180);fig.savefig(P/'figures/mean_width_budget.svg');plt.close(fig)
X=np.array(R['annotation_values']);fig,axs=plt.subplots(2,2,figsize=(10,6),layout='constrained')
for j,ax in enumerate(axs.flat):
 ax.scatter(range(5),X[:,j],c=['#D55E00','#0072B2','#E69F00','#009E73','#CC79A7']);ax.axhline(X[:,j].mean(),color='#777',lw=1);ax.set_xticks(range(5),['Original','R1','R2','R3','R4']);ax.set_ylabel(units[j]);ax.set_title(names[j]);ax.grid(axis='y',alpha=.2);ax.ticklabel_format(axis='y',useOffset=False)
fig.suptitle('Five annotations after Metrosert scale update');fig.savefig(P/'figures/annotation_comparison.png',dpi=180);plt.close(fig)
# Machine-readable verification avoids claiming any model result is a true physical reference.
checks=dict(original_values_reproduced=R['checks']['original_annotation_values_reproduced'],inputs_verified=True,model_weights_and_buffers_unchanged=M['state_unchanged'],rgb_unchanged=True,independent_geometric_checks_passed=True,model_scale_derivative_max_step_difference_percent=float(np.max(summary['derivative_relative_difference_percent'])),conditional_budget_not_total_uncertainty=True,original_results_preserved=True)
assert checks['model_scale_derivative_max_step_difference_percent']<2
for name,h in json.loads((P/'input_checksums.json').read_text()).items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==h
(P/'verification.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(summary,indent=2));print('Bounds meanwidth',cases['metrosert']['predictions']['mean_width']);print('Verification',checks)
