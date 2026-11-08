// Lecture 2, demo 2 - Interaction matrix of a point: s_dot = L_p v_c.
import { tex } from '../lib/math.js';
import { palette } from '../lib/theme.js';
import { card, h, label, readouts, segmented, slider, fmt } from '../lib/ui.js';
import { planeCard, view3dCard } from '../lib/widgets.js';

const PRESETS = [
    { value: 'lateral', label: 'sideways $\\nu_x$' },
    { value: 'forward', label: 'forward $\\nu_z$' },
    { value: 'pan', label: 'pan $\\omega_y$' },
    { value: 'roll', label: 'roll $\\omega_z$' },
    { value: 'ray', label: 'along the ray' },
    { value: 'roll_ray', label: 'about the ray' },
    { value: 'null', label: 'random in $\\Null(\\vL_p)$' },
    { value: 'zero', label: 'stop' },
];
const V_TEX = ['\\nu_x', '\\nu_y', '\\nu_z', '\\omega_x', '\\omega_y', '\\omega_z'];
const IMAGE = { x0: -0.65, x1: 0.65, y0: -0.5, y1: 0.5 };
const FRUSTUM = 0.35;                    // depth at which the image plane is drawn in 3-D

export async function mount({ workspace, session, state, options = {} }) {
    let S = state;
    const colors = (p) => ({ trans: p.gripR, rot: p.gripL, lin: p.aqua, path: p.ink, point: p.feature });

    // ---------------------------------------------------------------- 3-D view
    const scene = view3dCard('Camera and point', { center: [0, 0, 0.8], extent: 2.5 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'camera at $t=0$', color: p.ink, kind: 'line' },
            { label: 'camera at $t=T$', color: p.muted, kind: 'dashed' },
            { label: '$\\nu_c$', color: colors(p).trans, kind: 'line' },
            { label: 'axis of $\\omega_c$', color: colors(p).rot, kind: 'line' },
            { label: 'point $\\vP$', color: colors(p).point, kind: 'dot' },
        ],
    });
    const viewButtons = segmented({
        options: [{ value: 'side', label: 'Side' }, { value: 'top', label: 'Top' }, { value: 'behind', label: 'Behind camera' }],
        value: 'side',
        onChange: (v) => scene.view.setView({ side: { yaw: -0.75, pitch: 0.32 }, top: { yaw: -0.02, pitch: 1.3 }, behind: { yaw: 0, pitch: 0.12 } }[v]),
    });
    scene.toolbar.append(viewButtons.el);

    // ---------------------------------------------------------------- image plane
    const image = planeCard('Image plane (normalized coordinates)', { rect: IMAGE }, {
        note: 'drag the point',
        guide: 'The arrows add up to the first-order prediction $\\vs+\\vL_p\\vv_c\\,T$; the solid curve is the exact image path over the duration $T$.',
        legendItems: (p) => [
            { label: 'exact path', color: colors(p).path, kind: 'line' },
            { label: 'prediction $\\vs+\\dot{\\vs}\\,t$', color: colors(p).lin, kind: 'dashed' },
            { label: 'translation part', color: colors(p).trans, kind: 'line' },
            { label: 'rotation part', color: colors(p).rot, kind: 'line' },
        ],
    });
    const imageReadouts = readouts([
        { key: 'speed', label: '$\\norm{\\dot{\\vs}}$' },
        { key: 'gap', label: 'prediction error at $T$' },
        { key: 'depth', label: 'depth at $T$' },
    ]);
    image.body.append(imageReadouts.el);

    // ---------------------------------------------------------------- controls
    const sendSet = session.stream('set', (next) => { S = next; update(); });
    const presets = segmented({
        options: PRESETS, value: S.preset,
        onChange: async (name) => { S = await session.call('preset', { name }); update(); },
    });
    const vSliders = V_TEX.map((name, j) => slider({
        label: `$${name}$`, min: -S.v_max, max: S.v_max, step: 0.01, value: S.v[j],
        format: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)} ${j < 3 ? 'm/s' : 'rad/s'}`,
        onInput: () => { presets.set(null); sendSet({ v: vSliders.map((s) => s.get()) }); },
    }));
    const depth = slider({ label: 'depth of the point $Z$', min: S.limits.Z[0], max: S.limits.Z[1], step: 0.01, value: S.Z,
        format: (v) => `${v.toFixed(2)} m`, onInput: (Z) => sendSet({ Z }) });
    const horizon = slider({ label: 'duration $T$', min: S.limits.horizon[0], max: S.limits.horizon[1], step: 0.05, value: S.horizon,
        format: (v) => `${v.toFixed(2)} s`, onInput: (h) => sendSet({ horizon: h }) });
    const controls = card('Camera velocity $\\vv_c=(\\nu_c,\\omega_c)$', 'constant during $T$');
    controls.body.append(
        h('div', { class: 'toolbar', style: 'padding-top:0' }, presets.el),
        h('p', { class: 'slider-group-title' }, 'linear velocity'),
        h('div', { class: 'slider-group' }, vSliders.slice(0, 3).map((s) => s.el)),
        h('p', { class: 'slider-group-title' }, 'angular velocity'),
        h('div', { class: 'slider-group' }, vSliders.slice(3).map((s) => s.el)),
        h('p', { class: 'slider-group-title' }, 'point and duration'),
        h('div', { class: 'slider-group' }, depth.el, horizon.el));

    // ---------------------------------------------------------------- interaction matrix
    const matrix = card('Interaction matrix $\\vL_p$', 'normalized coordinates, $f=1$');
    const matrixTex = h('div', { class: 'matrix-tex' });
    const productTex = h('div', { class: 'matrix-tex' });
    const matrixReadouts = readouts([
        { key: 'rank', label: '$\\rank\\vL_p$' },
        { key: 'null', label: '$\\dim\\Null(\\vL_p)$' },
        { key: 'invisible', label: '$\\vv_c\\in\\Null(\\vL_p)$?' },
    ]);
    matrix.body.append(matrixTex, productTex,
        h('p', { class: 'equation-note' }, label('Translation columns (orange) scale with $1/Z$; rotation columns (violet) do not depend on $Z$.')),
        matrixReadouts.el);

    workspace.append(
        h('section', { class: 'views' }, scene.el, image.el),
        h('section', { class: 'plots' }, controls.el, matrix.el));

    image.view.enableDrag({ getPoint: () => S.s, onDrag: ([x, y]) => sendSet({ x, y }) });
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;

    // ---------------------------------------------------------------- drawing
    function drawScene() {
        scene.view.draw((g) => {
            const c = colors(g.p);
            g.floor({ level: 0.9, extent: 2.5, step: 0.5, zFrom: -1.5, zTo: 5 });
            const P = S.P;
            const imagePoint = [S.x * FRUSTUM, S.y * FRUSTUM, FRUSTUM];
            g.camera([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], { color: g.p.ink, size: FRUSTUM, fill: g.p.surfaceSoft });
            g.camera(S.camera_final, { color: g.p.muted, size: FRUSTUM, axes: false, dash: [5, 4], width: 1.3 });
            g.polyline(S.camera_origins, { color: c.trans, width: 1.4, dash: [2, 4] });
            g.line([0, 0, 0], P, { color: g.p.muted, width: 1, dash: [4, 4] });
            const end = S.camera_final.slice(0, 3).map((row) => row[3]);
            if (S.depth_final > 0) g.line(end, P, { color: c.lin, width: 1, dash: [4, 4] });
            g.point(imagePoint, { r: 3, color: c.point });
            g.point(P, { r: 5, color: c.point });
            g.label(P, 'P');
            const nu = S.v.slice(0, 3), w = S.v.slice(3);
            g.arrow([0, 0, 0], nu.map((v) => 2.0 * v), { color: c.trans, width: 2.4 });
            if (Math.hypot(...w) > 1e-6) g.arrow([0, 0, 0], w.map((v) => 2.0 * v), { color: c.rot, width: 2.4 });
        });
    }

    function drawImage() {
        image.view.draw((g) => {
            const c = colors(g.p);
            g.frame({ step: 0.1 });
            g.text([IMAGE.x0, IMAGE.y0], 'x →', { dx: 6, dy: 14 });
            g.text([IMAGE.x0, IMAGE.y0], 'y ↓', { dx: 6, dy: 28 });
            const T = S.horizon, s = S.s;
            g.polyline(S.linear, { color: c.lin, width: 1.8, dash: [6, 5] });
            g.polyline(S.path, { color: c.path, width: 2 });
            const tEnd = [s[0] + T * S.s_dot_translation[0], s[1] + T * S.s_dot_translation[1]];
            g.arrow(s, tEnd, { color: c.trans, width: 2.2 });
            g.arrow(tEnd, [tEnd[0] + T * S.s_dot_rotation[0], tEnd[1] + T * S.s_dot_rotation[1]], { color: c.rot, width: 2.2 });
            const last = S.path[S.path.length - 1];
            if (last && last[0] !== null) g.point(last, { r: 4, color: g.p.surface, ring: c.path });
            g.point(s, { r: 6, color: c.point });
        });
    }

    // ---------------------------------------------------------------- state -> page
    function matrixSource(L, p) {
        const num = (v) => (Math.abs(v) < 5e-4 ? '0' : v.toFixed(2));
        const rows = L.map((row) => row.map((v, j) => `\\textcolor{${j < 3 ? p.trans : p.rot}}{${num(v)}}`).join(' & ')).join(' \\\\ ');
        return `\\vL_p = \\begin{bmatrix} ${rows} \\end{bmatrix}`;
    }

    function update() {
        const p = colors(palette());
        S.v.forEach((v, j) => vSliders[j].set(v));
        depth.set(S.Z);
        horizon.set(S.horizon);
        if (S.preset) presets.set(S.preset);
        matrixTex.innerHTML = tex(matrixSource(S.L, p), true);
        const sd = S.s_dot.map((v) => (Math.abs(v) < 5e-5 ? '0' : v.toFixed(3)));
        productTex.innerHTML = tex(`\\dot{\\vs} = \\vL_p\\vv_c = \\begin{bmatrix} ${sd[0]} \\\\ ${sd[1]} \\end{bmatrix}`, true);
        matrixReadouts.set('rank', String(S.rank));
        matrixReadouts.set('null', String(S.null_basis[0].length));
        matrixReadouts.set('invisible', S.v_in_null ? 'yes (ṡ = 0)' : 'no', S.v_in_null ? 'good' : '');
        imageReadouts.set('speed', fmt(Math.hypot(...S.s_dot), 3));
        imageReadouts.set('gap', S.gap === null ? 'left the view'
            : fmt(S.gap, 3) + (S.travel > 1e-6 ? ` (${(100 * S.gap / S.travel).toFixed(0)}%)` : ''));
        imageReadouts.set('depth', S.depth_final > 0 ? `${S.depth_final.toFixed(2)} m` : 'behind the camera', S.depth_final > 0 ? '' : 'bad');
        drawScene();
        drawImage();
    }

    if (options.preset && PRESETS.some((x) => x.value === options.preset)) S = await session.call('preset', { name: options.preset });
    update();
}
