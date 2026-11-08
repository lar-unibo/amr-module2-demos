# Autonomous and Mobile Robotics M · Module 2: interactive demos

Interactive demos for the lectures of Module 2 of [Autonomous and Mobile Robotics M](https://www.unibo.it/en/study/course-units-transferable-skills-moocs/course-unit-catalogue/course-unit/2026/529948) (University of Bologna, second cycle degree in Automation Engineering), one part per lecture. Each demo pairs a short lesson (equations in the notation of the slides, with experiments to try) with a workspace where the camera, the robot, or the controller can be manipulated.

All computations run in Python, **directly in the browser**, with [Pyodide](https://pyodide.org). The site is a set of static files, published with GitHub Pages; no server or installation is needed to use it.

| Lecture | Demo | Slides |
|---|---|---|
| 1 · Sensors overview | 01 Image formation: central projection (extrinsics, depth lost, thin lens) | 13–18 |
| | 02 Pixels, camera matrix and homography | 19–23 |
| | 03 Lens distortion | 27–29 |
| | 04 Stereo: depth from two cameras (disparity, depth layers, back-projection) | 41–44 |
| 2 · Visual servoing | 01 PBVS: position-based visual servoing | 11–19 |
| | 02 Interaction matrix of a point | 25–29 |
| | 03 Why 4 points? (P3P: three points, up to four poses) | 30 |
| | 04 IBVS: control law and its issues (camera retreat, choice of the interaction matrix) | 31–32, 36 |
| | 05 Depth: guess or estimate | 33–34 |
| | 06 PBVS vs IBVS, with calibration errors | 35 |
| | 07 Stability of IBVS | 38–39 |

The demos of a lecture follow the order of its slides.

## Quick start (local)

Requirements: Python 3.9 or newer and a web browser. Nothing has to be installed to *view* the site.

```bash
python serve.py              # builds site/ and opens http://127.0.0.1:8765/
python serve.py --no-browser
```

The local server is a plain static file server, like GitHub Pages, and works offline: the Python runtime (Pyodide) and KaTeX are stored in `web/vendor/`.

To run the tests (they need numpy):

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Publishing on GitHub Pages

1. Create the repository `amr-module2-demos` on GitHub and push this folder (branch `main`).
2. In the repository: **Settings → Pages → Source: GitHub Actions**.
3. Every push to `main` runs `.github/workflows/pages.yml`: the tests, the build of `site/`, and the deployment. The site appears at `https://<user>.github.io/amr-module2-demos/`.

`site/` is a build output and is not committed.

## Links from the slides

Every demo has a stable address, `demo.html?id=<demo>`. Options in the address:

| Option | Effect |
|---|---|
| `&preset=<name>` | open the demo with a start pose or motion preset, e.g. `demo.html?id=interaction&preset=null`, `demo.html?id=ibvs&preset=rot_z_pi` |

The **◧ Hide lesson** button of a demo hides the explanation, so the workspace takes the full width (the choice is remembered in the browser). The **⋯** menu copies the address of the current view, saves the canvases as a PNG figure, and records them as a video. The site opens in the light theme; ◐ switches to the dark one.

## Structure

```
course/                 Python package (numpy only): the computations, in the notation of the slides
    geometry.py         rotations, angle-axis, poses, camera motion (body twists)
    camera.py           central projection, normalized and pixel coordinates
    interaction.py      interaction matrix of point features, null space
    pose.py             homography, pose of a planar target (Gauss-Newton), P3P, Kabsch
    servo.py            PBVS and IBVS controllers, closed-loop simulation
    calibration.py      Zhang's method: homographies, intrinsics, poses, radial distortion, refinement (no demo at the moment)
    handeye.py          hand-eye calibration, A X = X B (Park and Martin), degeneracy checks (no demo at the moment)
    stereo.py           normal stereo, triangulation, depth resolution, back-projection
sessions/               the Python state of each demo page (runs in the browser)
    catalog.py          course, lectures, and demos, in order (edit COURSE and LECTURES here)
    runtime.py          entry points called by the page: start(demo), call(session, action)
    camera_common.py    scene shared by the camera demos of lecture 1
    projection.py, pixels.py, distortion.py, stereo.py
    servo_common.py     scene and start poses shared by the closed-loop demos
    pbvs.py, interaction.py, four_points.py, ibvs.py, depth.py, comparison.py, stability.py
web/                    static sources of the site
    index.html, demo.html, css/, lessons/<demo>.html, js/demos/<demo>.js
    js/lib/             UI toolkit, plots, 3-D and plane views, Python worker (pyworker.js, api.js)
    vendor/             KaTeX (MIT) and Pyodide (MPL-2.0), stored for offline use
tools/build_site.py     web/ + Python sources + catalog.json -> site/
tools/fetch_pyodide.py  download a pinned Pyodide release into web/vendor/pyodide
serve.py                build and serve locally
tests/                  checks against first principles and the claims of the slides; session and site checks
```

How a demo runs: the page starts a web worker (`web/js/lib/pyworker.js`) that loads Pyodide and numpy, copies `course/` and `sessions/` into the browser's file system, and calls `sessions.runtime`. Each user action is a call to an `act_<name>` method of the demo's session, which returns the new state as JSON. The first visit downloads about 16 MB, which the browser then caches. On a laptop, Python is ready about 1.5 s after the page opens, and an update takes 15–40 ms.

## Adding a demo

1. **Computations** in `course/` (reusable, tested in `tests/test_course.py`).
2. **Session** in `sessions/<module>.py`: a `Session` subclass with `state()` and `act_<name>()` methods.
3. **Catalog entry** in `sessions/catalog.py`: id, lecture, number, title, summary, concepts, slides, session.
4. **Page**: `web/js/demos/<id>.js` exports `mount({workspace, session, state, options})`; `web/lessons/<id>.html` holds the lesson.
5. **Tests** in `tests/test_sessions.py`; `tests/test_site.py` checks that the page files exist.

Conventions: the notation and signs of each lecture's slides. Lecture 1: x = f X / Z on the image plane, u = x / rho_w + u0, extrinsics {}^C T_0, distortion D = (k1, k2, k3, p1, p2) on normalized coordinates. Lecture 2: error `e = s - s*`, control law `v_c = -lambda L^+ e`, velocities in the camera frame, linear part first. Camera frame: x right, y down, z along the optical axis. Figures on the site are drawn by the demos, not copied from papers.

## Updating Pyodide

Edit `VERSION` (and `PACKAGES`) in `tools/fetch_pyodide.py`, then run `python tools/fetch_pyodide.py`. The script checks every wheel against the SHA-256 of the release's lock file and prunes the lock file to the packages it keeps. Update the Python version in `.github/workflows/pages.yml` to the one of the release.

## Credits and licences

The code of this repository is released under the MIT licence (`LICENSE`). The interface is adapted from the interactive companion of *A Tutorial on Shape Servoing of Deformable Objects*. Third-party code in `web/vendor/` keeps its own licence: KaTeX (MIT, `web/vendor/katex/LICENSE`) and Pyodide (Mozilla Public License 2.0, `web/vendor/pyodide/LICENSE`).
