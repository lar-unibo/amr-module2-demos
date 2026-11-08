// Lecture 1, demo 2 - Discrete camera model: pixels, K, the camera matrix C and the homography H.
import { matrixTex, setTex } from '../lib/cams.js';
import { alpha, palette } from '../lib/theme.js';
import { card, h, readouts, slider } from '../lib/ui.js';
import { planeCard, view3dCard } from '../lib/widgets.js';

export async function mount({ workspace, session, state }) {
    let S = state;

    const scene = view3dCard('Camera {C} and the scene (world frame {0})', { up: 'z', center: [0.3, 0.2, 0.3], extent: 2.3, yaw: -0.9, pitch: 0.45 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [{ label: 'projection ray of the selected point', color: p.red, kind: 'dashed' }],
    });
    const image = planeCard('Image in pixels', { rect: { x0: -20, x1: 660, y0: -20, y1: 500 } }, {
        note: 'origin at the top-left corner, v down',
        legendItems: (p) => [
            { label: 'principal point $(u_0,v_0)$', color: p.red, kind: 'dot' },
            { label: 'table grid, mapped by $\\vH$', color: p.accent, kind: 'line' },
        ],
    });
    const send = session.stream('set', (next) => { S = next; load(); });
    const sl = (key, text, min, max, step, format) => slider({ label: text, min, max, step, value: S[key], format, onInput: (v) => send({ [key]: v }) });
    const f = sl('f_mm', 'focal length $f$', 2, 12, 0.1, (v) => `${v.toFixed(1)} mm`);
    const rw = sl('rho_w_um', 'pixel width $\\rho_w$', 2, 10, 0.1, (v) => `${v.toFixed(1)} µm`);
    const rh = sl('rho_h_um', 'pixel height $\\rho_h$', 2, 10, 0.1, (v) => `${v.toFixed(1)} µm`);
    const u0 = sl('u0', 'principal point $u_0$', 200, 440, 1, (v) => `${v.toFixed(0)} px`);
    const v0 = sl('v0', 'principal point $v_0$', 140, 340, 1, (v) => `${v.toFixed(0)} px`);
    const az = sl('azimuth', 'camera azimuth', -180, 180, 1, (v) => `${v.toFixed(0)}°`);
    const el = sl('elevation', 'camera elevation', 10, 80, 1, (v) => `${v.toFixed(0)}°`);
    const dist = sl('distance', 'camera distance', 0.5, 2, 0.01, (v) => `${v.toFixed(2)} m`);
    const sel = sl('selected', 'selected point', 0, 9, 1, (v) => `#${v + 1}`);
    const controls = card('Camera parameters', 'intrinsics $\\vK$ and pose ${}^C\\vT_0$ (extrinsics)');
    controls.body.append(h('p', { class: 'slider-group-title' }, 'intrinsic parameters'), h('div', { class: 'slider-group' }, f.el, rw.el, rh.el, u0.el, v0.el),
        h('p', { class: 'slider-group-title' }, 'camera pose (extrinsic parameters)'), h('div', { class: 'slider-group' }, az.el, el.el, dist.el),
        h('p', { class: 'slider-group-title' }, 'selected point'), h('div', { class: 'slider-group' }, sel.el));
    const kTex = h('div', { class: 'matrix-tex' });
    const pixTex = h('div', { class: 'matrix-tex' });
    const info = readouts([{ key: 'sensor', label: 'sensor size $W\\rho_w\\times H\\rho_h$' }, { key: 'fov', label: 'field of view' }]);
    const intrinsics = card('From the image plane to pixels', '$u=x/\\rho_w+u_0,\\ v=y/\\rho_h+v_0$');
    intrinsics.body.append(kTex, pixTex, info.el);
    const tTex = h('div', { class: 'matrix-tex' });
    const cTex = h('div', { class: 'matrix-tex' });
    const hTex = h('div', { class: 'matrix-tex' });
    const check = readouts([{ key: 'scale', label: 'defined up to scale' }, { key: 'check', label: '$\\vC$ reproduces the pixels to' }]);
    const matrices = card('Camera pose, camera matrix and homography', '$\\vC=\\vK[\\vI|\\mathbf 0]\\,{}^C\\vT_0$, shown with $c_{34}=1$, $h_{33}=1$');
    matrices.body.append(tTex, cTex, hTex, check.el);

    workspace.append(h('section', { class: 'views' }, scene.el, image.el),
        h('section', { class: 'plots' }, controls.el, intrinsics.el), matrices.el);
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;

    function drawScene() {
        scene.view.draw((g) => {
            const p = g.p;
            g.table({ extent: S.table_half, step: S.table_half / 3 });
            g.frame([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], { size: 0.15, label: '{0}' });
            for (const [a, b] of S.edges) g.line(S.world[a], S.world[b], { color: p.ink, width: 1.8 });
            g.point(S.world[S.selected], { r: 5, color: p.red, ring: null });
            g.camera(S.T_0c, { color: p.inkSoft, size: 0.12, axes: true, width: 1.6 });
            const c = [S.T_0c[0][3], S.T_0c[1][3], S.T_0c[2][3]];
            g.label(c, '{C}', { dx: -18, dy: -8 });
            g.line(c, S.world[S.selected], { color: alpha(p.red, 0.7), width: 1.2, dash: [5, 4] });
        });
    }
    function drawImage() {
        image.view.draw((g) => {
            const p = g.p;
            g.frame({ step: 40, axes: false });
            g.polyline([[0, 0], [S.W, 0], [S.W, S.H], [0, S.H], [0, 0]], { color: p.lineStrong, width: 1.8 });
            for (const L of S.table_lines) g.polyline(L, { color: alpha(p.accent, 0.6), width: 1.2 });
            for (const [a, b] of S.edges) g.line(S.uv[a], S.uv[b], { color: p.ink, width: 1.8 });
            g.point(S.uv[S.selected], { r: 5, color: p.red, ring: p.surface });
            g.line([S.W / 2 - 8, S.H / 2], [S.W / 2 + 8, S.H / 2], { color: p.muted, width: 1 });
            g.line([S.W / 2, S.H / 2 - 8], [S.W / 2, S.H / 2 + 8], { color: p.muted, width: 1 });
            g.point([S.u0, S.v0], { r: 4, color: p.red, ring: null });
            g.text([0, 0], '(0, 0)', { dx: 4, dy: -6, size: 10 });
        });
    }

    function load() {
        f.set(S.f_mm); rw.set(S.rho_w_um); rh.set(S.rho_h_um); u0.set(S.u0); v0.set(S.v0); az.set(S.azimuth); el.set(S.elevation); dist.set(S.distance); sel.set(S.selected);
        setTex(kTex, `\\begin{gathered}${matrixTex('\\vK', S.K, 1)}\\\\[2pt] f/\\rho_w=${S.K[0][0].toFixed(0)}\\text{ px},\\quad f/\\rho_h=${S.K[1][1].toFixed(0)}\\text{ px}\\end{gathered}`);
        const q = S.image_mm[S.selected], uv = S.uv[S.selected];
        setTex(pixTex, `\\begin{gathered}\\text{point }\\#${S.selected + 1}:\\ (x,y)=(${q[0].toFixed(3)},\\,${q[1].toFixed(3)})\\text{ mm}\\\\ \\rightarrow\\ (u,v)=(${uv[0].toFixed(1)},\\,${uv[1].toFixed(1)})\\text{ px}\\end{gathered}`);
        info.set('sensor', `${S.sensor_mm[0].toFixed(2)} × ${S.sensor_mm[1].toFixed(2)} mm`);
        info.set('fov', `${S.fov_deg[0].toFixed(0)}° × ${S.fov_deg[1].toFixed(0)}°`);
        setTex(tTex, matrixTex('{}^C\\vT_0', S.T_c0, 3) + '\\quad\\text{(camera pose: rotation and translation, m)}');
        setTex(cTex, matrixTex('\\vC', S.C, 2));
        setTex(hTex, matrixTex('\\vH', S.Hm, 2) + '\\quad\\text{(table points, } Z=0)');
        check.set('scale', '11 unknowns in C, 8 in H');
        check.set('check', `${S.C_check.toExponential(0)} px`);
        drawScene(); drawImage();
    }
    load();
}
