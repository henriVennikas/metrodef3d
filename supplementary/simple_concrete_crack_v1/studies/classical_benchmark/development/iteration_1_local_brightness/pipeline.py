"""Conventional dark-crack segmentation and physical geometric measurement.

This module accepts only image and scale arrays, never construction references.
Pixel coordinates denote centres, physical scales are mm/pixel. The diagonal
metric omits shear because directional sidecars do not encode the axis angle.
"""
import cv2
import numpy as np
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from skimage.morphology import skeletonize

TARGETS = ['centerline_length', 'mean_width', 'max_width', 'crack_area']
cv2.setNumThreads(1)


def segment(rgb, config):
    gray = cv2.cvtColor(rgb.astype(np.float32) / 255., cv2.COLOR_RGB2GRAY)
    background = cv2.GaussianBlur(gray, (0, 0), config['sigma_px'], borderType=cv2.BORDER_REFLECT)
    mask = gray < config['dark_ratio'] * np.maximum(background, 1 / 255.)
    if config['closing_radius_px']:
        mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE,
                               np.ones((3, 3), np.uint8), borderType=cv2.BORDER_REPLICATE) > 0
    return mask


def sample(array, points):
    return ndi.map_coordinates(array, [points[:, 1], points[:, 0]], order=1, mode='nearest')


def dominant_path(skeleton):
    """Two-sweep geodesic path; exact for tree skeletons, heuristic for loops."""
    ys, xs = np.nonzero(skeleton)
    if len(xs) < 2:
        return np.empty((0, 2))
    idx = np.full(skeleton.shape, -1, np.int32)
    idx[ys, xs] = np.arange(len(xs))
    rows, cols, costs = [], [], []
    h, w = skeleton.shape
    for dy, dx in [(0, 1), (1, -1), (1, 0), (1, 1)]:
        ny, nx = ys + dy, xs + dx
        ok = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
        ids = np.flatnonzero(ok)
        ids = ids[idx[ny[ids], nx[ids]] >= 0]
        if dx and dy:
            # Avoid diagonal shortcuts when an orthogonal link exists.
            ids = ids[~(skeleton[ys[ids], nx[ids]] | skeleton[ny[ids], xs[ids]])]
        a, b = ids, idx[ny[ids], nx[ids]]
        rows.extend(a); cols.extend(b); costs.extend([np.hypot(dx, dy)] * len(a))
        rows.extend(b); cols.extend(a); costs.extend([np.hypot(dx, dy)] * len(a))
    graph = coo_matrix((costs, (rows, cols)), shape=(len(xs), len(xs))).tocsr()
    dist = dijkstra(graph, directed=False, indices=0)
    a = int(np.argmax(np.where(np.isfinite(dist), dist, -1)))
    dist, pred = dijkstra(graph, directed=False, indices=a, return_predecessors=True)
    b = int(np.argmax(np.where(np.isfinite(dist), dist, -1)))
    path = [b]
    while b != a:
        b = int(pred[b])
        if b < 0:
            raise ValueError('Disconnected skeleton path')
        path.append(b)
    return np.column_stack((xs[path], ys[path])).astype(float)


def boundary_distance(mask, points, direction, max_distance=128., step=.5):
    """Bilinear 0.5 mask crossings, with image borders as clipping boundaries."""
    distances = np.arange(0, max_distance + step, step)
    coords = points[:, None, :] + direction[:, None, :] * distances[None, :, None]
    h, w = mask.shape
    inside = ((coords[..., 0] >= -.5) & (coords[..., 0] <= w-.5) &
              (coords[..., 1] >= -.5) & (coords[..., 1] <= h-.5))
    vals = ndi.map_coordinates(mask.astype(float),
        [coords[..., 1].ravel(), coords[..., 0].ravel()], order=1, mode='nearest').reshape(inside.shape)
    vals[~inside] = 0
    crossed = vals < .5
    first = crossed.argmax(axis=1)
    good = crossed.any(axis=1) & (first > 0)
    prev = np.maximum(first-1, 0)
    row = np.arange(len(points))
    t = np.divide(vals[row, prev]-.5, vals[row, prev]-vals[row, first],
                  out=np.zeros(len(points)), where=vals[row, prev]!=vals[row, first])
    result = (prev + t) * step
    result[~good] = np.nan
    # Exact distance to rectangular image boundary, rather than sampled overshoot.
    for axis, size in [(0, w), (1, h)]:
        d = direction[:, axis]
        edge = np.where(d > 0, size-.5, -.5)
        bound = np.divide(edge-points[:, axis], d, out=np.full(len(d), np.inf), where=abs(d)>1e-12)
        result = np.minimum(result, np.where(bound >= 0, bound, np.inf))
    return result


