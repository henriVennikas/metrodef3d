"""Known-answer checks on the independent fixture calculations."""
import math
import numpy as np
from fixtures import camera,footprint,straight_case,build

def test_square_footprint():
 np.testing.assert_allclose(footprint(camera()),[[-50,-50],[50,-50],[50,50],[-50,50]],atol=1e-12)

def test_rectangle_and_taper():
 for w0,w1 in [(2,2),(1,3)]:
  e=straight_case('test',camera(),w0=w0,w1=w1)['expected']
  np.testing.assert_allclose(list(e.values()),[80,2,w1,160],atol=1e-10)

def test_end_clipping():
 e=straight_case('test',camera(),length=140)['expected']
 np.testing.assert_allclose(list(e.values()),[100,2,2,200],atol=1e-10)

def test_lateral_clipping_definition():
 e=straight_case('test',camera(),shift=(0,49.5))['expected']
 np.testing.assert_allclose(list(e.values()),[80,1.5,2,120],atol=1e-10)

def test_rigid_invariance():
 for a in [-75,0,31,73]:
  e=straight_case('test',camera(),angle=a,shift=(2,3))['expected']
  np.testing.assert_allclose(list(e.values()),[80,2,2,160],atol=1e-10)

def test_tilt_crossing_closed_form():
 # Horizontal line at y=0 has visible width FOV/cos(tilt).
 e=straight_case('test',camera(tilt=30),length=180)['expected']
 assert abs(e['centerline_length']-100/math.cos(math.pi/6))<1e-10

def test_empty():
 assert not any(straight_case('test',camera(),shift=(0,60))['expected'].values())

def test_arc_expected_converges():
 arc=[x for x in build() if x['group']=='sampling_arc'];errors=[abs(x['expected']['centerline_length']-x['smooth_expected']['centerline_length']) for x in arc]
 assert all(a>b for a,b in zip(errors,errors[1:]))
 assert 3.9<errors[-2]/errors[-1]<4.1
