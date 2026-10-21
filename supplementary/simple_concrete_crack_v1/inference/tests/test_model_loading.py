"""Small CPU-only loading checks; no downloaded or released weights needed."""
import hashlib,json
import pytest
import torch
from metrodef_models.engine import Predictor,build_model


@pytest.fixture
def tiny_asset(tmp_path):
    config=dict(model='ScalarSegmentationTransformer',model_id='test',image_size=32,
        in_channels=4,embed_dim=32,dropout=.1,min_delta=1e-4,interval_mode='asymmetric',
        segmentation_head=True,token_stride=16,depth=1,num_heads=4,mlp_ratio=2.,
        targets=['length'],target_mean=[10],target_std=[2],interval_scales={'length':1.5},
        batchnorm_policy='eval',exclude_seeds=[7])
    model=build_model(config);torch.save(model.state_dict(),tmp_path/'weights.pt')
    config['weights_sha256']=hashlib.sha256((tmp_path/'weights.pt').read_bytes()).hexdigest()
    (tmp_path/'config.json').write_text(json.dumps(config))
    (tmp_path/'split_seeds.json').write_text(json.dumps({'train':[1],'val':[2],'test':[3]}))
    return tmp_path


def test_weights_tampering_rejected(tiny_asset):
    with (tiny_asset/'weights.pt').open('ab') as f:f.write(b'altered')
    with pytest.raises(ValueError,match='SHA-256'):Predictor(tiny_asset)


def test_batch_one_and_rgb_range(tiny_asset):
    p=Predictor(tiny_asset)
    with pytest.raises(ValueError,match='batch one'):p.predict(torch.ones(2,4,32,32))
    with pytest.raises(ValueError,match='RGB'):p.predict(torch.ones(1,4,32,32)*2)
    with pytest.raises(ValueError,match='positive'):p.predict(torch.zeros(1,4,32,32))
    assert [p.membership(s) for s in [1,2,3,7,12345]]==['train','val','test','excluded','outside_frozen_split']


def test_frozen_calibration_and_dense_parity(tiny_asset):
    p=Predictor(tiny_asset);x=torch.ones(1,4,32,32)*.2
    scalar,_=p.predict(x)
    p.model.has_segmentation_head=True
    full,dense=p.predict(x)
    assert full==scalar and dense['width_mm'].shape==(1,32,32)
    v=full['length']
    assert v['calibrated_lower']==v['mu']-(v['mu']-v['lower'])*1.5
    assert v['calibrated_upper']==v['mu']+(v['upper']-v['mu'])*1.5


def test_non_cuda_bfloat16_is_not_silently_changed(tiny_asset):
    with pytest.raises(ValueError,match='requires CUDA'):Predictor(tiny_asset,precision='bfloat16')
