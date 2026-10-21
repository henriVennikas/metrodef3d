# Fixed Geometry Background Sensitivity Study

Eight defect geometries are evaluated under eight procedural and sixteen photographed concrete backgrounds. Geometry, camera, scalar reference values, model checkpoint, and interval calibration remain fixed within each geometry group.

The study contains 64 procedural and 128 photographed observations (192 total). Row-level predictions and calibrated bounds are provided in `all_predictions.csv`.

## Pooled Results

| Source | Target | N | MARE (%) | Mean range / truth (%) | Max range / truth (%) | Coverage, 95% CI | Mean interval width / truth (%) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| procedural | centerline_length | 64 | 1.21 | 2.48 | 6.99 | 100.0% [94.3, 100.0] | 10.88 |
| procedural | mean_width | 64 | 1.13 | 3.70 | 5.49 | 98.4% [91.7, 99.7] | 10.01 |
| procedural | max_width | 64 | 2.63 | 4.12 | 6.74 | 98.4% [91.7, 99.7] | 13.10 |
| procedural | crack_area | 64 | 1.90 | 4.51 | 6.64 | 100.0% [94.3, 100.0] | 12.75 |
| photographic | centerline_length | 128 | 2.21 | 9.27 | 21.09 | 93.0% [87.2, 96.3] | 10.98 |
| photographic | mean_width | 128 | 1.85 | 6.96 | 11.69 | 94.5% [89.1, 97.3] | 10.00 |
| photographic | max_width | 128 | 3.87 | 10.11 | 20.55 | 93.8% [88.2, 96.8] | 13.01 |
| photographic | crack_area | 128 | 4.10 | 14.50 | 32.28 | 81.2% [73.6, 87.1] | 12.90 |

## Per Photographed Background Results

Each row combines eight geometries and four measurands (32 prediction intervals).

| Background | Across-target MARE (%) | Interval misses | Coverage | Centerline misses | Mean-width misses | Maximum-width misses | Area misses |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 001 | 2.23 | 1/32 | 96.9% | 0 | 0 | 1 | 0 |
| 002 | 2.19 | 1/32 | 96.9% | 0 | 0 | 0 | 1 |
| 003 | 1.87 | 1/32 | 96.9% | 0 | 0 | 1 | 0 |
| 004 | 1.87 | 0/32 | 100.0% | 0 | 0 | 0 | 0 |
| 005 | 2.66 | 1/32 | 96.9% | 0 | 0 | 0 | 1 |
| 006 | 2.97 | 2/32 | 93.8% | 0 | 0 | 0 | 2 |
| 007 | 2.62 | 1/32 | 96.9% | 0 | 0 | 0 | 1 |
| 008 | 1.88 | 0/32 | 100.0% | 0 | 0 | 0 | 0 |
| 009 | 1.92 | 0/32 | 100.0% | 0 | 0 | 0 | 0 |
| 010 | 1.70 | 0/32 | 100.0% | 0 | 0 | 0 | 0 |
| 011 | 2.25 | 0/32 | 100.0% | 0 | 0 | 0 | 0 |
| 012 | 8.44 | 19/32 | 40.6% | 6 | 4 | 2 | 7 |
| 013 | 3.98 | 6/32 | 81.2% | 0 | 0 | 2 | 4 |
| 014 | 3.86 | 5/32 | 84.4% | 1 | 1 | 0 | 3 |
| 015 | 5.65 | 10/32 | 68.8% | 2 | 2 | 1 | 5 |
| 016 | 2.02 | 1/32 | 96.9% | 0 | 0 | 1 | 0 |

## Per Geometry Results

