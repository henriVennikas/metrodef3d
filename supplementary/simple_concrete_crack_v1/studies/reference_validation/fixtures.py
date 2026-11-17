"""Analytical fixtures and independent double-precision expectations.
No imports from the production exporter or Blender.
"""
import math
import numpy as np

TARGETS=['centerline_length','mean_width','max_width','crack_area']

def camera(tilt=0, fov=100, resolution=1024, kind='perspective'):
    h=500.;t=math.radians(tilt)
    return dict(type=kind,position=[0,-h*math.tan(t),h],target=[0,0,0],resolution=[resolution,resolution],
                fov_degrees=math.degrees(2*math.atan(fov/(2*h))),fov_mm=fov,orthographic_scale=fov)

def footprint(cam):
    # Independently solve side-plane intersections on z=0. Square sensor, zero roll.
    h=cam['position'][2];theta=math.atan2(-cam['position'][1],h)
    c=math.cos(theta);s=math.sin(theta);d=h/c
    if cam['type']=='orthographic':
        x=cam['orthographic_scale']/2;y=x/c
        return np.array([[-x,-y],[x,-y],[x,y],[-x,y]])
    t=math.tan(math.radians(cam['fov_degrees'])/2)
    ys=[-t*d/(c+t*s),t*d/(c-t*s)]
    xs=[t*(d+y*s) for y in ys]
    return np.array([[-xs[0],ys[0]],[xs[0],ys[0]],[xs[1],ys[1]],[-xs[1],ys[1]]])

def cross(a,b):return float(a[0]*b[1]-a[1]*b[0])

def inside(p,poly,tol=1e-10):
    return all(cross(b-a,p-a)>=-tol for a,b in zip(poly,np.roll(poly,-1,axis=0)))

def intersection(a,b,c,d):
    v=b-a;w=d-c;den=cross(v,w)
    if abs(den)<1e-14:return None
    t=cross(c-a,w)/den;u=cross(c-a,v)/den
    return a+t*v if -1e-12<=t<=1+1e-12 and -1e-12<=u<=1+1e-12 else None

def convex_area_intersection(a,b):
    # Enumerate retained vertices and pairwise edge crossings, rather than
    # the production UV Sutherland-Hodgman clipping. Triangulate about centroid.
    pts=[p for p in a if inside(p,b)]+[p for p in b if inside(p,a)]
    for p,q in zip(a,np.roll(a,-1,axis=0)):
        for r,s in zip(b,np.roll(b,-1,axis=0)):
            x=intersection(p,q,r,s)
            if x is not None:pts.append(x)
    if len(pts)<3:return 0.
    pts=np.unique(np.round(pts,12),axis=0);ctr=pts.mean(axis=0)
    pts=pts[np.argsort(np.arctan2(pts[:,1]-ctr[1],pts[:,0]-ctr[0]))]
    return sum(abs(cross(p-ctr,q-ctr))/2 for p,q in zip(pts,np.roll(pts,-1,axis=0)))

def line_interval(a,b,poly):
    # World-plane half-space inequalities, no UV projection/reprojection.
    lo,hi=0.,1.;v=b-a
    for p,q in zip(poly,np.roll(poly,-1,axis=0)):
        c=cross(q-p,a-p);k=cross(q-p,v)
        if abs(k)<1e-14:
            if c<0:return None
        elif k>0:lo=max(lo,-c/k)
        else:hi=min(hi,-c/k)
    return (lo,hi) if hi>=lo else None

def point3(p):return [float(p[0]),float(p[1]),0.]

def strip(length=80,w0=2,w1=None,angle=0,shift=(0,0),step=1):
    w1=w0 if w1 is None else w1;n=max(1,math.ceil(length/step))
    a=math.radians(angle);v=np.array([math.cos(a),math.sin(a)]);normal=np.array([-v[1],v[0]])
    ss=np.linspace(-length/2,length/2,n+1);ws=np.linspace(w0,w1,n+1);pts=np.array(shift)+ss[:,None]*v
    left=pts+ws[:,None]/2*normal;right=pts-ws[:,None]/2*normal
    defect=dict(centerline=list(map(point3,pts)),left_boundary=list(map(point3,left)),right_boundary=list(map(point3,right)),width_profile=ws.tolist(),depth_profile=[1.]*(n+1))
    polygon=np.array([right[0],right[-1],left[-1],left[0]])
    return defect,polygon,pts[0],pts[-1]

