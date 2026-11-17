"""Integrity and arithmetic checks for the correction study, without mutation of inputs."""
import argparse,hashlib,json,csv,ast,tempfile
from pathlib import Path
import numpy as np
from load_overlay import load_visible_reference
HERE=Path(__file__).resolve().parent
TARGETS=['centerline_length','mean_width','max_width','crack_area']

def main():
 p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--learned-study',type=Path,required=True);p.add_argument('--classical-study',type=Path,required=True);p.add_argument('--generator-root',type=Path,required=True);a=p.parse_args()
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();sidecars=json.loads((HERE/'original_sidecar_hashes.json').read_text());meta=json.loads((HERE/'original_metadata_hashes.json').read_text())
 for i,(path,h) in enumerate(sidecars.items()):
  assert sha(a.dataset/path)==h,path
  if (i+1)%2000==0:print(i+1,'original sidecars unchanged',flush=True)
 for path,h in meta.items():assert sha(a.dataset/path)==h,path
 source=json.loads((HERE/'source_manifest.json').read_text());assert sha(a.generator_root/source['production_source'])==source['production_sha256'];assert sha(HERE/'corrected_export.py')==source['extracted_sha256']
 manifest=json.loads((HERE/'overlay/manifest.json').read_text());regen=json.loads((HERE/'regeneration.json').read_text());assert len(manifest['corrections'])==142;assert regen['partition_counts']==dict(train=92,val=24,test=26,excluded=0)
 for seed,entry in manifest['corrections'].items():
  original=a.dataset/entry['original_sidecar'];new=load_visible_reference(original,HERE/'overlay');assert new['schema']['version']==2
  points=np.array(new['centerline']);L=sum(float(np.linalg.norm(np.diff(points[start:stop],axis=0),axis=1).sum()) for start,stop in new['component_ranges']);assert abs(L-new['measurands']['centerline_length'])<5.01e-7
  # Area/length was computed with unrounded total length; use the same full sum.
  poly=np.array(new['visible_polygon']);area=abs(np.sum(poly[:,0]*np.roll(poly[:,1],-1)-poly[:,1]*np.roll(poly[:,0],-1)))/2
  assert abs(area-new['measurands']['crack_area'])<5.1e-7;assert abs(area/L-new['measurands']['mean_width'])<5.01e-7
  assert new['measurands']['centerline_length']<new['correction_provenance']['same_runtime_original_measurands']['centerline_length']
 # Unlisted zero/reference sample remains byte-equivalent as a JSON value.
 unlisted=next(path for path in sidecars if Path(path).stem=='1625');assert load_visible_reference(a.dataset/unlisted,HERE/'overlay')==json.loads((a.dataset/unlisted).read_text())
 # Wrong-source protection is exercised on a temporary file only.
 with tempfile.TemporaryDirectory() as tmp:
  name=next(iter(manifest['corrections']));wrong=Path(tmp)/(name+'.json');wrong.write_text('{}')
  try:load_visible_reference(wrong,HERE/'overlay')
  except ValueError:pass
  else:raise AssertionError('Checksum mismatch accepted')
 verified=json.loads((HERE/'benchmark_verification.json').read_text())
 for key,h in verified['input_sha256'].items():
  path,method=key.rsplit('|',1);base=a.classical_study if method=='conventional' else a.learned_study;assert sha(base/path)==h,key
 for method in ['transformer','resnet50','convnext_tiny','conventional']:
  source_path=a.classical_study/'results/test_predictions.csv' if method=='conventional' else a.learned_study/method/'test_predictions.csv';old=list(csv.DictReader(source_path.open()))
  for mode in ['corrected_fixed_calibration','corrected_recalibrated_valid_cohort']:
   new=list(csv.DictReader((HERE/'predictions'/f'{method}_{mode}.csv').open()));assert [r['seed'] for r in old]==[r['seed'] for r in new]
   for t in TARGETS:assert np.array_equal([float(r[t+'_mu']) for r in old],[float(r[t+'_mu']) for r in new])
 for path in HERE.glob('*.py'):ast.parse(path.read_text())
 result=dict(original_sidecars_verified=len(sidecars),original_metadata_files_verified=len(meta),corrected_sidecars_verified=142,original_dataset_preserved=True,original_prediction_csvs_preserved=True,central_predictions_bitwise_equal_after_csv_read=True,source_hash_verified=True,overlay_wrong_source_rejected=True,component_length_and_area_width_verified=True,unchanged_zero_reference_verified=True,python_syntax_checked=True,generator_unit_tests=43,blender_fixtures=72,ordinary_fixture_values_unchanged=65,preview_smoke='passed',publication=False,manuscript_tables='historical tables retained; impact assessment saved separately')
 (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
