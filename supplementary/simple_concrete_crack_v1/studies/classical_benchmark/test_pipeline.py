import numpy as np
import pytest
from pipeline import geometry, predict

CFG = dict(background_method="closing", min_contrast=.02, min_area_px=8, min_path_px=8, min_elongation=2,
           path_smoothing_sigma_px=2., sigma_px=31., dark_ratio=.5, closing_radius_px=0)


def test_straight_strip_full_frame_anisotropic_scale():
    m = np.zeros((128, 128), bool); m[59:69, :] = True
    sx = np.full(m.shape, .2); sy = np.full(m.shape, .1)
    a, _ = geometry(m, sx, sy, CFG)
    assert a['crack_area'] == pytest.approx(25.6)
    assert a['centerline_length'] == pytest.approx(25.6, rel=.005)
    assert a['mean_width'] == pytest.approx(1., rel=.005)
    assert a['max_width'] == pytest.approx(1., rel=.005)


def test_vertical_rotation_swaps_directional_scale():
    m = np.zeros((128, 128), bool); m[:, 59:69] = True
    a, _ = geometry(m, np.full(m.shape, .2), np.full(m.shape, .1), CFG)
    assert a['centerline_length'] == pytest.approx(12.8, rel=.005)
    assert a['mean_width'] == pytest.approx(2., rel=.005)
    assert a['max_width'] == pytest.approx(2., rel=.005)


def test_two_disconnected_strips_are_summed():
    m = np.zeros((128, 128), bool); m[20:26, :] = True; m[80:86, :] = True
    a, d = geometry(m, np.ones(m.shape), np.ones(m.shape), CFG)
    assert d['components'] == 2
    assert a['centerline_length'] == pytest.approx(256, rel=.01)
    assert a['crack_area'] == 1536


def test_empty_image_and_mask():
    m = np.zeros((128, 128), bool)
    a, _ = geometry(m, np.ones(m.shape), np.ones(m.shape), CFG)
    assert all(v == 0 for v in a.values())
    b, _ = predict(np.full((128, 128, 3), 180, np.uint8), np.ones(m.shape), np.ones(m.shape), CFG)
    assert all(v == 0 for v in b.values())


def test_isotropic_scale_units_and_area_exponent():
    m = np.zeros((128, 128), bool); m[59:69, :] = True
    a, _ = geometry(m, np.ones(m.shape), np.ones(m.shape), CFG)
    b, _ = geometry(m, np.full(m.shape, 3.), np.full(m.shape, 3.), CFG)
    for k in ['centerline_length', 'mean_width', 'max_width']:
        assert b[k] == pytest.approx(a[k]*3)
    assert b['crack_area'] == pytest.approx(a['crack_area']*9)


def test_diagonal_strip_length_width():
    y, x = np.indices((160, 160)); m = abs(y-x) <= 4
    a, _ = geometry(m, np.ones(m.shape), np.ones(m.shape), CFG)
    assert a['centerline_length'] == pytest.approx(160*np.sqrt(2), rel=.02)
    assert a['mean_width'] == pytest.approx(9/np.sqrt(2), rel=.03)


def test_invalid_scale_fails():
    m = np.zeros((32, 32), bool)
    with pytest.raises(ValueError):geometry(m, np.zeros(m.shape), np.ones(m.shape), CFG)


def test_reference_mask_uses_pixel_centres():
    from run_benchmark import oracle_mask
    truth = {'visible_polygon_pixels': [[0, 10], [64, 10], [64, 20], [0, 20]]}
    m = oracle_mask(truth, (64, 64))
    assert m.sum() == 640
    assert np.all(m[10:20]) and not m[:10].any() and not m[20:].any()


def test_signed_error_and_zero_reference_metrics():
    from run_benchmark import metrics, TARGETS
    rows=[]
    for actual, pred in [(0., 2.), (10., 9.)]:
        rows.append({**{t+'_actual': actual for t in TARGETS}, **{t+'_mu': pred for t in TARGETS}})
    result = metrics(rows)
    for r in result:
        assert r['n'] == 2 and r['n_positive'] == 1
        assert r['mae'] == pytest.approx(1.5)
        assert r['mare_percent'] == pytest.approx(10.)
        assert r['bias'] == pytest.approx(.5)


def test_selection_calibration_test_disjoint():
    import json
    from pathlib import Path
    p=json.loads((Path(__file__).parent/'protocol.json').read_text())
    a,b,c=[set(p[k]) for k in ['tune_seeds','calibration_seeds','test_seeds']]
    assert len(a)==256 and len(b)==1237 and len(c)==1494
    assert not (a&b or a&c or b&c)
    assert 551 not in a|b|c
