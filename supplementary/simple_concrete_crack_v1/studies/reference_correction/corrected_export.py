"""Frozen corrected production functions; see source_manifest.json."""
import json, math
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
VERSIONING={"visible_defect_schema_version":2}

def interpolate_point(left, right, fraction):
    return [
        float(left[0]) + (float(right[0]) - float(left[0])) * fraction,
        float(left[1]) + (float(right[1]) - float(left[1])) * fraction,
        float(left[2]) + (float(right[2]) - float(left[2])) * fraction,
    ]

def interpolate_scalar(left, right, fraction):
    return float(left) + (float(right) - float(left)) * fraction

def polyline_length(points):
    total = 0.0
    for left, right in zip(points, points[1:]):
        total += math.sqrt(
            (float(right[0]) - float(left[0])) ** 2
            + (float(right[1]) - float(left[1])) ** 2
            + (float(right[2]) - float(left[2])) ** 2
        )
    return total

def polygon_area_xy(points):
    if len(points) < 3:
        return 0.0
    total = 0.0
    for left, right in zip(points, points[1:] + points[:1]):
        total += float(left[0]) * float(right[1]) - float(right[0]) * float(left[1])
    return abs(total) * 0.5

def clip_unit_square_interval(left_uvz, right_uvz):
    if left_uvz[2] <= 0.0 and right_uvz[2] <= 0.0:
        return None
    start = 0.0
    end = 1.0
    dx = right_uvz[0] - left_uvz[0]
    dy = right_uvz[1] - left_uvz[1]
    dz = right_uvz[2] - left_uvz[2]
    for p, q in (
        (-dx, left_uvz[0]),
        (dx, 1.0 - left_uvz[0]),
        (-dy, left_uvz[1]),
        (dy, 1.0 - left_uvz[1]),
        (-dz, left_uvz[2]),
    ):
        if abs(p) < 1.0e-12:
            if q < 0.0:
                return None
            continue
        value = q / p
        if p < 0.0:
            if value > end:
                return None
            if value > start:
                start = value
        else:
            if value < start:
                return None
            if value < end:
                end = value
    if start > end:
        return None
    return (max(0.0, start), min(1.0, end))

def uv_inside(point, edge):
    u = float(point[0])
    v = float(point[1])
    if edge == "left":
        return u >= 0.0
    if edge == "right":
        return u <= 1.0
    if edge == "bottom":
        return v >= 0.0
    if edge == "top":
        return v <= 1.0
    return False

def uv_intersection(left, right, edge):
    lu, lv = float(left[0]), float(left[1])
    ru, rv = float(right[0]), float(right[1])
    du = ru - lu
    dv = rv - lv
    if edge == "left":
        fraction = 0.0 if abs(du) < 1.0e-12 else (0.0 - lu) / du
    elif edge == "right":
        fraction = 0.0 if abs(du) < 1.0e-12 else (1.0 - lu) / du
    elif edge == "bottom":
        fraction = 0.0 if abs(dv) < 1.0e-12 else (0.0 - lv) / dv
    else:
        fraction = 0.0 if abs(dv) < 1.0e-12 else (1.0 - lv) / dv
    fraction = max(0.0, min(1.0, fraction))
    return (
        lu + du * fraction,
        lv + dv * fraction,
        float(left[2]) + (float(right[2]) - float(left[2])) * fraction,
    )

def clip_uv_polygon_to_unit_square(points):
    clipped = list(points)
    for edge in ("left", "right", "bottom", "top"):
        if not clipped:
            return []
        output = []
        previous = clipped[-1]
        previous_inside = uv_inside(previous, edge)
        for current in clipped:
            current_inside = uv_inside(current, edge)
            if current_inside:
                if not previous_inside:
                    output.append(uv_intersection(previous, current, edge))
                output.append(current)
            elif previous_inside:
                output.append(uv_intersection(previous, current, edge))
            previous = current
            previous_inside = current_inside
        clipped = output
    return clipped