def straight_case(name,cam,**kw):
    d,poly,a,b=strip(**kw);fp=footprint(cam);inter=line_interval(a,b,fp);area=convex_area_intersection(poly,fp)
    length=0.;mx=0.
    if inter:
        lo,hi=inter;length=float(np.linalg.norm(b-a))*(hi-lo)
        mx=max(d['width_profile'][0]+(d['width_profile'][-1]-d['width_profile'][0])*t for t in inter)
    expected=dict(zip(TARGETS,[length,area/length if length>1e-12 else 0.,mx,area]))
    # Degenerate edge-only area can occur without a centreline. No width reference
    # is defined there: the study records exporter behavior rather than filling it.
    return dict(id=name,group='straight',camera=cam,defect=d,expected=expected,oracle='closed-form segment / independent convex world-plane intersection',parameters=kw)

def build():
    cases=[]
    for kind in ['perspective','orthographic']:
        for label,opts in [('constant',{}),('tapered',dict(w0=1,w1=3)),('rigid',dict(angle=31,shift=(3,-4))),('clipped',dict(length=140)),('width_clipped',dict(shift=(0,49.5))),('excluded',dict(shift=(0,60)))]:
            cases.append(straight_case(kind+'_'+label,camera(kind=kind),**opts))
    for tilt in [0,5,15,30]:
        for fov in [50,100,150]:
            for angle in [0,37,90]:
                c=straight_case(f'tilt{tilt}_fov{fov}_angle{angle}',camera(tilt=tilt,fov=fov),length=180,w0=1,w1=3,angle=angle,step=.2);c['group']='projection';cases.append(c)
    for step in [5,1,.2,.1,.05]:
        c=straight_case(f'straight_step_{step}',camera(tilt=15),length=180,w0=1,w1=3,angle=37,step=step);c['group']='sampling_straight';cases.append(c)
    for n in [8,16,32,64,128,256,512]:
        R=30.;w=2.;theta=math.pi/2;tt=np.linspace(-theta/2,theta/2,n+1)
        pts=np.column_stack([R*np.sin(tt),R*np.cos(tt)-R]);left=np.column_stack([(R-w/2)*np.sin(tt),(R-w/2)*np.cos(tt)-R]);right=np.column_stack([(R+w/2)*np.sin(tt),(R+w/2)*np.cos(tt)-R])
        d=dict(centerline=list(map(point3,pts)),left_boundary=list(map(point3,left)),right_boundary=list(map(point3,right)),width_profile=[w]*(n+1),depth_profile=[1.]*(n+1))
        length=2*R*n*math.sin(theta/(2*n));area=R*w*n*math.sin(theta/n)
        cases.append(dict(id=f'arc_n{n}',group='sampling_arc',camera=camera(),defect=d,expected=dict(zip(TARGETS,[length,area/length,w,area])),smooth_expected=dict(zip(TARGETS,[R*theta,w,w,R*w*theta])),oracle='L=2Rn sin(theta/2n), A=Rwn sin(theta/n)',parameters=dict(radius=R,width=w,theta=theta,segments=n)))
    for resolution in [256,512,1024,2048,4096]:
        c=straight_case(f'resolution_{resolution}',camera(tilt=15,resolution=resolution),length=140,angle=37,w0=1,w1=3,step=.2);c['group']='resolution';cases.append(c)
    for eps in [-.01,-.0001,0,.0001,.01]:
        c=straight_case(f'boundary_only_{eps}',camera(),shift=(0,51+eps));c['group']='boundary_stress';cases.append(c)
    # One continuous strip leaves and re-enters the frame. Each visible arm has
    # length sqrt(40²+70²)*50/70. Their out-of-frame connection must not be counted.
    pts=np.array([[-40,0],[0,70],[40,0]],float);offset=np.array([0,1.]);d=dict(centerline=list(map(point3,pts)),left_boundary=list(map(point3,pts+offset)),right_boundary=list(map(point3,pts-offset)),width_profile=[2.]*3,depth_profile=[1.]*3)
    cases.append(dict(id='exit_reentry',group='topology_stress',camera=camera(),defect=d,expected={'centerline_length':2*math.hypot(40,70)*50/70},oracle='sum of two visible arm lengths; no bridge',parameters={}))
    # Centreline exactly on the frame edge, nonzero opening remains inside.
    c=straight_case('centreline_on_edge',camera(),shift=(0,50));c['group']='boundary_stress';cases.append(c)
    return cases

if __name__=='__main__':
    import json
    from pathlib import Path
    path=Path(__file__).resolve().parent/'fixtures.json';path.write_text(json.dumps(build(),indent=2)+'\n');print(len(build()),'fixtures')