| Source | Seed | Target | Truth | MARE (%) | Range / truth (%) | Coverage | Mean interval width |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| photographic | 10155 | centerline_length | 100.732 | 1.30 | 9.71 | 14/16 | 7.42311 |
| photographic | 10155 | mean_width | 0.897541 | 1.16 | 5.39 | 15/16 | 0.0614823 |
| photographic | 10155 | max_width | 1.14494 | 2.93 | 3.27 | 16/16 | 0.105333 |
| photographic | 10155 | crack_area | 90.4113 | 2.00 | 10.12 | 14/16 | 7.66973 |
| photographic | 10316 | centerline_length | 118.339 | 2.15 | 7.62 | 15/16 | 9.41813 |
| photographic | 10316 | mean_width | 0.575418 | 2.31 | 8.53 | 15/16 | 0.0795034 |
| photographic | 10316 | max_width | 0.63508 | 6.97 | 17.84 | 13/16 | 0.121974 |
| photographic | 10316 | crack_area | 68.0943 | 4.83 | 14.75 | 14/16 | 8.00405 |
| photographic | 10558 | centerline_length | 73.89 | 2.59 | 7.43 | 14/16 | 7.9869 |
| photographic | 10558 | mean_width | 0.924117 | 1.48 | 3.54 | 16/16 | 0.0673612 |
| photographic | 10558 | max_width | 1.06519 | 3.26 | 20.55 | 15/16 | 0.109458 |
| photographic | 10558 | crack_area | 68.283 | 3.97 | 10.46 | 10/16 | 7.37654 |
| photographic | 10660 | centerline_length | 92.5883 | 1.70 | 9.70 | 15/16 | 8.42745 |
| photographic | 10660 | mean_width | 0.53756 | 3.64 | 8.15 | 15/16 | 0.0822031 |
| photographic | 10660 | max_width | 0.590904 | 7.08 | 13.62 | 14/16 | 0.127837 |
| photographic | 10660 | crack_area | 49.7718 | 6.45 | 16.51 | 11/16 | 8.05238 |
| photographic | 10694 | centerline_length | 94.6963 | 1.37 | 7.76 | 15/16 | 7.67164 |
| photographic | 10694 | mean_width | 0.817013 | 1.38 | 7.40 | 15/16 | 0.0598397 |
| photographic | 10694 | max_width | 1.01382 | 2.51 | 8.53 | 16/16 | 0.0979441 |
| photographic | 10694 | crack_area | 77.3681 | 2.63 | 11.37 | 13/16 | 7.28856 |
| photographic | 10701 | centerline_length | 159.018 | 1.16 | 4.86 | 16/16 | 13.6407 |
| photographic | 10701 | mean_width | 0.932355 | 0.72 | 3.33 | 16/16 | 0.0795648 |
| photographic | 10701 | max_width | 1.13098 | 0.95 | 5.25 | 16/16 | 0.13766 |
| photographic | 10701 | crack_area | 148.261 | 1.15 | 7.52 | 16/16 | 16.58 |
| photographic | 10784 | centerline_length | 46.8731 | 6.22 | 21.09 | 14/16 | 13.3838 |
| photographic | 10784 | mean_width | 0.890057 | 2.37 | 11.69 | 15/16 | 0.120867 |
| photographic | 10784 | max_width | 1.2493 | 4.47 | 4.11 | 14/16 | 0.142124 |
| photographic | 10784 | crack_area | 41.7198 | 9.80 | 32.28 | 11/16 | 10.6206 |
| photographic | 10866 | centerline_length | 161.02 | 1.23 | 5.96 | 16/16 | 11.9232 |
| photographic | 10866 | mean_width | 0.940464 | 1.76 | 7.60 | 14/16 | 0.0688692 |
| photographic | 10866 | max_width | 1.11116 | 2.77 | 7.69 | 16/16 | 0.117118 |
| photographic | 10866 | crack_area | 151.433 | 1.93 | 12.98 | 15/16 | 15.0265 |
| procedural | 10155 | centerline_length | 100.732 | 0.53 | 1.74 | 8/8 | 7.34533 |
| procedural | 10155 | mean_width | 0.897541 | 0.53 | 1.07 | 8/8 | 0.0606146 |
| procedural | 10155 | max_width | 1.14494 | 3.25 | 1.62 | 8/8 | 0.103434 |
| procedural | 10155 | crack_area | 90.4113 | 0.53 | 1.97 | 8/8 | 7.57196 |
| procedural | 10316 | centerline_length | 118.339 | 1.12 | 2.45 | 8/8 | 9.53229 |
| procedural | 10316 | mean_width | 0.575418 | 1.94 | 5.13 | 8/8 | 0.0832445 |
| procedural | 10316 | max_width | 0.63508 | 1.52 | 5.83 | 8/8 | 0.132514 |
| procedural | 10316 | crack_area | 68.0943 | 1.71 | 6.39 | 8/8 | 8.10798 |
| procedural | 10558 | centerline_length | 73.89 | 0.43 | 2.01 | 8/8 | 7.8593 |
| procedural | 10558 | mean_width | 0.924117 | 0.12 | 0.52 | 8/8 | 0.0657622 |
| procedural | 10558 | max_width | 1.06519 | 3.23 | 1.18 | 8/8 | 0.101378 |
| procedural | 10558 | crack_area | 68.283 | 0.48 | 1.76 | 8/8 | 7.25262 |
| procedural | 10660 | centerline_length | 92.5883 | 1.41 | 1.37 | 8/8 | 8.3124 |
| procedural | 10660 | mean_width | 0.537559 | 1.51 | 5.49 | 8/8 | 0.0836627 |
| procedural | 10660 | max_width | 0.590904 | 2.48 | 5.41 | 8/8 | 0.1325 |
| procedural | 10660 | crack_area | 49.7717 | 2.88 | 6.64 | 8/8 | 8.00956 |
| procedural | 10694 | centerline_length | 94.6963 | 0.32 | 1.57 | 8/8 | 7.53959 |
| procedural | 10694 | mean_width | 0.817013 | 0.54 | 2.75 | 8/8 | 0.0587714 |
| procedural | 10694 | max_width | 1.01382 | 2.40 | 1.57 | 8/8 | 0.095325 |
| procedural | 10694 | crack_area | 77.368 | 0.42 | 1.65 | 8/8 | 7.15646 |
| procedural | 10701 | centerline_length | 159.018 | 0.93 | 0.94 | 8/8 | 13.567 |
| procedural | 10701 | mean_width | 0.932355 | 1.63 | 5.26 | 7/8 | 0.0777815 |
| procedural | 10701 | max_width | 1.13098 | 2.09 | 5.88 | 8/8 | 0.132967 |
| procedural | 10701 | crack_area | 148.261 | 1.65 | 6.08 | 8/8 | 16.0556 |
| procedural | 10784 | centerline_length | 46.8732 | 4.19 | 6.99 | 8/8 | 13.2243 |
| procedural | 10784 | mean_width | 0.890058 | 1.07 | 4.23 | 8/8 | 0.120222 |
| procedural | 10784 | max_width | 1.2493 | 4.62 | 4.71 | 7/8 | 0.140005 |
| procedural | 10784 | crack_area | 41.7198 | 6.07 | 6.48 | 8/8 | 10.4592 |
| procedural | 10866 | centerline_length | 161.02 | 0.79 | 2.77 | 8/8 | 11.925 |
| procedural | 10866 | mean_width | 0.940464 | 1.69 | 5.14 | 8/8 | 0.0668891 |
| procedural | 10866 | max_width | 1.11116 | 1.41 | 6.74 | 8/8 | 0.117484 |
| procedural | 10866 | crack_area | 151.433 | 1.46 | 5.15 | 8/8 | 14.9329 |

## Files

- `all_predictions.csv`: every central prediction, calibrated lower and upper bound, error, coverage result, and interval width.
- `per_geometry_summary.csv`: background sensitivity summarized separately for each fixed geometry and source type.
- `per_background_summary.csv`: photographed-surface errors and interval misses pooled over all eight geometries.
- `pooled_summary.csv`: pooled error, coverage, interval width, and within-geometry prediction variation.
- `procedural_vs_photographic.csv`: direct comparison of the pooled source summaries.
- `summary.json`: machine-readable study description and summary.