def dedupe_points(points):
    deduped = []
    for point in points:
        rounded = round_point(point)
        if not deduped or rounded != deduped[-1]:
            deduped.append(rounded)
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    return deduped

def dedupe_pixel_points(points):
    deduped = []
    for point in points:
        rounded = [round(float(point[0]), 6), round(float(point[1]), 6)]
        if not deduped or rounded != deduped[-1]:
            deduped.append(rounded)
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    return deduped

def round_point(point):
    return [round(float(point[0]), 6), round(float(point[1]), 6), round(float(point[2]), 6)]

def uv_to_pixel(uv, camera):
    width = int(camera["resolution"][0])
    height = int(camera["resolution"][1])
    return [round(float(uv[0]) * width, 6), round((1.0 - float(uv[1])) * height, 6)]

def segment_fraction_for_point(left, right, point):
    dx = float(right[0]) - float(left[0])
    dy = float(right[1]) - float(left[1])
    dz = float(right[2]) - float(left[2])
    denom = dx * dx + dy * dy + dz * dz
    if denom <= 1.0e-18:
        return 0.0
    fraction = (
        (float(point[0]) - float(left[0])) * dx
        + (float(point[1]) - float(left[1])) * dy
        + (float(point[2]) - float(left[2])) * dz
    ) / denom
    return max(0.0, min(1.0, fraction))

def append_visible_sample(samples, point, pixel, width, depth, left_boundary, right_boundary, left_pixel, right_pixel, source_index, fraction):
    rounded = round_point(point)
    if samples["centerline"] and rounded == samples["centerline"][-1]:
        samples["width_profile"][-1] = round(float(width), 6)
        samples["depth_profile"][-1] = round(float(depth), 6)
        samples["left_boundary"][-1] = round_point(left_boundary)
        samples["right_boundary"][-1] = round_point(right_boundary)
        samples["centerline_pixels"][-1] = [round(float(pixel[0]), 6), round(float(pixel[1]), 6)]
        samples["left_boundary_pixels"][-1] = [round(float(left_pixel[0]), 6), round(float(left_pixel[1]), 6)]
        samples["right_boundary_pixels"][-1] = [round(float(right_pixel[0]), 6), round(float(right_pixel[1]), 6)]
        samples["source_profile"][-1] = {
            "segment_index": int(source_index),
            "segment_fraction": round(float(fraction), 6),
        }
        return
    samples["centerline"].append(rounded)
    samples["width_profile"].append(round(float(width), 6))
    samples["depth_profile"].append(round(float(depth), 6))
    samples["left_boundary"].append(round_point(left_boundary))
    samples["right_boundary"].append(round_point(right_boundary))
    samples["centerline_pixels"].append([round(float(pixel[0]), 6), round(float(pixel[1]), 6)])
    samples["left_boundary_pixels"].append([round(float(left_pixel[0]), 6), round(float(left_pixel[1]), 6)])
    samples["right_boundary_pixels"].append([round(float(right_pixel[0]), 6), round(float(right_pixel[1]), 6)])
    samples["source_profile"].append(
        {
            "segment_index": int(source_index),
            "segment_fraction": round(float(fraction), 6),
        }
    )

def visible_polygon_from_blender_camera(scene, camera_obj, defect):
    left_boundary = defect.get("left_boundary", [])
    right_boundary = defect.get("right_boundary", [])
    if len(left_boundary) < 2 or len(right_boundary) < 2:
        return [], []
    polygon = list(left_boundary) + list(reversed(right_boundary))
    uv_polygon = []
    for point in polygon:
        uv = world_to_camera_view(scene, camera_obj, Vector((float(point[0]), float(point[1]), float(point[2]))))
        if float(uv.z) <= 0.0:
            continue
        uv_polygon.append((float(uv.x), float(uv.y), float(uv.z)))
    clipped_uv = clip_uv_polygon_to_unit_square(uv_polygon)
    visible_polygon = []
    visible_polygon_pixels = []
    for u, v, _z in clipped_uv:
        world = ray_plane_intersection(camera_obj, float(u), float(v), 0.0)
        if world is not None:
            visible_polygon.append([float(world.x), float(world.y), 0.0])
            visible_polygon_pixels.append(uv_to_pixel((u, v), {"resolution": [scene.render.resolution_x, scene.render.resolution_y]}))
    return dedupe_points(visible_polygon), dedupe_pixel_points(visible_polygon_pixels)

