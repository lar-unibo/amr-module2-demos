// Lecture 1, demo 6 - Depth from two cameras (normal stereo) and from pixels to 3-D points.
import { setTex } from '../lib/cams.js';
import { alpha, palette } from '../lib/theme.js';
import { card, h, label, readouts, segmented, slider } from '../lib/ui.js';
import { planeCard, plotCard } from '../lib/widgets.js';

const TOP = { x0: -1.4, x1: 1.6, y0: -0.7, y1: 15.5 };          // x (m) horizontally, Z (m) upward

export async function mount({ workspace, session, state }) {
    let S = state;

    const top = planeCard('Top view: two cameras and a point', { rect: TOP, flipY: true, keepAspect: false }, {
        note: 'drag the red point · x is stretched to show the baseline',
        legendItems: (p) => [
            { label: 'rays from the two cameras', color: p.red, kind: 'dashed' },
            { label: 'measured point', color: p.red, kind: 'ring' },
            { label: 'the only depths a whole-pixel disparity can give', color: p.accent, kind: 'dashed' },
        ],
    });
    top.canvas.style.height = 'clamp(360px, 52vh, 520px)';
    const rows = planeCard('Where the point appears in the two images', { rect: { x0: -20, x1: 660, y0: -0.2, y1: 3.1 }, keepAspect: false }, {
        note: 'the same image row (epipolar line)',
    });
    rows.canvas.style.height = '190px';
    const imageReadouts = readouts([
        { key: 'uL', label: '$u_L$ (left)' }, { key: 'uR', label: '$u_R$ (right)' },
        { key: 'd', label: 'disparity $d=u_L-u_R$' }, { key: 'z', label: "depth $Z=bf'/d$" },
    ]);
    rows.body.append(imageReadouts.el);

    const send = session.stream('set', (next) => { S = next; load(); });
    const sl = (key, text, min, max, step, format) => slider({ label: text, min, max, step, value: S[key], format, onInput: (v) => send({ [key]: v }) });
    const baseline = sl('b', 'baseline $b$', 0.02, 0.6, 0.005, (v) => `${(100 * v).toFixed(1)} cm`);
    const focal = sl('f_px', "focal length in pixels $f'=f/\\rho_w$", 200, 1600, 10, (v) => `${v.toFixed(0)} px`);
    const noise = sl('noise', 'matching noise on $d$', 0, 2, 0.05, (v) => `${v.toFixed(2)} px`);
    const px = sl('probe_x', 'point $X$', -1.2, 1.4, 0.01, (v) => `${v.toFixed(2)} m`);
    const pz = sl('probe_z', 'point depth $Z$', 0.4, 15, 0.05, (v) => `${v.toFixed(2)} m`);
    const step = segmented({ options: [{ value: '1 pixel', label: 'whole pixels' }, { value: '1/4 pixel', label: '1/4 pixel' }, { value: 'exact', label: 'exact' }],
        value: S.step, onChange: (v) => send({ step: v }) });
    const controls = card('Stereo camera', 'parallel optical axes, right camera shifted by $b$ along $x$');
    controls.body.append(h('div', { class: 'slider-group' }, baseline.el, focal.el, px.el, pz.el),
        h('div', { class: 'choice-row' }, h('span', {}, 'disparity measured in'), step.el), noise.el);
    const bpTex = h('div', { class: 'matrix-tex' });
    const res = readouts([{ key: 'res', label: 'depth step at this $Z$' }, { key: 'err', label: 'depth error' }]);
    const back = card('From pixels to the 3-D point', 'once $Z$ is known (slide 41)');
    back.body.append(bpTex, res.el);

    const curve = plotCard("Depth from disparity: $Z=bf'/d$", { xLabel: 'disparity d (px)', yLabel: 'Z (m)', y: [0, 15] }, { size: 'short' });

    workspace.append(h('section', { class: 'views' }, top.el, h('div', {}, rows.el, back.el)),
        h('section', { class: 'plots' }, controls.el, curve.el));
    top.view.redraw = drawTop;
    rows.view.redraw = drawRows;
    top.view.enableDrag({ getPoint: () => [S.probe_x, S.probe_z], radius: 22,
        onDrag: ([x, z]) => send({ probe_x: Math.max(-1.2, Math.min(1.4, x)), probe_z: Math.max(0.4, Math.min(15, z)) }) });

    function drawTop() {
        top.view.draw((g) => {
            const p = g.p;
            for (let z = 0; z <= 15; z += 1) {
                g.line([TOP.x0, z], [TOP.x1, z], { color: p.grid, width: 1 });
                if (z % 3 === 0) g.text([TOP.x0, z], `${z} m`, { dx: 2, dy: -3, size: 10 });
            }
            // the depths a quantized disparity can give: drawn while they are at least 3 px apart
            let last = null;
            const q = { '1 pixel': 1, '1/4 pixel': 0.25 }[S.step];
            S.layers.forEach((z, i) => {
                const y = g.view.toScreen([0, z])[1];
                if (last !== null && Math.abs(y - last) < 3) return;
                g.line([TOP.x0, z], [TOP.x1, z], { color: alpha(p.accent, 0.45), width: 1, dash: [4, 4] });
                const next = S.layers[i + 1];                       // label the lines that have room for it
                if (next !== undefined && Math.abs(g.view.toScreen([0, next])[1] - y) >= 14 && (last === null || Math.abs(y - last) >= 14)) {
                    const d = Math.round(S.b * S.f_px / z / q) * q;
                    g.text([TOP.x1, z], `d = ${d} px`, { dx: -4, dy: -3, size: 9, align: 'right', color: p.accent });
                }
                last = y;
            });
            const cams = [[0, 'L'], [S.b, 'R']];
            for (const [x] of cams) g.line([x, 0], [S.probe_x, S.probe_z], { color: alpha(p.red, 0.75), width: 1.3, dash: [5, 4] });
            for (const [x, name] of cams) {
                const [sx, sy] = g.view.toScreen([x, 0]);
                const ctx = g.ctx;
                ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx - 9, sy + 14); ctx.lineTo(sx + 9, sy + 14); ctx.closePath();
                ctx.fillStyle = p.surface; ctx.fill(); ctx.strokeStyle = p.ink; ctx.lineWidth = 1.8; ctx.stroke();
                g.text([x, 0], name, { dx: name === 'L' ? -20 : 12, dy: 12, size: 11, color: p.ink });
            }
            g.line([0, -0.45], [S.b, -0.45], { color: p.ink, width: 1.5 });
            g.text([S.b / 2, -0.45], `b = ${(100 * S.b).toFixed(0)} cm`, { dy: 14, size: 10, align: 'center' });
            const m = S.probe_reconstructed;
            if (m[2] !== null && m[2] < 16) g.point([m[0], m[2]], { r: 7, color: 'rgba(0,0,0,0)', ring: p.red });
            g.point([S.probe_x, S.probe_z], { r: 6, color: p.red, ring: p.surface });
        });
    }
    function drawRows() {
        rows.view.draw((g) => {
            const p = g.p;
            const bar = (y, name) => {
                g.ctx.fillStyle = p.surfaceSoft;
                const [x0, y0] = g.view.toScreen([0, y - 0.3]), [x1, y1] = g.view.toScreen([S.W, y + 0.3]);
                g.ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
                g.polyline([[0, y - 0.3], [S.W, y - 0.3], [S.W, y + 0.3], [0, y + 0.3], [0, y - 0.3]], { color: p.lineStrong, width: 1.2 });
                for (let u = 0; u <= S.W; u += 80) g.text([u, y + 0.3], String(u), { dy: 12, size: 9, align: 'center' });
                g.text([0, y - 0.3], name, { dy: -4, size: 10, color: p.inkSoft });
                g.line([S.u0, y - 0.3], [S.u0, y + 0.3], { color: alpha(p.muted, 0.6), width: 1, dash: [2, 3] });
            };
            bar(0.45, 'left image (row v)');
            bar(2.1, 'right image (same row)');
            const [uL] = S.probe_left, [uR] = S.probe_right;
            g.line([uL, 0.45], [uL, 2.1], { color: alpha(p.red, 0.35), width: 1, dash: [3, 3] });
            g.point([uL, 2.1], { r: 5, color: p.surface, ring: alpha(p.red, 0.7) });
            g.arrow([uL, 2.1], [uR, 2.1], { color: p.gripR, width: 2.2, head: 8 });
            g.text([(uL + uR) / 2, 2.1], `d = ${S.probe_disparity_true.toFixed(1)} px`, { dy: -12, size: 11, align: 'center', color: p.gripR });
            g.point([uL, 0.45], { r: 6, color: p.red, ring: p.surface });
            g.point([uR, 2.1], { r: 6, color: p.red, ring: p.surface });
        });
    }
    function drawPlots() {
        const p = palette();
        curve.plot.set({ series: [{ x: S.curve_d, y: S.curve_z, color: p.accent, width: 2 }],
            markers: [{ x: S.probe_disparity, y: S.probe_reconstructed[2] ?? NaN, color: p.red, r: 5 }] });
    }

    function load() {
        baseline.set(S.b); focal.set(S.f_px); noise.set(S.noise); px.set(S.probe_x); pz.set(S.probe_z); step.set(S.step);
        const [uL, v] = S.probe_left, [uR] = S.probe_right;
        const z = S.probe_reconstructed[2];
        imageReadouts.set('uL', `${uL.toFixed(1)} px`);
        imageReadouts.set('uR', `${uR.toFixed(1)} px`);
        imageReadouts.set('d', S.step === 'exact' && S.noise === 0 ? `${S.probe_disparity.toFixed(2)} px`
            : `${S.probe_disparity.toFixed(2)} px (true ${S.probe_disparity_true.toFixed(2)})`);
        imageReadouts.set('z', z === null ? 'no match' : `${z.toFixed(2)} m`);
        const bp = S.back_projection;
        setTex(bpTex, `\\vP_C=Z\\,\\vK^{-1}\\begin{bmatrix}u_L\\\\v\\\\1\\end{bmatrix}=\\begin{bmatrix}${bp.map((x) => x.toFixed(2)).join('\\\\')}\\end{bmatrix}\\text{ m}`);
        res.set('res', S.step === 'exact' ? '— (exact)' : `${(100 * S.probe_resolution).toFixed(1)} cm`);
        res.set('err', z === null ? '—' : `${(100 * (z - S.probe_z)).toFixed(1)} cm`, z !== null && Math.abs(z - S.probe_z) < 0.03 * S.probe_z ? 'good' : 'bad');
        drawTop(); drawRows(); drawPlots();
    }
    load();
}
