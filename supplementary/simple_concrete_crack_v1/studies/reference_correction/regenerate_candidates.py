"""Re-export candidates into an additive overlay, never into the source dataset."""
import argparse,sys,json,hashlib,importlib.util,time
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import corrected_export as corrected
p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--original-export',type=Path,required=True);p.add_argument('--split',type=Path,required=True);args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
spec=importlib.util.spec_from_file_location('original_export',args.original_export);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
original_hashes=json.loads((HERE/'original_sidecar_hashes.json').read_text());candidate=json.loads((HERE/'candidate_screen.json').read_text());seeds=[r['seed'] for r in candidate['candidates']];controls=sorted(set([1,2,8,9,551,1625,8532,9999])-set(seeds));parts=json.loads(args.split.read_text());partition={int(s):k for k in ['train','val','test'] for s in parts[k]};paths={int(p.stem):p for p in args.dataset.glob('seeds_*/json/*.json')}
out=HERE/'overlay';assert not out.exists();(out/'visible_defect').mkdir(parents=True);rows=[];start=time.perf_counter();targets=['centerline_length','mean_width','max_width','crack_area'];inputs={}
for number,seed in enumerate(seeds+controls):
 path=paths[seed];raw=path.read_bytes();meta=json.loads(raw);cap=next(c for c in meta['outputs']['captures'] if c['capture_id']=='perspective-area');camera=cap['camera'];assert camera['resolution']==[1024,1024]
 original_path=path.parent.parent/'visible_defect'/path.name;original_raw=original_path.read_bytes();original_hash=hashlib.sha256(original_raw).hexdigest();assert original_hash==original_hashes[str(original_path.relative_to(args.dataset))];original=json.loads(original_raw)
 inputs[str(path.relative_to(args.dataset))]=hashlib.sha256(raw).hexdigest()
 scene=bpy.context.scene;scene.render.resolution_x,scene.render.resolution_y=camera['resolution'];scene.render.resolution_percentage=100;scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1
 cam=corrected.configure_camera(camera,str(seed));old_rerun=old.visible_defect_from_blender_camera(scene,cam,meta['defect'],camera);new=corrected.visible_defect_from_blender_camera(scene,cam,meta['defect'],camera)
 changed=new['measurands']!=old_rerun['measurands'];multiple=len(new['component_ranges'])>1
 assert all(new['measurands'][t] is not None for t in targets),(seed,'unexpected undefined target')
 if seed in controls:assert not changed and not multiple,(seed,'control changed')
 if multiple:
  new['correction_provenance']=dict(original_dataset='MetroDef3D Simple Concrete Crack Dataset v1.0',original_sidecar=str(original_path.relative_to(args.dataset)),original_sha256=original_hash,original_metadata_sha256=inputs[str(path.relative_to(args.dataset))],correction='component-aware-2',blender_version=bpy.app.version_string,original_measurands=original['measurands'],same_runtime_original_measurands=old_rerun['measurands'])
  (out/'visible_defect'/path.name).write_text(json.dumps(new,indent=2,sort_keys=True)+'\n')
 row=dict(seed=seed,partition=partition.get(seed,'excluded'),role='candidate' if seed in seeds else 'control',corrected=multiple,components=len(new['component_ranges']),original_sha256=original_hash,original_metadata_sha256=inputs[str(path.relative_to(args.dataset))],original=original['measurands'],same_runtime_original=old_rerun['measurands'],corrected_measurands=new['measurands'],component_ranges=new['component_ranges'],runtime_seconds=time.perf_counter()-start)
 rows.append(row)
 data=cam.data;bpy.data.objects.remove(cam,do_unlink=True);bpy.data.cameras.remove(data)
 assert hashlib.sha256(original_path.read_bytes()).hexdigest()==original_hash;assert hashlib.sha256(path.read_bytes()).hexdigest()==inputs[str(path.relative_to(args.dataset))]
 if (number+1)%10==0:print(number+1,'of',len(seeds+controls),'completed',round(time.perf_counter()-start,1),'s',flush=True)
 (HERE/'regeneration_progress.json').write_text(json.dumps(dict(completed=number+1,total=len(seeds+controls),seconds=time.perf_counter()-start)))
summary=dict(correction_version='component-aware-2',blender=bpy.app.version_string,candidate_count=len(seeds),control_count=len(controls),corrected_count=sum(r['corrected'] for r in rows),partition_counts={k:sum(r['corrected'] and r['partition']==k for r in rows) for k in ['train','val','test','excluded']},seconds=time.perf_counter()-start,rows=rows)
(HERE/'regeneration.json').write_text(json.dumps(summary,indent=2)+'\n');(HERE/'original_metadata_hashes.json').write_text(json.dumps(inputs,indent=2)+'\n')
print('REGENERATION_COMPLETE',summary['corrected_count'],summary['partition_counts'],round(summary['seconds'],1),'seconds')