def geometry(mask, sx, sy, config, diagnostic=False):
    if mask.shape != sx.shape or mask.shape != sy.shape or mask.ndim != 2:
        raise ValueError('Mask and directional scale shapes must agree')
    if not (np.isfinite(sx).all() and np.isfinite(sy).all() and (sx > 0).all() and (sy > 0).all()):
        raise ValueError('Scales must be finite and positive')
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    retained = np.zeros(mask.shape, bool)
    lengths, maxwidths, paths = [], [], []
    for label in range(1, n):
        x, y, w, h, area = stats[label]
        if area < config['min_area_px']:
            continue
        # Crop for efficient skeletonization, with halo for correct boundary sampling.
        x0, y0 = max(0, x-2), max(0, y-2)
        x1, y1 = min(mask.shape[1], x+w+2), min(mask.shape[0], y+h+2)
        local = labels[y0:y1, x0:x1] == label
        path = dominant_path(skeletonize(local))
        if len(path) < 2:
            continue
        raw_length = np.linalg.norm(np.diff(path, axis=0), axis=1).sum()
        if raw_length < config['min_path_px']:
            continue
        # Thinning can curl terminal pixels toward rectangular cap corners.
        # Trim one local opening width before tangent estimation, then extend
        # along the stable interior tangent back to the observed boundary.
        edt = ndi.distance_transform_edt(local)
        radius = np.median(edt[path[:, 1].astype(int), path[:, 0].astype(int)])
        trim = min(max(2, int(np.ceil(2*radius))), 25, max(0, (len(path)-10)//4))
        if trim:
            path = path[trim:-trim]
        path += [x0, y0]
        path = ndi.gaussian_filter1d(path, config['path_smoothing_sigma_px'], axis=0, mode='nearest')
        # Direction from a five-step neighbourhood reduces grid-direction artefacts.
        i = np.arange(len(path)); delta = path[np.minimum(i+5, len(path)-1)]-path[np.maximum(i-5, 0)]
        tangent = delta / np.maximum(np.linalg.norm(delta, axis=1, keepdims=True), 1e-12)
        normal = np.column_stack((-tangent[:, 1], tangent[:, 0]))
        component = labels == label
        a = boundary_distance(component, path, normal)
        b = boundary_distance(component, path, -normal)
        widths_px = a+b
        finite = np.isfinite(widths_px) & (widths_px > 0)
        if not finite.any() or raw_length / np.median(widths_px[finite]) < config['min_elongation']:
            continue
        # Extend each terminal path point to the mask/field boundary.
        ends = path[[0, -1]]
        outward = tangent[[0, -1]] * np.array([[-1], [1]])
        ext = boundary_distance(component, ends, outward)
        extended = path.copy()
        for j, k in [(0, 0), (1, -1)]:
            if np.isfinite(ext[j]): extended[k] += outward[j]*ext[j]
        dp = np.diff(extended, axis=0); mid = (extended[:-1]+extended[1:])/2
        length = np.sqrt((dp[:, 0]*sample(sx, mid))**2+(dp[:, 1]*sample(sy, mid))**2).sum()
        width_scale = np.sqrt((normal[:, 0]*sample(sx, path))**2+(normal[:, 1]*sample(sy, path))**2)
        # Discard widths clipped by image borders: they are not full local openings.
        end_a = path + normal*a[:, None]; end_b = path-normal*b[:, None]
        hh, ww = mask.shape
        interior = np.ones(len(path), bool)
        for q in [end_a, end_b]:
            interior &= (q[:, 0] > -.49)&(q[:, 0] < ww-.51)&(q[:, 1] > -.49)&(q[:, 1] < hh-.51)
        good = finite & interior
        if not good.any(): good = finite
        lengths.append(float(length)); maxwidths.append(float(np.max(widths_px[good]*width_scale[good])))
        retained |= component; paths.append(extended)
    length = sum(lengths)
    area = float(np.sum((sx*sy)[retained], dtype=np.float64))
    result = dict(centerline_length=length, mean_width=area/length if length > 0 else 0.,
                  max_width=max(maxwidths, default=0.), crack_area=area)
    details = dict(components=len(lengths), mask_pixels=int(retained.sum()),
                   local_metric='diagonal_directional_scales')
    if diagnostic: details.update(mask=retained, paths=paths)
    return result, details


def predict(rgb, sx, sy, config, diagnostic=False):
    return geometry(segment(rgb, config), sx, sy, config, diagnostic)
