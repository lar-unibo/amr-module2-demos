// Lecture 1, demo 1 - Image formation: central projection x = f X / Z, extrinsics, depth loss, thin lens.
import { matrixTex, setTex } from '../lib/cams.js';
import { alpha, palette } from '../lib/theme.js';
import { card, h, label, readouts, slider } from '../lib/ui.js';
import { planeCard, plotCard, view3dCard } from '../lib/widgets.js';

const LENS = { x0: -10.5, x1: 8.5, y0: -3.4, y1: 3.4 };          // thin-lens drawing, in units of f
const HO = 1.2;                                                   // object height (units of f), fixed

export async function mount({ workspace, session, state }) {
    let S = state;

    const scene = view3dCard('Camera {C} and the scene (world frame {0})', { up: 'z', center: [0.25, 0.15, 0.25], extent: 2.2, yaw: -0.9, pitch: 0.45 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'projection ray of the selected point', color: p.red, kind: 'dashed' },
            { label: 'image plane (drawn enlarged)', color: p.accent, kind: 'line' },
        ],
    });
    const image = planeCard('Image plane: $x=fX/Z$, $y=fY/Z$', { rect: { x0: -2, x1: 2, y0: -1.5, y1: 1.5 } }, { note: 'millimetres, origin at the principal point' });
    const send = session.stream('set', (next) => { S = next; load(); });
    const sl = (key, text, min, max, step, format) => slider({ label: text, min, max, step, value: S[key], format, onInput: (v) => send({ [key]: v }) });
    const az = sl('azimuth', 'camera azimuth', -180, 180, 1, (v) => `${v.toFixed(0)}°`);
    const el = sl('elevation', 'camera elevation', 5, 85, 1, (v) => `${v.toFixed(0)}°`);
    const dist = sl('distance', 'camera distance', 0.4, 2.5, 0.01, (v) => `${v.toFixed(2)} m`);
    const f = sl('f_mm', 'focal length $f$', 2, 12, 0.1, (v) => `${v.toFixed(1)} mm`);
    const sel = sl('selected', 'selected point', 0, 9, 1, (v) => `#${v + 1}`);
    const ray = sl('ray', 'move it along its ray (×)', 0.4, 2.5, 0.01, (v) => `${v.toFixed(2)}`);
    const scale = sl('scale', 'scale the whole scene about the camera (×)', 0.4, 2.0, 0.01, (v) => `${v.toFixed(2)}`);
    const controls = card('Camera and scene', '');
    controls.body.append(h('div', { class: 'slider-group' }, az.el, el.el, dist.el, f.el),
        h('p', { class: 'slider-group-title' }, 'depth is lost'), h('div', { class: 'slider-group' }, sel.el, ray.el, scale.el));
    const extr = h('div', { class: 'matrix-tex' });
    const point = h('div', { class: 'matrix-tex' });
    const info = readouts([{ key: 'fov', label: 'field of view' }, { key: 'sensor', label: 'sensor size' }]);
    const frames = card('Extrinsics ${}^C\\vT_0$ and the selected point', '$\\tilde{\\vP}_C={}^C\\vT_0\\,\\tilde{\\vP}_0$');
    frames.body.append(extr, point, info.el);

    // thin lens: ray diagram in units of f, and where the image forms
    const lens = planeCard('Thin lens: $\\frac{1}{z_o}+\\frac{1}{z_i}=\\frac{1}{f}$', { rect: LENS, flipY: true, keepAspect: false }, {
        note: 'distances in units of $f$ (same $f$ as above) · the object has a fixed height',
        legendItems: (p) => [
            { label: 'parallel to the axis, then through $F\'$', color: p.accent, kind: 'line' },
            { label: 'through the lens centre, undeviated', color: p.gripR, kind: 'line' },
            { label: 'through $F$, then parallel', color: p.aqua, kind: 'line' },
            { label: 'image', color: p.red, kind: 'line' },
        ],
    });
    lens.canvas.style.height = 'clamp(240px, 36vh, 330px)';
    const fmtDist = (v) => (v < 1 ? `${(1000 * v).toFixed(v < 0.1 ? 1 : 0)} mm` : `${v.toFixed(2)} m`);
    const times = (r) => r.toFixed(r < 10 ? 2 : r < 100 ? 1 : 0);
    const zo = slider({ label: 'object distance $z_o$ (log scale)', min: 0.002, max: 10, log: true, value: S.z_object,
        format: (v) => `${fmtDist(v)} = ${times(1000 * v / S.f_mm)} f`, onInput: (v) => send({ z_object: v }) });
    const lensReadout = readouts([{ key: 'zi', label: 'image distance $z_i$' }, { key: 'gap', label: '$z_i - f$' },
        { key: 'm', label: 'magnification $m=-z_i/z_o$' }]);
    const lensControls = card('Object distance', 'the image forms where the rays meet');
    lensControls.body.append(zo.el, lensReadout.el);
    const where = plotCard('Where the image forms', { xLabel: 'z_o / f  (log scale)', yLabel: 'z_i / f', logX: true, x: [1, 10000], y: [0, 6] },
        { note: 'dashed: $z_i=f$, the pinhole model', size: 'short' });

    workspace.append(h('section', { class: 'views' }, scene.el, image.el), h('section', { class: 'plots' }, controls.el, frames.el),
        lens.el, h('section', { class: 'plots' }, lensControls.el, where.el));
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;
    lens.view.redraw = drawLens;

    const at = (T, q) => [0, 1, 2].map((i) => T[i][0] * q[0] + T[i][1] * q[1] + T[i][2] * q[2] + T[i][3]);

    function drawScene() {
        scene.view.draw((g) => {
            const p = g.p;
            g.table({ extent: 0.5, step: 0.1 });
            g.frame([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], { size: 0.15, label: '{0}' });
            for (const [a, b] of S.edges) g.line(S.world[a], S.world[b], { color: p.ink, width: 1.8 });
            S.world.forEach((q, i) => g.point(q, { r: i === S.selected ? 5 : 2.5, color: i === S.selected ? p.red : p.ink, ring: null }));
            g.camera(S.T_0c, { color: p.inkSoft, size: 0.12, axes: true, width: 1.6 });
            g.label(at(S.T_0c, [0, 0, 0]), '{C}', { dx: -18, dy: -8 });
            // the image plane drawn enlarged, at a depth proportional to f
            const d = 0.03 * S.f_mm, sw = S.sensor_mm[0] / S.f_mm * d / 2, sh = S.sensor_mm[1] / S.f_mm * d / 2;
            g.polyline([[-sw, -sh, d], [sw, -sh, d], [sw, sh, d], [-sw, sh, d], [-sw, -sh, d]].map((q) => at(S.T_0c, q)), { color: p.accent, width: 1.4 });
            for (const [a, b] of S.edges) {
                const qa = S.image_mm[a].map((v) => v / S.f_mm * d), qb = S.image_mm[b].map((v) => v / S.f_mm * d);
                g.line(at(S.T_0c, [qa[0], qa[1], d]), at(S.T_0c, [qb[0], qb[1], d]), { color: p.accent, width: 1.2 });
            }
            g.line(at(S.T_0c, [0, 0, 0]), S.world[S.selected], { color: alpha(p.red, 0.7), width: 1.2, dash: [5, 4] });
        });
    }
    function drawImage() {
        image.view.draw((g) => {
            const p = g.p;
            const w = S.sensor_mm[0] / 2, hh = S.sensor_mm[1] / 2;
            g.frame({ step: 0.25, axes: true });
            g.polyline([[-w, -hh], [w, -hh], [w, hh], [-w, hh], [-w, -hh]], { color: p.accent, width: 1.8 });
            g.text([-w, -hh], 'sensor', { dy: -5, size: 10, color: p.accent });
            for (const [a, b] of S.edges) g.line(S.image_mm[a], S.image_mm[b], { color: p.ink, width: 1.8 });
            S.image_mm.forEach((q, i) => g.point(q, { r: i === S.selected ? 5 : 2.5, color: i === S.selected ? p.red : p.ink, ring: null }));
        });
    }
    function drawLens() {
        lens.view.draw((g) => {
            const p = g.p, L = S.lens, zo = L.zo_over_f, zi = L.zi_over_f, R = LENS;
            const xs = Math.max(-zo, R.x0 - 1);                         // where the incoming rays enter the drawing
            g.line([R.x0, 0], [R.x1, 0], { color: p.lineStrong, width: 1 });
            for (const x of [-2, -1, 1, 2]) {
                g.point([x, 0], { r: 3, color: p.ink, ring: null });
                g.text([x, 0], `${Math.abs(x) === 2 ? '2' : ''}F${x > 0 ? '′' : ''}`, { dy: 15, size: 10, align: 'center', color: p.inkSoft });
            }
            g.arrow([0, 0], [0, R.y1 - 0.15], { color: p.accent, width: 3, head: 9 });
            g.arrow([0, 0], [0, R.y0 + 0.15], { color: p.accent, width: 3, head: 9 });

            // the three principal rays from the tip of the object: y(x) before the lens, height at the lens, slope after it
            const rays = [
                { color: p.accent, before: () => HO, at: HO, slope: -HO },
                { color: p.gripR, before: (x) => -HO * x / zo, at: 0, slope: -HO / zo },
                ...(Math.abs(zo - 1) > 1e-6 ? [{ color: p.aqua, before: (x) => HO * (x + 1) / (1 - zo), at: HO / (1 - zo), slope: 0 }] : []),
            ].filter((r) => Math.abs(r.at) < R.y1);
            const real = L.real && zi !== null, hi = L.magnification === null ? null : L.magnification * HO;
            for (const r of rays) {
                g.line([xs, r.before(xs)], [0, r.at], { color: r.color, width: 1.6 });
                const xEnd = real ? Math.min(zi, R.x1 + 1) : R.x1 + 1;
                g.line([0, r.at], [xEnd, r.at + r.slope * xEnd], { color: r.color, width: 1.6 });
                if (real && zi < R.x1) g.line([zi, hi], [R.x1 + 1, r.at + r.slope * (R.x1 + 1)], { color: alpha(r.color, 0.3), width: 1.2 });
                if (!real && zi !== null) g.line([0, r.at], [zi, hi], { color: alpha(r.color, 0.6), width: 1.2, dash: [4, 4] });
            }

            // object
            if (-zo >= R.x0) {
                g.arrow([-zo, 0], [-zo, HO], { color: p.ink, width: 2.4, head: 8 });
                g.text([-zo, HO], 'object', { dy: -7, align: 'center', color: p.ink });
            } else {
                g.text([R.x0, HO], `← object at z_o = ${times(zo)} f`, { dx: 2, dy: -7, color: p.ink });
            }
            // image
            if (real) {
                if (zi <= R.x1) {
                    g.line([zi, R.y0 + 0.2], [zi, R.y1 - 0.2], { color: alpha(p.red, 0.45), width: 1, dash: [3, 4] });
                    if (Math.abs(hi) > 0.12) g.arrow([zi, 0], [zi, hi], { color: p.red, width: 2.4, head: 8 });
                    else g.point([zi, hi], { r: 3.5, color: p.red, ring: null });
                    g.text([zi, R.y0 + 0.2], `image, z_i = ${zi.toFixed(zi < 1.1 ? 3 : 2)} f`, { dx: 4, dy: -4, size: 10, color: p.red });
                } else {
                    g.text([R.x1, R.y0 + 0.2], `image at z_i = ${times(zi)} f →`, { dx: -4, dy: -4, size: 10, align: 'right', color: p.red });
                }
            } else if (zi === null) {
                g.text([R.x1, R.y1 - 0.2], 'z_o = f: the rays leave parallel, image at infinity', { dx: -4, dy: 10, size: 10, align: 'right', color: p.red });
            } else {
                if (zi >= R.x0 && Math.abs(hi) < R.y1) g.arrow([zi, 0], [zi, hi], { color: alpha(p.red, 0.7), width: 2, head: 8, dash: [4, 3] });
                g.text([R.x1, R.y1 - 0.2], 'z_o < f: the rays diverge, no real image', { dx: -4, dy: 10, size: 10, align: 'right', color: p.red });
                g.text([R.x1, R.y1 - 0.2], '(dashed: they seem to come from a virtual image)', { dx: -4, dy: 24, size: 10, align: 'right', color: p.red });
            }
        });
    }
    function drawWhere() {
        const p = palette(), L = S.lens;
        where.plot.set({ series: [{ x: L.curve_zo, y: L.curve_zi, color: p.accent, width: 2 }],
            hlines: [{ y: 1, color: alpha(p.red, 0.6), dash: [5, 4] }],
            markers: L.real ? [{ x: L.zo_over_f, y: L.zi_over_f, color: p.red, r: 5 }] : [] });
    }
    function draw() { drawScene(); drawImage(); drawLens(); drawWhere(); }

    function load() {
        az.set(S.azimuth); el.set(S.elevation); dist.set(S.distance); f.set(S.f_mm); sel.set(S.selected); ray.set(S.ray); scale.set(S.scale); zo.set(S.z_object);
        setTex(extr, matrixTex('{}^C\\vT_0', S.T_c0, 3));
        const P = S.P_c[S.selected], q = S.image_mm[S.selected];
        setTex(point, `\\begin{gathered}\\vP_C=\\begin{bmatrix}${P.map((v) => v.toFixed(3)).join('\\\\')}\\end{bmatrix}\\text{ m}\\\\[2pt]`
            + `x=f\\tfrac{X}{Z}=${q[0].toFixed(3)}\\text{ mm},\\quad y=f\\tfrac{Y}{Z}=${q[1].toFixed(3)}\\text{ mm}\\end{gathered}`);
        info.set('fov', `${S.fov_deg[0].toFixed(0)}° × ${S.fov_deg[1].toFixed(0)}°`);
        info.set('sensor', `${S.sensor_mm[0].toFixed(1)} × ${S.sensor_mm[1].toFixed(1)} mm`);
        const Ln = S.lens;
        lensReadout.set('zi', S.z_image_mm === null ? (Ln.zi_over_f === null ? 'at infinity' : 'none (virtual)') : `${S.z_image_mm.toFixed(3)} mm`);
        lensReadout.set('gap', S.z_image_mm === null ? '—' : `${(S.z_image_mm - S.f_mm).toFixed(3)} mm`);
        lensReadout.set('m', Ln.magnification === null ? '—'
            : Ln.magnification.toFixed(Math.abs(Ln.magnification) < 0.1 ? 4 : 2));
        draw();
    }
    load();
}
