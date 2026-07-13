#!/usr/bin/env python3
"""Write a browser overlay viewer for a metrodef3d run directory."""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
import struct
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")
    viewer_dir = run_dir / args.viewer_dir
    viewer_dir.mkdir(parents=True, exist_ok=True)
    (viewer_dir / "pixel_scale").mkdir(parents=True, exist_ok=True)
    samples = build_samples(run_dir, viewer_dir)
    write_json(viewer_dir / "viewer_data.json", {"samples": samples})
    (viewer_dir / "overlay_viewer.html").write_text(HTML, encoding="utf-8")
    print(f"Wrote {viewer_dir / 'overlay_viewer.html'}")
    print(f"Wrote {viewer_dir / 'viewer_data.json'}")
    print(f"Wrote {viewer_dir / 'pixel_scale'}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--viewer-dir", default="overlay_viewer")
    return parser.parse_args()


def build_samples(run_dir: Path, viewer_dir: Path) -> List[Dict[str, Any]]:
    samples = []
    for metadata_path in sorted((run_dir / "json").glob("*.json"), key=lambda path: int(path.stem)):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        for capture in metadata["outputs"]["captures"]:
            pixel_scale_path = Path(capture["pixel_scale_sidecar"])
            if not pixel_scale_path.is_absolute():
                pixel_scale_path = run_dir / pixel_scale_path.relative_to(run_dir) if str(pixel_scale_path).startswith(str(run_dir)) else pixel_scale_path
            if not pixel_scale_path.exists():
                pixel_scale_path = run_dir / capture["pixel_scale_sidecar"]
            descriptor = write_pixel_scale_binary(
                pixel_scale_path,
                viewer_dir / "pixel_scale" / f"{metadata['run']['seed']}_{capture['capture_id']}.f32",
            )
            samples.append(
                {
                    "seed": metadata["run"]["seed"],
                    "capture_id": capture["capture_id"],
                    "image": relpath(run_dir, Path(capture["image"])),
                    "metadata": relpath(run_dir, metadata_path),
                    "visible_defect_sidecar": relpath(run_dir, Path(capture["visible_defect_sidecar"])),
                    "pixel_scale_sidecar": relpath(run_dir, Path(capture["pixel_scale_sidecar"])),
                    "pixel_scale_binary": relpath(run_dir, descriptor["path"]),
                    "pixel_scale": descriptor["pixel_scale"],
                    "camera": capture["camera"],
                    "visible_defect": capture["visible_defect"],
                    "measurands": capture["visible_defect"]["measurands"],
                }
            )
    return samples


