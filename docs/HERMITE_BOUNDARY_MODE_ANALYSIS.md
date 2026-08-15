# Hermite boundary-mode analysis

This note documents the sliding-window Hermite boundary strategies implemented in `SlidingWindowHermiteInterpolator` and their measured effect on boundary accuracy for the project OEM benchmark.

## Context

The boundary issue is observed when interpolating near the first and last samples in a time series. In this project, the boundary benchmark compares interpolated states against a dense Hermite reference series built from OEM ephemerides.

The benchmark used in practice was:

- source: `tmp/leo3_itrf.4h.oem`
- reference: `tmp/leo3_itrf.4h.10m.hermite.1m.oem`
- query spacing: 60 s
- boundary probes: 8 points on each side

The measured metrics below are the maximum position error and RMS position error near the domain edges.

## Boundary modes

### 1. `centered`

Default behavior. The local window is centered on the query point whenever possible.

Near the first or last sample, the window is clipped to the available data, so the support becomes effectively one-sided.

Observed accuracy on the benchmark:

| degree | max_pos_err_m | rms_pos_err_m | max_vel_err_m_s |
|---|---:|---:|---:|
| 3 | 223681.317205 | 157972.487980 | 226.812950 |
| 5 | 223681.320872 | 157972.488035 | 226.812950 |
| 7 | 223681.345097 | 157972.488535 | 226.812950 |

This is the baseline reference for comparison.

### 2. `widen`

When the query is near a boundary, the algorithm expands the local window to include more available data on the open side of the domain. This aims to reduce the one-sided sensitivity of the fit.

Observed behavior:

- with a small extension (`boundary_window_extension = 2`), the result is effectively the same as `centered`
- with larger extensions, the error grows quickly and becomes much worse

Example at `boundary_window_extension = 8`:

| degree | max_pos_err_m | rms_pos_err_m | max_vel_err_m_s |
|---|---:|---:|---:|
| 3 | 223683.111902 | 157972.495369 | 226.836303 |
| 5 | 223699.391345 | 157972.432901 | 227.497770 |
| 7 | 223887.926029 | 157973.050362 | 237.922043 |

At `boundary_window_extension = 16` and above, the error becomes severe and the strategy is not viable.

### 3. `edge`

This is a more explicit one-sided boundary strategy that anchors the local window to the domain edge when the query is close to the first or last sample.

This strategy behaves similarly to `widen` in the project benchmark:

- small extension values produce almost no change versus `centered`
- larger extensions quickly increase the error and destabilize the fit

Example at `boundary_window_extension = 8`:

| degree | max_pos_err_m | rms_pos_err_m | max_vel_err_m_s |
|---|---:|---:|---:|
| 3 | 223683.111902 | 157972.495369 | 226.836303 |
| 5 | 223699.391345 | 157972.432901 | 227.497770 |
| 7 | 223887.926029 | 157973.050362 | 237.922043 |

This is not a useful boundary remedy for the present OEM data.

### 4. `compact`

This strategy intentionally slightly shrinks the edge window in order to stabilize the local fit and avoid over-expanding the support.

Observed behavior on the benchmark:

| degree | max_pos_err_m | rms_pos_err_m | max_vel_err_m_s |
|---|---:|---:|---:|
| 3 | 223681.312808 | 157972.485464 | 226.812950 |
| 5 | 223681.317205 | 157972.487980 | 226.812950 |
| 7 | 223681.320872 | 157972.488035 | 226.812950 |

This is the best-performing option of the tested heuristics, but the improvement is tiny:

- degree 3 max position error: `223681.317205` to `223681.312808`
- improvement: about `0.0044 m`
- RMS position error improvement: about `0.0025 m`
- velocity error is effectively unchanged

In other words, `compact` is slightly better than the baseline, but only at the level of a few thousandths of a meter on a roughly `223,681 m` boundary error. That is not a practically meaningful improvement.

## Summary of effects

The boundary-window heuristics tested here do not materially solve the underlying boundary accuracy problem for this dataset.

The ranking is roughly:

1. `compact` — marginally best, but essentially negligible
2. `centered` — baseline behavior
3. `widen` / `edge` — sometimes similar at small extension values, but quickly degrade with larger support

The one-sided and widened variants become unstable as soon as the boundary support becomes too aggressive.

## Recommendation

For the project’s current OEM interpolation use case, the boundary heuristics are not worth treating as a real fix. The small gain from `compact` is too small to justify the added complexity and configuration surface.

A truly effective solution would likely require a more structural approach, such as:

- a dedicated one-sided Hermite formulation at the first and last sample range
- degree reduction near the data edge
- using a different interpolant family only near the boundary
- matching the interpolation scheme to the underlying orbit model rather than only changing window geometry

## Practical conclusion

The benchmark evidence indicates that the sliding-window behavior is not the dominant cause of the observed boundary error. The problem is more fundamental to the one-sided local polynomial fit near the edge than to the specific window placement alone.
