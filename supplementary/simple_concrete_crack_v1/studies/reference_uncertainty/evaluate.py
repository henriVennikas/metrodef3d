"""Propagate evaluated uncertainty components for retained image references.

No fitting, inference, image modification, or reference replacement is performed.
Run from any directory with Python, NumPy and SciPy installed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sys
import time

# Avoid nested numerical-library threads when using a small process pool.
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import numpy as np
import scipy
from scipy.special import ndtri
from scipy.stats import qmc

ROOT = Path(__file__).resolve().parent
REPEATS = ROOT.parent / "annotation_repeatability"
EXAMPLE = ROOT.parent / "uncertainty_example"
sys.path.insert(0, str(REPEATS))
from reference_geometry import project, chain, interp, sections  # noqa: E402

KEYS = ["centerline_length", "mean_width", "max_width", "crack_area"]
UNITS = ["mm", "mm", "mm", "mm^2"]
IMAGES = ["IMG_8184", "IMG_8162"]
SEED = 20261117


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def physical_geometry(image, pass_index):
    folder = REPEATS / "inputs" / image
    H = np.asarray(read(folder / "preprocessing.json")["images"][0]["homography"])
    annotation = read(folder / f"annotation_{pass_index}.json")
    line = next(t["points"] for t in annotation["annotations"] if t["kind"] == "centreline")
    polygon = next(t["points"] for t in annotation["annotations"] if t["kind"] == "boundary")
    return project(np.asarray(line), H), project(np.asarray(polygon), H)


def width_vectorized(line, polygon):
    """Same finite stations, tangent window and intersections as sections().

    The calculation is vectorized over all stations and polygon edges. Removing
    duplicate intersections does not change the nearest positive/negative chord
    ends except at numerical coincidences; equality is explicitly checked against
    sections() for all ten input annotations and representative scale probes.
    """
    s = chain(line)
    length = s[-1]
    stations = np.arange(.025, length, .05)
    points = interp(s, line, stations)
    tangents = interp(s, line, np.minimum(length, stations + .5)) - interp(
        s, line, np.maximum(0, stations - .5))
    tangents /= np.linalg.norm(tangents, axis=1)[:, None]
    normals = np.column_stack([-tangents[:, 1], tangents[:, 0]])
    a, b = polygon, np.roll(polygon, -1, axis=0)
    edges = b - a
    vectors = a[None, :, :] - points[:, None, :]
    denominator = normals[:, None, 0] * edges[None, :, 1] - normals[:, None, 1] * edges[None, :, 0]
    nonzero = np.abs(denominator) > 1e-12
    ray = np.divide(
        vectors[:, :, 0] * edges[None, :, 1] - vectors[:, :, 1] * edges[None, :, 0],
        denominator, out=np.full(denominator.shape, np.nan), where=nonzero)
    along_edge = np.divide(
        vectors[:, :, 0] * normals[:, None, 1] - vectors[:, :, 1] * normals[:, None, 0],
        denominator, out=np.full(denominator.shape, np.nan), where=nonzero)
    intersects = nonzero & (along_edge >= 0) & (along_edge < 1)
    positive = np.min(np.where(intersects & (ray >= 0), ray, np.inf), axis=1)
    negative = np.max(np.where(intersects & (ray <= 0), ray, -np.inf), axis=1)
    crosses_horizontal = ((a[None, :, 1] > points[:, None, 1]) != (b[None, :, 1] > points[:, None, 1]))
    crossing_x = ((b[None, :, 0] - a[None, :, 0]) * (points[:, None, 1] - a[None, :, 1]) /
                  (b[None, :, 1] - a[None, :, 1] + 1e-300) + a[None, :, 0])
    inside = np.count_nonzero(crosses_horizontal & (points[:, None, 0] < crossing_x), axis=1) % 2 == 1
    valid = inside & np.isfinite(positive) & np.isfinite(negative)
    if not valid.any():
        raise ValueError("No valid width chord")
    return float(np.max((positive - negative)[valid]))


def values(line, polygon):
    length = float(chain(line)[-1])
    area = float(abs(np.sum(polygon[:, 0] * np.roll(polygon[:, 1], -1) -
                            polygon[:, 1] * np.roll(polygon[:, 0], -1))) / 2)
    return np.array([length, area / length, width_vectorized(line, polygon), area])


def jacobian_smooth(line, polygon):
    """Exact derivatives for L, A/L and A wrt relative physical X/Y scales."""
    delta = np.diff(line, axis=0)
    segment_lengths = np.linalg.norm(delta, axis=1)
    assert np.all(segment_lengths > 0)
    length = segment_lengths.sum()
    area = abs(np.sum(polygon[:, 0] * np.roll(polygon[:, 1], -1) -
                      polygon[:, 1] * np.roll(polygon[:, 0], -1))) / 2
    j_length = np.sum(delta**2 / segment_lengths[:, None], axis=0)
    j_area = np.full(2, area)
    j_mean = (j_area * length - area * j_length) / length**2
    return np.vstack([j_length, j_mean, j_area])


def scanner_model():
    cert = read(EXAMPLE / "inputs/metrosert_values.json")
    scans = read(EXAMPLE / "inputs/scanner/spans.json")
    saved = read(EXAMPLE / "results/reference_budget.json")["scanner"]
    coefficients = []
    for scan in scans:
        pixels = np.array([scan["spans"][name]["observed_px"] for name in cert["span_names"]])
        coefficient = np.zeros((2, 4))
        coefficient[0, :2] = .5 / pixels[:2]
        coefficient[1, 2:] = .5 / pixels[2:]
        if scan["rotation_cw"] % 180:
            coefficient = coefficient[::-1]
        coefficients.append(coefficient)
    coefficients = np.array(coefficients)
    per_scan = coefficients @ np.array(cert["span_mm"])
    mean_new = per_scan.mean(axis=0)
    original = np.array(saved["previous_rounded_mean_mm_per_px"])
    mean_old = (coefficients @ np.array(cert["reference_old_mm"])).mean(axis=0)
    np.testing.assert_allclose(mean_old, original, rtol=0, atol=5e-10)
    standard_span = cert["expanded_uncertainty_mm"] / cert["coverage_factor"]
    assert standard_span == cert["standard_uncertainty_mm"]
    common_shift = coefficients.mean(axis=0) @ np.full(4, standard_span)
    certificate_covariance = np.outer(common_shift, common_shift)
    scanner_covariance = np.cov(per_scan, rowvar=False, ddof=1)
    np.testing.assert_allclose(mean_new, saved["metrosert_mean_mm_per_px"], rtol=1e-12)
    np.testing.assert_allclose(common_shift, saved["certificate_common_shift_mm_per_px"], rtol=1e-12)
    np.testing.assert_allclose(scanner_covariance, saved["per_scan_sample_covariance"], rtol=1e-12)
    return dict(
        original_scanner_scales_mm_per_px=original.tolist(),
        calibrated_scanner_scales_mm_per_px=mean_new.tolist(),
        calibration_report=cert["report"], calibration_span_standard_uncertainty_mm=standard_span,
        certificate_common_shift_mm_per_px=common_shift.tolist(),
        certificate_covariance_mm2_per_px2=certificate_covariance.tolist(),
        scanner_transfer_covariance_mm2_per_px2=scanner_covariance.tolist(),
        relative_certificate_covariance=(certificate_covariance / np.outer(original, original)).tolist(),
        relative_scanner_transfer_covariance=(scanner_covariance / np.outer(original, original)).tolist(),
        nominal_scale_correction_factors=(mean_new / original).tolist(),
        number_of_scans=len(scans),
        scanner_covariance_divided_by_number_of_scans=False,
        source_covariances_reproduced=True)


def propagate_job(job):
    image, mode, seed, power, scanner = job
    line, polygon = physical_geometry(image, 0)
    normals = ndtri(qmc.Sobol(d=3, scramble=True, seed=seed).random_base2(power))
    original = np.array(scanner["original_scanner_scales_mm_per_px"])
    certificate_relative = np.array(scanner["certificate_common_shift_mm_per_px"]) / original
    scanner_relative_chol = np.linalg.cholesky(np.array(scanner["relative_scanner_transfer_covariance"]))
    cert = normals[:, :1] * certificate_relative[None, :]
    scan = normals[:, 1:] @ scanner_relative_chol.T
    perturbation = {"certificate": cert, "scanner_transfer": scan, "joint_scale": cert + scan}[mode]
    factors = 1 + perturbation
    assert np.all(factors > 0)
    out = np.array([values(line * factor, polygon * factor) for factor in factors])
    nominal = values(line, polygon)
    convergence = []
    for p in range(10, power + 1):
        x = out[:2**p]
        covariance = np.cov(x, rowvar=False, ddof=1)
        convergence.append(dict(power=p, draws=len(x), standard_uncertainty=np.sqrt(np.diag(covariance)).tolist(),
                                mean_shift_from_nominal=(x.mean(axis=0) - nominal).tolist(),
                                output_covariance=covariance.tolist()))
    return image, mode, dict(seed=seed,
                            min_relative_axis_perturbation=perturbation.min(axis=0).tolist(),
                            max_relative_axis_perturbation=perturbation.max(axis=0).tolist(),
                            convergence=convergence, **convergence[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--power", type=int, default=12, help="Sobol sample count is 2**power, minimum 10")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.power < 10:
        parser.error("power must be at least 10")
    started = time.monotonic()
    source_inputs = [EXAMPLE / "inputs/metrosert_values.json", EXAMPLE / "inputs/scanner/spans.json",
                     EXAMPLE / "results/reference_budget.json", REPEATS / "results.json", REPEATS / "reference_geometry.py"]
    for image in IMAGES:
        source_inputs.extend(REPEATS / "inputs" / image / name for name in
                             ["preprocessing.json", "reference.json"] + [f"annotation_{i}.json" for i in range(5)])
    hashes = {os.path.relpath(p, ROOT): digest(p) for p in source_inputs}
    scanner = scanner_model()
    repeats = read(REPEATS / "results.json")
    cases, checks = {}, {}
    for image in IMAGES:
        expected = repeats["cases"][image]
        annotation_values, width_errors = [], []
        for i in range(5):
            line, polygon = physical_geometry(image, i)
            measured = values(line, polygon)
            original_width = sections(line, polygon)["max_width_mm"]
            width_errors.append(abs(measured[2] - original_width))
            np.testing.assert_allclose(measured, [expected["annotations"][i]["values"][k] for k in KEYS], rtol=0, atol=1e-9)
            annotation_values.append(measured)
        x = np.array(annotation_values)
        annotation_covariance = np.cov(x, rowvar=False, ddof=1)
        np.testing.assert_allclose(annotation_covariance, expected["five"]["sample_covariance"], rtol=1e-9, atol=1e-12)
        line, polygon = physical_geometry(image, 0)
        nominal = x[0]
        smooth_indices = [0, 1, 3]
        J = jacobian_smooth(line, polygon)
        derivative_checks = []
        for step in [.002, .001, .0005, .0001]:
            columns = []
            for axis in range(2):
                f_minus, f_plus = np.ones(2), np.ones(2)
                f_minus[axis] -= step
                f_plus[axis] += step
                minus, plus = values(line * f_minus, polygon * f_minus), values(line * f_plus, polygon * f_plus)
                columns.append((plus - minus) / (2 * step))
            finite = np.array(columns).T
            np.testing.assert_allclose(finite[smooth_indices], J, rtol=2e-5, atol=2e-6)
            derivative_checks.append(dict(relative_step=step, finite_difference_jacobian=finite.tolist()))
        # Verify the vectorized width routine under anisotropic perturbations too.
        for factor in [np.array([1.0003, .9996]), np.array([.9997, 1.0004])]:
            fast = width_vectorized(line * factor, polygon * factor)
            reference = sections(line * factor, polygon * factor)["max_width_mm"]
            np.testing.assert_allclose(fast, reference, rtol=0, atol=1e-9)
        corrected = values(line * scanner["nominal_scale_correction_factors"], polygon * scanner["nominal_scale_correction_factors"])
        linear = {}
        for mode, C in [("certificate", scanner["relative_certificate_covariance"]),
                        ("scanner_transfer", scanner["relative_scanner_transfer_covariance"]),
                        ("joint_scale", np.array(scanner["relative_certificate_covariance"]) + np.array(scanner["relative_scanner_transfer_covariance"]))]:
            covariance = J @ np.asarray(C) @ J.T
            linear[mode] = dict(quantities=[KEYS[i] for i in smooth_indices],
                                standard_uncertainty=np.sqrt(np.diag(covariance)).tolist(),
                                output_covariance=covariance.tolist())
        cases[image] = dict(retained_reference=nominal.tolist(), annotation_count=5,
                           single_annotation_covariance=annotation_covariance.tolist(),
                           single_annotation_standard_uncertainty=np.sqrt(np.diag(annotation_covariance)).tolist(),
                           annotation_values=x.tolist(), original_reference_retained=True,
                           smooth_reference_jacobian=J.tolist(), linear_propagation_checks=linear,
                           finite_difference_sensitivity=derivative_checks,
                           nominal_scale_correction=dict(applied=False, calibrated_scale_reference=corrected.tolist(),
                               shift=(corrected-nominal).tolist(), shift_over_annotation_standard_uncertainty=((corrected-nominal)/np.sqrt(np.diag(annotation_covariance))).tolist(),
                               treatment="Separate negligible unapplied correction, not added as a random uncertainty component."))
        checks[image] = dict(all_five_reference_vectors_reproduced=True,
                             max_width_vectorization_max_absolute_difference=max(width_errors),
                             perturbed_width_vectorization_verified=True,
                             analytical_smooth_derivatives_verified=True,
                             annotation_covariance_reproduced=True)
    jobs = [(image, mode, SEED + i, args.power, scanner) for i, image in enumerate(IMAGES)
            for mode in ["certificate", "scanner_transfer", "joint_scale"]]
    print(f"Verified input references. Propagating {len(jobs)} modes x {2**args.power} samples with {args.workers} workers.", flush=True)
    with mp.get_context("spawn").Pool(args.workers) as pool:
        for image, mode, result in pool.imap_unordered(propagate_job, jobs):
            cases[image].setdefault("scale_propagation", {})[mode] = result
            print(image, mode, "scale u", np.round(result["standard_uncertainty"], 9), flush=True)
    rows = []
    for image, case in cases.items():
        propagation = case["scale_propagation"]
        scale_covariance = np.array(propagation["joint_scale"]["output_covariance"])
        annotation_covariance = np.array(case["single_annotation_covariance"])
        combined = annotation_covariance + scale_covariance
        assert np.linalg.eigvalsh(combined).min() >= -1e-12
        case["evaluated_reference_covariance"] = combined.tolist()
        case["evaluated_standard_uncertainty"] = np.sqrt(np.diag(combined)).tolist()
        case["combined_convergence"] = []
        for item in propagation["joint_scale"]["convergence"]:
            u = np.sqrt(np.diag(annotation_covariance + np.array(item["output_covariance"])))
            case["combined_convergence"].append(dict(draws=item["draws"], standard_uncertainty=u.tolist(),
                table_precision_formatted=[f"{v:.{d}f}" for v,d in zip(u,[2,3,3,2])]))
        formatted = [c["table_precision_formatted"] for c in case["combined_convergence"]]
        assert all(v == formatted[-1] for v in formatted), (image, "Table precision not converged")
        checks[image]["combined_uncertainty_table_precision_stable"] = True
        checks[image]["linear_mc_relative_standard_uncertainty_differences"] = {}
        for mode in propagation:
            empirical = np.array(propagation[mode]["standard_uncertainty"])[[0,1,3]]
            analytic = np.array(case["linear_propagation_checks"][mode]["standard_uncertainty"])
            difference = empirical/analytic-1
            assert np.max(abs(difference)) < .01, (image, mode, difference)
            checks[image]["linear_mc_relative_standard_uncertainty_differences"][mode] = difference.tolist()
        for i, name in enumerate(KEYS):
            rows.append(dict(image=image, quantity=name, unit=UNITS[i], reference=case["retained_reference"][i],
                u_certificate=propagation["certificate"]["standard_uncertainty"][i],
                u_scanner_transfer=propagation["scanner_transfer"]["standard_uncertainty"][i],
                u_joint_scale=propagation["joint_scale"]["standard_uncertainty"][i],
                u_annotation=case["single_annotation_standard_uncertainty"][i],
                u_evaluated=case["evaluated_standard_uncertainty"][i],
                unapplied_nominal_scale_correction=case["nominal_scale_correction"]["shift"][i]))
    assert all(digest(ROOT / path)==expected for path,expected in hashes.items()), "Input changed during evaluation"
    result = dict(quantities=KEYS, units=UNITS, scanner=scanner, cases=cases,
        propagation=dict(method="Deterministic scrambled Sobol integration of Gaussian scale inputs", seed=SEED,
            draws_per_mode=2**args.power, modes=["certificate", "scanner_transfer", "joint_scale"],
            distribution_assumptions="One common Gaussian certificate error and a correlated bivariate Gaussian scanner-transfer error, mutually independent.",
            covariance_combination="Full single-annotation covariance plus joint nonlinear scale-output covariance; annotation and scale groups assumed independent.",
            nonlinear_note="Maximum width retains physical station spacing 0.05 mm and tangent window 1 mm. Sampling changes make its local finite-difference Jacobian unstable; all components are propagated through the actual estimator.",
            joint_scale_note="Certificate-only and scanner-only max-width variances need not add to the joint nonlinear variance. The joint value is used in the combined budget.",
            convergence_note="Nested Sobol prefixes are convergence diagnostics, not independent replications or confidence limits on numerical integration error."),
        scope=dict(reference_estimator="Retained single annotation", uncertainty="Evaluated standard uncertainty, not a 95% interval or complete uncertainty budget.",
            unquantified=["Common annotation bias", "Local calibration-target coordinate errors beyond measured spans", "Mapping/lens-model inadequacy", "Target-to-surface plane or pose mismatch", "Unmeasured temporal drift and paper dimensional change"],
            no_uncertainty_evaluation_for=["IMG_8169", "IMG_8139"],
            not_evaluated={image: "No repeated-annotation estimate is available; missing components are not treated as zero." for image in ["IMG_8169", "IMG_8139"]},
            known_scale_correction="Retained references are not recentered. The small nominal correction is calculated separately and remains unapplied.",
            annotation_order="No inference of independence or dependence is made from the order of repeated annotation values."),
        runtime_seconds=time.monotonic()-started,
        software=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__))
    write("results.json", result)
    write("input_checksums.json", hashes)
    verification=dict(input_hashes_unchanged=True, scanner_covariances_reproduced=True,
                      retained_references_unchanged=True, no_model_inference=True, no_training=True,
                      checks=checks, script_sha256=digest(Path(__file__)), runtime_seconds=result["runtime_seconds"])
    write("verification.json", verification)
    with (ROOT/"components.csv").open("w", newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    for image, case in cases.items():
        print(image, "evaluated u", case["evaluated_standard_uncertainty"], flush=True)
    print("Complete in", round(result["runtime_seconds"], 1), "seconds", flush=True)


if __name__ == "__main__":
    main()