def visible_defect_from_blender_camera(scene, camera_obj, defect, camera):
    points = defect["centerline"]
    widths = defect["width_profile"]
    depths = defect["depth_profile"]
    left_boundary = defect.get("left_boundary", points)
    right_boundary = defect.get("right_boundary", points)
    samples = {
        "centerline": [],
        "width_profile": [],
        "depth_profile": [],
        "left_boundary": [],
        "right_boundary": [],
        "centerline_pixels": [],
        "left_boundary_pixels": [],
        "right_boundary_pixels": [],
        "source_profile": [],
    }

    components = []
    active = None
    previous_index = None
    previous_end = None
    for index in range(len(points) - 1):
        left = points[index]
        right = points[index + 1]
        left_uv = world_to_camera_view(scene, camera_obj, Vector((float(left[0]), float(left[1]), float(left[2]))))
        right_uv = world_to_camera_view(scene, camera_obj, Vector((float(right[0]), float(right[1]), float(right[2]))))
        interval = clip_unit_square_interval(
            (float(left_uv.x), float(left_uv.y), float(left_uv.z)),
            (float(right_uv.x), float(right_uv.y), float(right_uv.z)),
        )
        if interval is None:
            active = None
            continue
        connected = (active is not None and previous_index == index - 1
                     and previous_end == 1.0 and interval[0] == 0.0)
        if not connected:
            active = {key: [] for key in samples}
            components.append(active)
        previous_index = index
        previous_end = interval[1]
        for uv_fraction in interval:
            clipped_uv = (
                float(left_uv.x) + (float(right_uv.x) - float(left_uv.x)) * uv_fraction,
                float(left_uv.y) + (float(right_uv.y) - float(left_uv.y)) * uv_fraction,
            )
            clipped_world = ray_plane_intersection(camera_obj, clipped_uv[0], clipped_uv[1], 0.0)
            if clipped_world is None:
                continue
            point = [float(clipped_world.x), float(clipped_world.y), float(clipped_world.z)]
            fraction = segment_fraction_for_point(left, right, point)
            left_boundary_point = interpolate_point(left_boundary[index], left_boundary[index + 1], fraction)
            right_boundary_point = interpolate_point(right_boundary[index], right_boundary[index + 1], fraction)
            left_boundary_uv = world_to_camera_view(
                scene,
                camera_obj,
                Vector((float(left_boundary_point[0]), float(left_boundary_point[1]), float(left_boundary_point[2]))),
            )
            right_boundary_uv = world_to_camera_view(
                scene,
                camera_obj,
                Vector((float(right_boundary_point[0]), float(right_boundary_point[1]), float(right_boundary_point[2]))),
            )
            append_visible_sample(
                active,
                point,
                uv_to_pixel(clipped_uv, camera),
                interpolate_scalar(widths[index], widths[index + 1], fraction),
                interpolate_scalar(depths[index], depths[index + 1], fraction),
                left_boundary_point,
                right_boundary_point,
                uv_to_pixel((float(left_boundary_uv.x), float(left_boundary_uv.y)), camera),
                uv_to_pixel((float(right_boundary_uv.x), float(right_boundary_uv.y)), camera),
                index,
                fraction,
            )

    component_ranges = []
    centerline_length = 0.0
    for component in components:
        if not component["centerline"]:
            continue
        start = len(samples["centerline"])
        centerline_length += polyline_length(component["centerline"])
        for key in samples:
            samples[key].extend(component[key])
        component_ranges.append([start, len(samples["centerline"])])
    visible_polygon, visible_polygon_pixels = visible_polygon_from_blender_camera(scene, camera_obj, defect)
    polygon_area = polygon_area_xy(visible_polygon)
    has_stations = bool(samples["centerline"])
    visible = has_stations or polygon_area > 0.0
    mean_width = polygon_area / centerline_length if centerline_length > 1.0e-9 else None
    # A visible polygon without visible centreline stations has area, but no
    # station-based width/depth extrema. Null must not be interpreted as zero.
    max_width = max(samples["width_profile"]) if has_stations else None
    max_depth = max(samples["depth_profile"]) if has_stations else None
    measurands = {
        "centerline_length": round(centerline_length, 6) if visible else 0.0,
        "max_width": (round(max_width, 6) if max_width is not None else None) if visible else 0.0,
        "mean_width": (round(mean_width, 6) if mean_width is not None else None) if visible else 0.0,
        "max_depth": (round(max_depth, 6) if max_depth is not None else None) if visible else 0.0,
        "crack_area": round(polygon_area, 6) if visible else 0.0,
        "point_count": len(samples["centerline"]),
        "visible_polygon_point_count": len(visible_polygon),
    }
    return {
        "schema": {
            "name": "metrodef3d.visible_defect",
            "version": int(VERSIONING["visible_defect_schema_version"]),
        },
        "visible": visible,
        "reference_export_revision": "component-aware-2",
        "component_ranges": component_ranges,
        "measurand_validity": {name: value is not None for name, value in measurands.items()},
        "clip_model": "blender_camera_view",
        "camera_type": camera["type"],
        "clip_fov_mm": camera.get("fov_mm", camera.get("orthographic_scale")),
        "centerline": samples["centerline"],
        "left_boundary": samples["left_boundary"],
        "right_boundary": samples["right_boundary"],
        "visible_polygon": visible_polygon,
        "centerline_pixels": samples["centerline_pixels"],
        "left_boundary_pixels": samples["left_boundary_pixels"],
        "right_boundary_pixels": samples["right_boundary_pixels"],
        "visible_polygon_pixels": visible_polygon_pixels,
        "width_profile": samples["width_profile"],
        "depth_profile": samples["depth_profile"],
        "source_profile": samples["source_profile"],
        "measurands": measurands,
    }