def relpath(root: Path, path: Path) -> str:
    if not path.is_absolute():
        candidate = path
        if not candidate.exists():
            candidate = root / path
    else:
        candidate = path
    try:
        return str(candidate.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(candidate)


def write_pixel_scale_binary(npz_path: Path, out_path: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(npz_path) as archive:
        scale_x = read_npy_float32(archive.read("scale_x_mm_per_px.npy"))
        scale_y = read_npy_float32(archive.read("scale_y_mm_per_px.npy"))
    if scale_x["shape"] != scale_y["shape"]:
        raise ValueError(f"Pixel-scale shape mismatch: {npz_path}")
    values_x = scale_x["values"]
    values_y = scale_y["values"]
    interleaved = bytearray(len(values_x) * 8)
    offset = 0
    for x_value, y_value in zip(values_x, values_y):
        struct.pack_into("<ff", interleaved, offset, x_value, y_value)
        offset += 8
    out_path.write_bytes(interleaved)
    return {
        "path": out_path,
        "pixel_scale": {
            "width": int(scale_x["shape"][1]),
            "height": int(scale_x["shape"][0]),
            "dtype": "float32_interleaved_xy",
            "scale_x_mm_per_px": numeric_summary(values_x),
            "scale_y_mm_per_px": numeric_summary(values_y),
        },
    }


def read_npy_float32(data: bytes) -> Dict[str, Any]:
    if not data.startswith(b"\x93NUMPY"):
        raise ValueError("Not an NPY file")
    major = data[6]
    if major == 1:
        header_len = struct.unpack_from("<H", data, 8)[0]
        header_start = 10
    elif major == 2:
        header_len = struct.unpack_from("<I", data, 8)[0]
        header_start = 12
    else:
        raise ValueError(f"Unsupported NPY version: {major}")
    header = data[header_start : header_start + header_len].decode("latin1").strip()
    info = ast.literal_eval(header)
    if info.get("descr") not in ("<f4", "|f4"):
        raise ValueError(f"Unsupported NPY dtype: {info.get('descr')}")
    if info.get("fortran_order"):
        raise ValueError("Fortran-order NPY arrays are not supported")
    shape = tuple(int(value) for value in info["shape"])
    count = math.prod(shape)
    payload_start = header_start + header_len
    values = struct.unpack_from("<" + "f" * count, data, payload_start)
    return {"shape": shape, "values": values}


def numeric_summary(values: Sequence[float]) -> Dict[str, float]:
    ordered = sorted(float(value) for value in values)
    return {
        "min": round(ordered[0], 9),
        "max": round(ordered[-1], 9),
        "mean": round(sum(ordered) / len(ordered), 9),
    }


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>metrodef3d Overlay Viewer</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111316;
      --panel: #1b1f24;
      --line: #303843;
      --text: #e9edf2;
      --muted: #9aa6b2;
      --accent: #58c4ff;
      --green: #77e38f;
      --red: #ff6c6c;
      --yellow: #ffd166;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      display: grid;
      grid-template-columns: 320px 1fr;
      height: 100vh;
      overflow: hidden;
    }
    aside {
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 14px;
      overflow: auto;
    }
    main {
      display: grid;
      grid-template-rows: auto 1fr auto;
      min-width: 0;
      min-height: 0;
    }
    .topbar, .status {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
      padding: 10px 14px;
      border-bottom: 1px solid var(--line);
      background: #15191e;
    }
    .status {
      border-top: 1px solid var(--line);
      border-bottom: 0;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }
    h1 {
      font-size: 18px;
      margin: 0 0 12px;
    }
    .sample-list {
      display: grid;
      gap: 6px;
    }
    button, select {
      background: #252b33;
      border: 1px solid #3a4450;
      color: var(--text);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
    }
    button {
      cursor: pointer;
      text-align: left;
    }
    button.active {
      border-color: var(--accent);
      background: #173143;
    }
    label {
      display: inline-flex;
      gap: 6px;
      align-items: center;
      color: var(--muted);
      font-size: 14px;
    }
    input[type="range"] { width: 120px; }
    .viewer {
      min-width: 0;
      min-height: 0;
      display: grid;
      place-items: center;
      overflow: auto;
      background: #0b0d10;
      padding: 12px;
    }
    .stage {
      position: relative;
      width: min(1024px, calc(100vw - 360px));
      aspect-ratio: 1 / 1;
      background: #000;
      box-shadow: 0 0 0 1px #2c333c;
    }
    canvas {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      image-rendering: auto;
    }
    .metrics {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin: 12px 0;
      font-size: 13px;
      color: var(--muted);
    }
    .metric {
      background: #12161b;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
    }
    .metric strong {
      display: block;
      color: var(--text);
      font-size: 15px;
      margin-top: 2px;
    }
    .legend {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .swatch {
      width: 90px;
      height: 12px;
      border-radius: 3px;
      background: linear-gradient(90deg, #2b59ff, #1ee3a6, #ffe75f, #ff3b3b);
      border: 1px solid #4a5360;
    }
    @media (max-width: 900px) {
      body { grid-template-columns: 1fr; grid-template-rows: 260px 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .stage { width: min(1024px, calc(100vw - 24px)); }
    }
  </style>
</head>
<body>
  <aside>
    <h1>metrodef3d overlay</h1>
    <div class="metrics" id="metrics"></div>
    <div class="sample-list" id="samples"></div>
  </aside>
  <main>
    <div class="topbar">
      <label><input type="checkbox" id="showCenter" checked> centerline</label>
      <label><input type="checkbox" id="showBoundary" checked> boundary</label>
      <label><input type="checkbox" id="showPolygon"> fill polygon</label>
      <label><input type="radio" name="scaleMode" value="none" checked> no scale</label>
      <label><input type="radio" name="scaleMode" value="x"> horizontal scale</label>
      <label><input type="radio" name="scaleMode" value="y"> vertical scale</label>
      <label>alpha <input id="scaleAlpha" type="range" min="0" max="100" value="55"></label>
      <span class="legend"><span class="swatch"></span><span id="legendText"></span></span>
    </div>
    <div class="viewer">
      <div class="stage" id="stage">
        <canvas id="imageCanvas" width="1024" height="1024"></canvas>
        <canvas id="scaleCanvas" width="1024" height="1024"></canvas>
        <canvas id="overlayCanvas" width="1024" height="1024"></canvas>
      </div>
    </div>
    <div class="status" id="status">loading</div>
  </main>
  <script>
    const rootPrefix = "../";
    const imageCanvas = document.getElementById("imageCanvas");
    const scaleCanvas = document.getElementById("scaleCanvas");
    const overlayCanvas = document.getElementById("overlayCanvas");
    const imageCtx = imageCanvas.getContext("2d");
    const scaleCtx = scaleCanvas.getContext("2d");
    const overlayCtx = overlayCanvas.getContext("2d");
    const controls = ["showCenter", "showBoundary", "showPolygon", "scaleAlpha"].map(id => document.getElementById(id));
    const state = { samples: [], sample: null, image: null, scaleValues: null };

    function dot(a, b) { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }
    function cross(a, b) { return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]; }
    function norm(a) { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0]/l, a[1]/l, a[2]/l]; }
    function sub(a, b) { return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]; }

    function cameraBasis(camera) {
      const position = camera.position.map(Number);
      const target = camera.target.map(Number);
      const forward = norm(sub(target, position));
      let worldUp = [0, 1, 0];
      if (Math.abs(dot(forward, worldUp)) > 0.98) worldUp = [1, 0, 0];
      let right = norm(cross(forward, worldUp));
      let up = norm(cross(right, forward));
      const roll = (camera.roll_degrees || 0) * Math.PI / 180;
      if (roll) {
        const c = Math.cos(roll), s = Math.sin(roll);
        const rolledRight = [right[0]*c + up[0]*s, right[1]*c + up[1]*s, right[2]*c + up[2]*s];
        const rolledUp = [up[0]*c - right[0]*s, up[1]*c - right[1]*s, up[2]*c - right[2]*s];
        right = rolledRight; up = rolledUp;
      }
      return { position, forward, right, up };
    }

    function worldToPixel(point, sample) {
      const camera = sample.camera;
      const basis = cameraBasis(camera);
      const delta = sub(point, basis.position);
      const x = dot(delta, basis.right);
      const y = dot(delta, basis.up);
      const z = dot(delta, basis.forward);
      const width = camera.resolution[0], height = camera.resolution[1];
      if (z <= 0) return null;
      if (camera.type === "orthographic") {
        const vertical = camera.orthographic_scale;
        const horizontal = vertical * width / height;
        return [(x / horizontal + 0.5) * width, (0.5 - y / vertical) * height];
      }
      const tanV = Math.tan((camera.fov_degrees * Math.PI / 180) / 2);
      const tanH = tanV * width / height;
      return [(x / (z * tanH) * 0.5 + 0.5) * width, (0.5 - y / (z * tanV) * 0.5) * height];
    }

    function pointToCanvas(point, sample) {
      if (!point) return null;
      if (point.length === 2) return point;
      return worldToPixel(point, sample);
    }

    function drawPolyline(ctx, points, sample, color, width, close=false) {
      if (!points || points.length < 2) return;
      ctx.beginPath();
      let started = false;
      for (const point of points) {
        const px = pointToCanvas(point, sample);
        if (!px) continue;
        if (!started) { ctx.moveTo(px[0], px[1]); started = true; }
        else ctx.lineTo(px[0], px[1]);
      }
      if (close) ctx.closePath();
      ctx.lineWidth = width;
      ctx.strokeStyle = color;
      ctx.stroke();
    }

    function drawOverlay() {
      const sample = state.sample;
      overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
      if (!sample) return;
      const vd = sample.visible_defect;
      const polygon = vd.visible_polygon_pixels || vd.visible_polygon;
      const leftBoundary = vd.left_boundary_pixels || vd.left_boundary;
      const rightBoundary = vd.right_boundary_pixels || vd.right_boundary;
      const centerline = vd.centerline_pixels || vd.centerline;
      if (document.getElementById("showPolygon").checked && polygon && polygon.length > 2) {
        overlayCtx.beginPath();
        polygon.forEach((point, index) => {
          const px = pointToCanvas(point, sample);
          if (!px) return;
          if (index === 0) overlayCtx.moveTo(px[0], px[1]);
          else overlayCtx.lineTo(px[0], px[1]);
        });
        overlayCtx.closePath();
        overlayCtx.fillStyle = "rgba(255, 209, 102, 0.24)";
        overlayCtx.fill();
      }
      if (document.getElementById("showBoundary").checked) {
        drawPolyline(overlayCtx, leftBoundary, sample, "rgba(119, 227, 143, 0.95)", 2);
        drawPolyline(overlayCtx, rightBoundary, sample, "rgba(255, 108, 108, 0.95)", 2);
      }
      if (document.getElementById("showCenter").checked) {
        drawPolyline(overlayCtx, centerline, sample, "rgba(88, 196, 255, 0.98)", 2.5);
      }
    }

    function scaleMode() {
      return document.querySelector("input[name='scaleMode']:checked").value;
    }

    function colorRamp(t, alpha) {
      t = Math.max(0, Math.min(1, t));
      const stops = [
        [43, 89, 255],
        [30, 227, 166],
        [255, 231, 95],
        [255, 59, 59],
      ];
      const scaled = t * (stops.length - 1);
      const index = Math.min(stops.length - 2, Math.floor(scaled));
      const f = scaled - index;
      const a = stops[index], b = stops[index + 1];
      return [
        Math.round(a[0] + (b[0] - a[0]) * f),
        Math.round(a[1] + (b[1] - a[1]) * f),
        Math.round(a[2] + (b[2] - a[2]) * f),
        alpha,
      ];
    }

    function drawScale() {
      scaleCtx.clearRect(0, 0, scaleCanvas.width, scaleCanvas.height);
      const sample = state.sample;
      if (!sample || !state.scaleValues || scaleMode() === "none") {
        document.getElementById("legendText").textContent = "";
        return;
      }
      const mode = scaleMode();
      const summary = mode === "x" ? sample.pixel_scale.scale_x_mm_per_px : sample.pixel_scale.scale_y_mm_per_px;
      const width = sample.pixel_scale.width, height = sample.pixel_scale.height;
      const imageData = scaleCtx.createImageData(width, height);
      const alpha = Math.round(Number(document.getElementById("scaleAlpha").value) * 2.55);
      const min = summary.min, max = summary.max, span = Math.max(1e-12, max - min);
      for (let i = 0; i < width * height; i++) {
        const value = state.scaleValues[i * 2 + (mode === "x" ? 0 : 1)];
        const color = colorRamp((value - min) / span, alpha);
        const j = i * 4;
        imageData.data[j] = color[0];
        imageData.data[j + 1] = color[1];
        imageData.data[j + 2] = color[2];
        imageData.data[j + 3] = color[3];
      }
      scaleCtx.putImageData(imageData, 0, 0);
      document.getElementById("legendText").textContent = `${mode === "x" ? "h" : "v"} ${min.toFixed(6)}..${max.toFixed(6)} mm/px`;
    }

    async function loadScale(sample) {
      const response = await fetch(rootPrefix + sample.pixel_scale_binary);
      const buffer = await response.arrayBuffer();
      return new Float32Array(buffer);
    }

    async function loadSample(index) {
      state.sample = state.samples[index];
      state.scaleValues = null;
      document.querySelectorAll(".sample-list button").forEach((button, i) => button.classList.toggle("active", i === index));
      const image = new Image();
      image.src = rootPrefix + state.sample.image;
      await image.decode();
      imageCtx.clearRect(0, 0, imageCanvas.width, imageCanvas.height);
      imageCtx.drawImage(image, 0, 0, imageCanvas.width, imageCanvas.height);
      state.image = image;
      state.scaleValues = await loadScale(state.sample);
      updateMetrics();
      drawScale();
      drawOverlay();
      updateStatus();
    }

    function updateMetrics() {
      const sample = state.sample;
      const m = sample.measurands;
      document.getElementById("metrics").innerHTML = [
        ["seed", sample.seed],
        ["visible", sample.visible_defect.visible],
        ["length", Number(m.centerline_length).toFixed(3)],
        ["mean width", Number(m.mean_width).toFixed(4)],
        ["max width", Number(m.max_width).toFixed(4)],
        ["area", Number(m.crack_area).toFixed(3)],
      ].map(([k, v]) => `<div class="metric">${k}<strong>${v}</strong></div>`).join("");
    }

    function pixelFromEvent(event) {
      const rect = overlayCanvas.getBoundingClientRect();
      const x = Math.max(0, Math.min(overlayCanvas.width - 1, Math.floor((event.clientX - rect.left) * overlayCanvas.width / rect.width)));
      const y = Math.max(0, Math.min(overlayCanvas.height - 1, Math.floor((event.clientY - rect.top) * overlayCanvas.height / rect.height)));
      return { x, y };
    }

    function updateStatus(event) {
      if (!state.sample) return;
      let text = `seed ${state.sample.seed} / ${state.sample.capture_id}`;
      if (event && state.scaleValues) {
        const { x, y } = pixelFromEvent(event);
        const width = state.sample.pixel_scale.width;
        const offset = (y * width + x) * 2;
        text += ` | px (${x}, ${y}) | h ${state.scaleValues[offset].toFixed(6)} mm/px | v ${state.scaleValues[offset + 1].toFixed(6)} mm/px`;
      }
      document.getElementById("status").textContent = text;
    }

    function buildSampleList() {
      const list = document.getElementById("samples");
      list.innerHTML = "";
      state.samples.forEach((sample, index) => {
        const button = document.createElement("button");
        const visible = sample.visible_defect.visible ? "visible" : "not visible";
        button.textContent = `${sample.seed} · ${sample.capture_id} · ${visible}`;
        button.addEventListener("click", () => loadSample(index));
        list.appendChild(button);
      });
    }

    async function init() {
      if (window.location.protocol === "file:") {
        throw new Error("This viewer must be opened through a local HTTP server so the browser can load JSON and pixel-scale binary files. Use http://127.0.0.1:8765/overlay_viewer/overlay_viewer.html for the current run, or run python3 -m http.server 8765 --directory <run_dir>.");
      }
      const data = await fetch("viewer_data.json").then(response => response.json());
      state.samples = data.samples;
      buildSampleList();
      controls.forEach(control => control.addEventListener("input", () => { drawScale(); drawOverlay(); }));
      document.querySelectorAll("input[name='scaleMode']").forEach(control => control.addEventListener("input", drawScale));
      overlayCanvas.addEventListener("mousemove", updateStatus);
      overlayCanvas.addEventListener("mouseleave", () => updateStatus());
      if (state.samples.length) await loadSample(0);
    }
    init().catch(error => {
      document.getElementById("status").textContent = error.stack || String(error);
      console.error(error);
    });
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
