"""Generate comparative article figure/table from frozen benchmark predictions."""
from pathlib import Path
import argparse, json, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
MODELS = [('transformer', 'Transformer', '#356c9b'),
          ('resnet50', 'ResNet-50', '#cc8635'),
          ('convnext_tiny', 'ConvNeXt-Tiny', '#568766')]
TARGETS = [('centerline_length', 'Centreline length', 'mm'),
           ('mean_width', 'Mean width', 'mm'),
           ('max_width', 'Maximum width', 'mm'),
           ('crack_area', 'Crack area', 'mm²')]

def wilson(k, n):
    z = 1.959963984540054
    p = k / n
    den = 1 + z*z/n
    centre = (p + z*z/(2*n))/den
    half = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return 100*np.array([centre-half, centre+half])

def build(source):
    comparison = pd.read_csv(source/'comparison.csv')
    datasets = {m: pd.read_csv(source/m/'test_predictions.csv') for m,_,_ in MODELS}
    scales = {m: json.loads((source/m/'calibration.json').read_text())['posthoc_calibration']['interval_scales'] for m,_,_ in MODELS}
    reference = datasets['transformer']
    for frame in datasets.values():
        assert list(frame['seed']) == list(reference['seed'])
        for t,_,_ in TARGETS:
            np.testing.assert_array_equal(frame[t+'_actual'], reference[t+'_actual'])
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':7,
                         'axes.linewidth':.55, 'pdf.fonttype':42})
    fig, axes = plt.subplots(4, 3, figsize=(7.2, 4.65),
        gridspec_kw={'width_ratios':[1.25,.95,1.25]})
    fig.subplots_adjust(left=.14, right=.992, bottom=.072, top=.872,
                        wspace=.23, hspace=.84)
    summaries = {'models':[name for _,name,_ in MODELS], 'targets':{},
                 'error_display_limits_percent':[-30,30],
                 'width_display_rule':'Maximum model-specific 99.5th percentile, rounded up to a shared readable limit; all data retained in box statistics',
                 'width_display_limits':{},
                 'source_sha256':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for m,_,_ in MODELS for p in [source/m/'test_predictions.csv',source/m/'calibration.json']}}
    checks = 0
    for row,(target,title,unit) in enumerate(TARGETS):
        err_ax, cov_ax, width_ax = axes[row]
        for ax in axes[row]:
            ax.set_ylim(.45,3.55)
            ax.set_yticks([3,2,1])
            ax.set_yticklabels([])
            ax.tick_params(axis='y',length=0)
            ax.tick_params(axis='x',labelsize=6.5,pad=1,length=2)
            ax.grid(axis='x',color='#dce1e6',linewidth=.5,zorder=0)
            for spine in ax.spines.values(): spine.set_color('#87929c')
        err_ax.set_yticklabels([name for _,name,_ in MODELS],fontsize=7)
        err_ax.axvline(0,color='#646d76',linestyle='--',linewidth=.6)
        err_ax.set_xlim(-33,33);err_ax.set_xticks([-30,-15,0,15,30])
        err_ax.set_xlabel('Error (%)',fontsize=7,labelpad=1)
        cov_ax.axvline(95,color='#646d76',linestyle='--',linewidth=.7)
        cov_ax.set_xlim(90,98);cov_ax.set_xticks([90,92,94,96,98])
        cov_ax.set_xlabel('Coverage (%)',fontsize=7,labelpad=1)
        width_ax.set_xlabel(unit,fontsize=7,labelpad=1)
        width_ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        widths_by_model={};summaries['targets'][target]={}
        for idx,(model,name,color) in enumerate(MODELS):
            d=datasets[model]; y=3-idx
            truth=d[target+'_actual'].to_numpy(); pred=d[target+'_mu'].to_numpy()
            positive=truth>0; error=100*(pred[positive]-truth[positive])/truth[positive]
            lower=pred-scales[model][target]*(pred-d[target+'_lower'].to_numpy())
            upper=pred+scales[model][target]*(d[target+'_upper'].to_numpy()-pred)
            width=upper-lower; widths_by_model[model]=width
            covered=int(np.sum((truth>=lower)&(truth<=upper)));coverage=100*covered/len(truth)
            ci=wilson(covered,len(truth))
            metrics=comparison[(comparison['model'].str.startswith(name if model!='convnext_tiny' else 'ConvNeXt'))&(comparison.target==target)].iloc[0]
            calculated={'positive_mare_percent':float(np.mean(abs(error))),
                        'rmse':float(np.sqrt(np.mean((pred-truth)**2))),
                        'coverage_percent':coverage,'mean_interval_width':float(np.mean(width))}
            for key,value in calculated.items():
                np.testing.assert_allclose(value,metrics[key],rtol=1e-10,atol=1e-10);checks+=1
            for ax,data in [(err_ax,error),(width_ax,width)]:
                ax.boxplot(data,positions=[y],orientation='horizontal',widths=.47,
                    patch_artist=True,showmeans=True,manage_ticks=False,
                    boxprops={'facecolor':color,'edgecolor':color,'alpha':.65,'linewidth':.7},
                    medianprops={'color':'#202a33','linewidth':.85},
                    meanprops={'marker':'D','markersize':2.6,'markerfacecolor':'#202a33','markeredgecolor':'#202a33','markeredgewidth':.3},
                    whiskerprops={'color':color,'linewidth':.7},capprops={'color':color,'linewidth':.7},
                    flierprops={'marker':'.','markersize':1.6,'markerfacecolor':color,'markeredgecolor':color,'alpha':.28})
            low=int(sum(error<-30));high=int(sum(error>30))
            # Mask the narrow outer strips before adding explicit tail markers.
            for left,right in [(-33,-30),(30,33)]:
                err_ax.axvspan(left,right,color='white',zorder=3)
            for n,x,marker,offset,align in [(low,-31,'<',6,'left'),(high,31,'>',-6,'right')]:
                if n:
                    err_ax.plot(x,y,marker=marker,color=color,markersize=3,zorder=4)
                    err_ax.annotate(str(n),(x,y),xytext=(offset,0),textcoords='offset points',
                        va='center',ha=align,fontsize=5.5,color=color,zorder=5,
                        bbox={'facecolor':'white','edgecolor':'none','pad':.2})
            cov_ax.errorbar(coverage,y,xerr=[[coverage-ci[0]],[ci[1]-coverage]],
                fmt='o',color=color,markersize=3.4,capsize=2,linewidth=1)
            summaries['targets'][target][model]={**calculated,'coverage_wilson_95_percent':ci.tolist(),
                'n':len(truth),'n_positive':int(sum(positive)),
                'error_tails_below_display':low,'error_tails_above_display':high}
        # Use one common scale for all models within each measurand.
        # Only the display is restricted; the boxes and metrics use every value.
        robust_max = max(float(np.quantile(w, .995)) for w in widths_by_model.values())
        step = 2 * 10 ** np.floor(np.log10(robust_max))
        width_limit = float(np.ceil(robust_max / step) * step)
        summaries['width_display_limits'][target] = [0, width_limit]
        width_ax.set_xlim(0, width_limit * 1.10)
        width_ax.set_xticks(np.linspace(0, width_limit, 5))
        width_ax.axvspan(width_limit, width_limit * 1.10, color='white', zorder=3)
        for idx, (model, name, color) in enumerate(MODELS):
            n = int(np.sum(widths_by_model[model] > width_limit))
            summaries['targets'][target][model]['width_tails_above_display'] = n
            if n:
                x, y = width_limit * 1.05, 3 - idx
                width_ax.plot(x, y, marker='>', color=color, markersize=3, zorder=4)
                width_ax.annotate(str(n), (x, y), xytext=(-6, 0), textcoords='offset points',
                    va='center', ha='right', fontsize=5.5, color=color, zorder=5,
                    bbox={'facecolor':'white', 'edgecolor':'none', 'pad':.2})
        box=err_ax.get_position();fig.text(.55,box.y1+.014,title,ha='center',va='bottom',fontsize=8,fontweight='bold')
    for ax,title in zip(axes[0],['Signed relative error','Calibrated coverage','Calibrated interval width']):
        box=ax.get_position();fig.text((box.x0+box.x1)/2,.96,title,ha='center',va='top',fontsize=8,fontweight='bold')
    for suffix,dpi in [('pdf',300),('png',220)]:fig.savefig(ROOT/f'intermodel_comparison.{suffix}',dpi=dpi)
    plt.close(fig)
    summaries['verified_metric_checks']=checks
    (ROOT/'intermodel_comparison.json').write_text(json.dumps(summaries,indent=2)+'\n')
    lines=[r'\begin{table*}[!b]',
      r'\caption{\revisiontext{Comparison of the three trained models on the common test partition. MARE uses 1493 positive references; other metrics use all 1494 observations. RMSE and mean interval width use the units stated for each measurand. Coverage, width, and score use calibrated bounds. The normalized interval score is defined in Eq.~\eqref{eq:relative_interval_score}. Bold values mark the lowest MARE, RMSE, and score within each group.}}',
      r'\label{tab:benchmark_results}',r'\centering',r'\renewcommand{\arraystretch}{1.08}',r'\setlength{\tabcolsep}{5pt}',
      r'\revisiontext{\begin{tabular}{llrrrrr}',r'\hline',
      r'Measurand & Model & MARE (\%) & RMSE & \shortstack{Coverage\\(\%)} & \shortstack{Mean interval\\width} & \shortstack{Normalized\\score (\%)} \\',r'\hline']
    for target,title,unit in TARGETS:
        group=comparison[comparison.target==target]
        for i,(model,name,color) in enumerate(MODELS):
            m=group[group.model.str.startswith(name if model!='convnext_tiny' else 'ConvNeXt')].iloc[0]
            label=(title+' ('+('mm$^2$' if target=='crack_area' else 'mm')+')') if i==0 else ''
            vals=[]
            for key in ['positive_mare_percent','rmse','coverage_percent','mean_interval_width','relative_interval_score_percent']:
                places=3 if key in ['rmse','mean_interval_width'] and target in ['mean_width','max_width'] else (1 if key in ['coverage_percent','relative_interval_score_percent'] else 2)
                value=f'{m[key]:.{places}f}'
                if key in ['positive_mare_percent','rmse','relative_interval_score_percent'] and m[key]==group[key].min():value=r'\textbf{'+value+'}'
                vals.append(value)
            lines.append(' & '.join([label,name]+vals)+r' \\')
        lines.append(r'\hline')
    lines += [r'\end{tabular}}',r'\end{table*}']
    (ROOT/'intermodel_table.tex').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'metric_checks':checks,'paired_references':True,'figure':'intermodel_comparison.pdf','table':'intermodel_table.tex'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=ROOT)
    build(parser.parse_args().source)