def write_visible_defect(path, scene, camera_obj, defect, camera):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(visible_defect_from_blender_camera(scene, camera_obj, defect, camera), handle, indent=2, sort_keys=True)
        handle.write("\n")

def camera_frame_point(camera_obj, u, v):
    frame = camera_obj.data.view_frame(scene=bpy.context.scene)
    top_right = frame[0]
    bottom_right = frame[1]
    bottom_left = frame[2]
    top_left = frame[3]
    bottom = bottom_left.lerp(bottom_right, u)
    top = top_left.lerp(top_right, u)
    return bottom.lerp(top, v)

def ray_plane_intersection(camera_obj, u, v, plane_z=0.0):
    frame_point = camera_frame_point(camera_obj, u, v)
    world_point = camera_obj.matrix_world @ frame_point
    if camera_obj.data.type == "ORTHO":
        origin = world_point
        direction = camera_obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
    else:
        origin = camera_obj.matrix_world.translation
        direction = (world_point - origin).normalized()
    if abs(direction.z) < 1.0e-9:
        return None
    distance = (plane_z - origin.z) / direction.z
    if distance <= 0.0:
        return None
    return origin + direction * distance

def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def configure_camera(camera, suffix):
    bpy.ops.object.camera_add(location=camera["position"])
    cam = bpy.context.object
    cam.name = "configured_camera_" + suffix
    look_at(cam, camera["target"])
    if "roll_degrees" in camera:
        cam.rotation_euler.rotate_axis("Z", math.radians(float(camera["roll_degrees"])))
    if camera["type"] == "orthographic":
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = float(camera["orthographic_scale"])
    else:
        cam.data.type = "PERSP"
        cam.data.angle = math.radians(float(camera["fov_degrees"]))
    bpy.context.scene.camera = cam
    bpy.context.view_layer.update()
    return cam
