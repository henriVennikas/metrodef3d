import json
from pathlib import Path
import numpy as np
import pytest
import torch
from PIL import Image
from metrodef_models.inputs import image_input, resolve_sidecar, metadata_index
from metrodef_models.evaluation import metrics


def test_rectangular_resize_preserves_directional_scale(tmp_path):
    p=tmp_path/'image.png';Image.new('RGB',(8,4),(128,64,32)).save(p)
    x=image_input(p,size=2,mm_per_pixel=.5)
    assert x.shape==(1,4,2,2)
    np.testing.assert_allclose(x[0,3],np.sqrt(2.0),rtol=1e-7)
    np.testing.assert_allclose(x[0,:3,0,0],[128/255,64/255,32/255],rtol=1e-7)


def test_model_grid_not_scaled_twice(tmp_path):
    p=tmp_path/'image.png';Image.new('RGB',(8,8)).save(p)
    s=tmp_path/'scale.npz';np.savez(s,scale_x_mm_per_px=np.ones((2,2))*.2,scale_y_mm_per_px=np.ones((2,2))*.8)
    assert torch.allclose(image_input(p,2,s,scale_grid='model')[0,3],torch.full((2,2),.4))
    with pytest.raises(ValueError,match='declared grid'):image_input(p,2,s)


@pytest.mark.parametrize('scale',[0,-1,float('nan'),float('inf')])
def test_invalid_scales_rejected(tmp_path,scale):
    p=tmp_path/'image.png';Image.new('RGB',(4,4)).save(p)
    with pytest.raises(ValueError,match='positive'):image_input(p,2,mm_per_pixel=scale)


def test_scale_is_required(tmp_path):
    with pytest.raises(ValueError,match='exactly one'):image_input(tmp_path/'image.png')


def test_paths_are_rebased_without_escaping(tmp_path):
    root=tmp_path/'newrun';(root/'json').mkdir(parents=True);(root/'img').mkdir()
    image=root/'img/3.jpg';image.touch();meta=root/'json/3.json'
    assert resolve_sidecar(meta,'/old/runs/newrun/img/3.jpg')==image
    assert resolve_sidecar(meta,'/old/runs/renamed_run/img/3.jpg')==image
    with pytest.raises(ValueError):resolve_sidecar(meta,'../outside.jpg')


def test_duplicate_seeds_fail(tmp_path):
    for name in ['a','b']:
        p=tmp_path/name/'json';p.mkdir(parents=True);(p/'1.json').write_text('{}')
    with pytest.raises(ValueError,match='Ambiguous'):metadata_index(tmp_path)


def test_zero_reference_kept_but_excluded_from_mare():
    rows=[{'width_actual':0,'width_mu':10,'width_lower':9,'width_upper':11},
          {'width_actual':2,'width_mu':3,'width_lower':2,'width_upper':4}]
    cfg={'targets':['width'],'interval_scales':{'width':2},'relative_floors':[.1]}
    m=metrics(rows,cfg)[0]
    assert m['n']==2 and m['n_positive']==1 and m['positive_mare_percent']==50
    assert m['mae']==5.5 and m['coverage_percent']==50 and m['mean_interval_width']==4
    assert m['relative_interval_score_percent']>100000
