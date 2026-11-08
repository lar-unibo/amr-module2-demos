"""
The course and its demos, in lecture order.
===========================================

One part of the site per lecture. A demo names its lecture, its position in
the lecture, the slides it belongs to, and its session class
("module:Class" inside `sessions`); its page files are
`web/lessons/<id>.html` and `web/js/demos/<id>.js`.

`tools/build_site.py` writes this structure to `catalog.json`, so the menu
renders without waiting for Python.
"""
from __future__ import annotations

COURSE = {
    "title": "Autonomous and Mobile Robotics M · Module 2",
    "subtitle": "Interactive demos for the lectures",
    "author": "Alessio Caporali",
    "affiliation": "DEI - LAR, University of Bologna",
    "programme": "Second cycle degree in Automation Engineering, 2026/2027",
    "url": "https://www.unibo.it/en/study/course-units-transferable-skills-moocs/course-unit-catalogue/course-unit/2026/529948",
}

LECTURES = [
    {"id": "sensors", "number": 1, "title": "Sensors overview",
     "summary": "camera model, lens distortion, and stereo"},
    {"id": "visual-servoing", "number": 2, "title": "Visual servoing",
     "summary": "interaction matrix, PBVS and IBVS, depth, stability"},
]

_ENTRIES = [
    # ---- lecture 1: sensors overview (vision part)
    {"id": "projection", "lecture": "sensors", "number": 1,
     "title": "Image formation: central projection",
     "summary": "Project a scene through a pinhole camera, move the camera, and see why the depth is "
                "lost; the thin-lens equation.",
     "concepts": ["$x=fX/Z$", "${}^C\\vT_0$", "depth lost"],
     "slides": "13-18",
     "session": "projection:ProjectionSession"},
    {"id": "pixels", "lecture": "sensors", "number": 2,
     "title": "Pixels, camera matrix and homography",
     "summary": "From the image plane to pixels with the intrinsic matrix K; the 3x4 camera matrix "
                "and the homography of a plane.",
     "concepts": ["$\\vK$", "$\\vC=\\vK[\\vI|\\mathbf 0]\\,{}^C\\vT_0$", "$\\vH$"],
     "slides": "19-23",
     "session": "pixels:PixelsSession"},
    {"id": "distortion", "lecture": "sensors", "number": 3,
     "title": "Lens distortion",
     "summary": "Radial (barrel, pincushion) and tangential distortion of a grid, and its correction.",
     "concepts": ["$k_1,k_2,k_3$", "$p_1,p_2$", "barrel / pincushion"],
     "slides": "27-29",
     "session": "distortion:DistortionSession"},
    {"id": "stereo", "lecture": "sensors", "number": 4,
     "title": "Stereo: depth from two cameras",
     "summary": "Two cameras see a point along two rays: the shift between the images (disparity) "
                "gives its depth, in steps that grow with distance. Then from pixels to 3-D points.",
     "concepts": ["$\\vP_C=Z\\vK^{-1}\\tilde{\\vp}$", "$Z=bf'/d$", "$\\Delta Z\\propto Z^2$"],
     "slides": "41-44",
     "session": "stereo:StereoSession"},
    # ---- lecture 2: visual servoing
    {"id": "pbvs", "lecture": "visual-servoing", "number": 1,
     "title": "PBVS: position-based visual servoing",
     "summary": "Drive the camera to the desired pose using its estimated 3-D pose: a straight line "
                "in 3-D, while the image paths are not controlled.",
     "concepts": ["${}^d\\vT_c\\to\\vI$", "$\\theta\\vm$", "straight line"],
     "slides": "11-19",
     "session": "pbvs:PBVSSession"},
    {"id": "interaction", "lecture": "visual-servoing", "number": 2,
     "title": "Interaction matrix of a point",
     "summary": "Move the camera and compare the image motion of a point with its "
                "first-order prediction from the interaction matrix.",
     "concepts": ["$\\dot{\\vs}=\\vL_p\\vv_c$", "depth $Z$", "null space"],
     "slides": "25-29",
     "session": "interaction:InteractionSession"},
    {"id": "four-points", "lecture": "visual-servoing", "number": 3,
     "title": "Why 4 points?",
     "summary": "With three points, up to four camera poses see the same image: IBVS can stop at a "
                "wrong pose with e = 0. A fourth point removes the ambiguity.",
     "concepts": ["P3P", "4 solutions", "$\\ve=\\mathbf 0$ at a wrong pose"],
     "slides": "30",
     "session": "four_points:FourPointsSession"},
    {"id": "ibvs", "lecture": "visual-servoing", "number": 4,
     "title": "IBVS: control law and its issues",
     "summary": "Servo four image points to their desired positions; compare the choices of the "
                "interaction matrix on rotations about the optical axis (camera retreat).",
     "concepts": ["$\\vv_c=-\\lambda\\Lhp\\ve$", "camera retreat", "$\\vL(\\vs)$, $\\vL(\\vs^{*})$, mean"],
     "slides": "31-32, 36",
     "session": "ibvs:IBVSSession"},
    {"id": "depth", "lecture": "visual-servoing", "number": 5,
     "title": "Depth: guess or estimate",
     "summary": "The interaction matrix needs the depth Z. Use a constant guess or estimate it online "
                "from the camera and image motion; compare with the true depths.",
     "concepts": ["$\\hat Z$", "$\\hat Z/Z$ scaling", "online least squares"],
     "slides": "33-34",
     "session": "depth:DepthSession"},
    {"id": "comparison", "lecture": "visual-servoing", "number": 6,
     "title": "PBVS vs IBVS",
     "summary": "Same start, same camera: PBVS gives a straight 3-D path, IBVS straight image paths. "
                "With a wrong calibration, only IBVS still reaches the goal.",
     "concepts": ["image paths", "calibration errors", "final pose error"],
     "slides": "35",
     "session": "comparison:ComparisonSession"},
    {"id": "stability", "lecture": "visual-servoing", "number": 7,
     "title": "Stability of IBVS",
     "summary": "Follow the 6-D error the controller acts on, check the conditions of the slides, and "
                "make the camera stop with an error it cannot see.",
     "concepts": ["$\\ve'=\\Lhp\\ve$", "$\\Lhp\\vL>0$", "$\\Null(\\Lhp)$"],
     "slides": "38-39",
     "session": "stability:StabilitySession"},
]

DEMOS = {entry["id"]: entry for entry in _ENTRIES}


def catalog() -> dict:
    """The structure of catalog.json: course, lectures, and their demos in order."""
    lectures = []
    for lecture in LECTURES:
        demos = sorted((d for d in _ENTRIES if d["lecture"] == lecture["id"]), key=lambda d: d["number"])
        lectures.append({**lecture, "demos": [{k: v for k, v in d.items() if k != "session"} for d in demos]})
    return {"course": COURSE, "lectures": lectures}
