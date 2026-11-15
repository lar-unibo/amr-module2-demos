// Lecture 3, demo 3 - ICP: pose of a known object from a partial, noisy depth view.
import { cursor, playback } from '../lib/servo.js';
import { alpha, mix, palette } from '../lib/theme.js';
import { button, card, h, readouts, segmented, slider } from '../lib/ui.js';
import { planeCard, plotCard, plotsGrid, view3dCard } from '../lib/widgets.js';

const PERIOD = 0.12;                      // seconds per iteration at 1x
const apply = (T, q) => [0, 1, 2].map((i) => T[i][0] * q[0] + T[i][1] * q[1] + T[i][2] * q[2] + T[i][3]);

export async function mount({ workspace, session, state, options }) {
    let S = state;
    if (options.preset) S = await session.call('preset', { name: options.preset });
    let k = 0;

    const scene = view3dCard('Depth camera, scene points and the ICP estimate', { up: 'z', center: [0.13, -0.09, 0.14], extent: 0.56, yaw: -0.25, pitch: 0.42 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'scene $s_j$', color: p.rod, kind: 'dot' },
            { label: 'model at the estimate', color: p.red, kind: 'dot' },
            { label: 'pairs $(m_{c(j)}, s_j)$ · rejected', color: p.red, kind: 'dashed' },
            { label: 'true pose (unknown to ICP)', color: p.muted, kind: 'dashed' },
        ],
    });
    scene.canvas.style.height = 'clamp(380px, 56vh, 560px)';
    const image = planeCard('What the depth camera measures', { rect: { x0: 0, x1: S.width, y0: 0, y1: S.height } }, {
        note: `${S.width} × ${S.height} pixels · grey: no measurement`,
    });
    image.canvas.style.height = '210px';

    const player = playback({ onFrame: (i) => { k = i; draw(); }, format: (i, n) => `iteration ${i} / ${n - 1}` });
    const status = h('span', { class: 'run-status' });
    const runReadouts = readouts([
        { key: 'it', label: 'iterations' }, { key: 'rms', label: 'RMS of the pairs' },
        { key: 'rot', label: 'rotation error' }, { key: 'trans', label: 'translation error' },
    ]);
    const runCard = card('ICP run', '');
    runCard.body.append(player.el, h('div', { class: 'toolbar' }, status), runReadouts.el);

    // ---- controls
    const send = session.stream('set', (next) => { S = next; load(); });
    const sl = (key, text, min, max, step, format) => slider({ label: text, min, max, step, value: S[key], format, onInput: (v) => send({ [key]: v }) });
    const yaw0 = sl('yaw0', 'initial guess: rotation error about $z$', -180, 180, 1, (v) => `${v.toFixed(0)}°`);
    const dx0 = sl('dx0', 'initial guess: offset $x$', -6, 6, 0.1, (v) => `${v.toFixed(1)} cm`);
    const dy0 = sl('dy0', 'initial guess: offset $y$', -6, 6, 0.1, (v) => `${v.toFixed(1)} cm`);
    const noise = sl('noise', 'depth noise σ', 0, 8, 0.5, (v) => `${v.toFixed(1)} mm`);
    const outliers = sl('outliers', 'outliers (stray depths)', 0, 200, 5, (v) => String(Math.round(v)));
    const preset = (name) => async () => { S = await session.call('preset', { name }); load({ at: 'start' }); player.start(); };
    const guess = card('Initial guess and data', 'the true pose is fixed; the guess is turned and shifted');
    guess.body.append(h('div', { class: 'slider-group' }, yaw0.el, dx0.el, dy0.el, noise.el, outliers.el),
        h('div', { class: 'toolbar' },
            button('good guess', preset('good'), { small: true }),
            button('bad guess', preset('far'), { small: true, title: 'turned by 120°: a local minimum' }),
            button('outliers', preset('outliers'), { small: true }),
            button('outliers + rejection', preset('rejection'), { small: true }),
            button('point-to-plane', preset('plane'), { small: true })));

    const metric = segmented({ options: [{ value: 'point', label: 'point-to-point' }, { value: 'plane', label: 'point-to-plane' }],
        value: S.metric, onChange: (v) => send({ metric: v }) });
    const reject = segmented({ options: [{ value: 'none', label: 'none' }, { value: 'distance', label: 'distance > threshold' }, { value: 'worst', label: 'worst n%' }],
        value: S.reject, onChange: (v) => send({ reject: v }) });
    const distance = sl('reject_distance', 'distance threshold', 0.3, 5, 0.1, (v) => `${v.toFixed(1)} cm`);
    const worst = sl('reject_worst', 'worst pairs rejected', 1, 50, 1, (v) => `${v.toFixed(0)} %`);
    const variant = card('ICP variant', 'slides 48–51');
    variant.body.append(h('div', { class: 'choice-row' }, h('span', {}, 'error metric'), metric.el),
        h('div', { class: 'choice-row' }, h('span', {}, 'reject pairs'), reject.el),
        h('div', { class: 'slider-group' }, distance.el, worst.el));

    const errorPlot = plotCard('Alignment error E', { xLabel: 'iteration', logY: true }, { size: 'short' });
    const posePlot = plotCard('Distance from the true pose', { xLabel: 'iteration', yLabel: '° / mm' }, { size: 'short' });

    workspace.append(
        h('section', { class: 'views' }, scene.el, h('div', {}, image.el, runCard.el)),
        h('section', { class: 'plots' }, guess.el, variant.el),
        plotsGrid(errorPlot, posePlot));
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;

    function drawScene() {
        scene.view.draw((g) => {
            const p = g.p;
            g.table({ extent: 0.18, step: 0.03 });
            g.camera(S.T_cam, { color: p.inkSoft, size: 0.06, axes: false, width: 1.4 });
            g.label(S.T_cam.slice(0, 3).map((row) => row[3]), 'depth camera', { size: 11 });
            for (const [a, b] of S.edges) g.line(apply(S.T_true, a), apply(S.T_true, b), { color: alpha(p.muted, 0.7), width: 1, dash: [3, 3] });
            const T = S.T[k], pairs = S.pairs[k], rejected = new Set(S.rejected[k]);
            const moved = S.model.map((q) => apply(T, q));
            S.scene.forEach((s, j) => {
                const q = moved[pairs[j]];
                if (!rejected.has(j)) g.line(s, q, { color: alpha(p.red, 0.28), width: 1 });
                else g.line(s, q, { color: alpha(p.muted, 0.5), width: 1, dash: [2, 3] });
            });
            moved.forEach((q) => g.point(q, { r: 1.7, color: alpha(p.red, 0.8), ring: null }));
            S.scene.forEach((s) => g.point(s, { r: 2.2, color: p.rod, ring: null }));
            for (const [a, b] of S.edges) g.line(apply(T, a), apply(T, b), { color: p.red, width: 1.6 });
        });
    }

    function drawImage() {
        image.view.draw((g) => {
            const p = g.p, ctx = g.ctx;
            const [x0, y0] = g.view.toScreen([0, 0]), [x1, y1] = g.view.toScreen([S.width, S.height]);
            ctx.fillStyle = p.surfaceSoft;
            ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
            const dmin = Math.min(...S.depth), dmax = Math.max(...S.depth);
            const near = p.dark ? '#f2b52a' : '#eda100', far = p.dark ? '#4b93ea' : '#2a3a9e';
            S.uv.forEach(([u, v], j) => {
                const [sx, sy] = g.view.toScreen([u - 0.5, v - 0.5]);
                ctx.fillStyle = mix(near, far, (S.depth[j] - dmin) / Math.max(dmax - dmin, 1e-9));
                ctx.fillRect(sx, sy, g.view.k + 0.5, g.view.k + 0.5);
            });
            ctx.strokeStyle = p.lineStrong; ctx.lineWidth = 1;
            ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
            g.text([0, S.height], `near ${(100 * dmin).toFixed(0)} cm`, { dy: 13, size: 10, color: near });
            g.text([S.width, S.height], `far ${(100 * dmax).toFixed(0)} cm`, { dy: 13, size: 10, color: far, align: 'right' });
        });
    }

    function drawPlots() {
        const p = palette();
        const it = S.E.map((_, i) => i);
        errorPlot.plot.set({ series: [{ x: it, y: S.E, color: p.accent, width: 2 }], vlines: cursor(k, p) });
        errorPlot.setLegend([{ label: S.metric === 'plane' ? 'E, point-to-plane (m²)' : 'E, point-to-point (m²)', color: p.accent }]);
        posePlot.plot.set({ series: [{ x: it, y: S.rot_err, color: p.gripL, width: 2 }, { x: it, y: S.trans_err, color: p.gripR, width: 2 }],
            vlines: cursor(k, p) });
        posePlot.setLegend([{ label: 'rotation error (°)', color: p.gripL }, { label: 'translation error (mm)', color: p.gripR }]);
    }

    function draw() {
        drawScene(); drawImage(); drawPlots();
        runReadouts.set('rms', `${S.rms[k].toFixed(1)} mm`);
        runReadouts.set('rot', `${S.rot_err[k].toFixed(2)}°`, k === S.E.length - 1 ? (S.rot_err[k] < 5 ? 'good' : 'bad') : '');
        runReadouts.set('trans', `${S.trans_err[k].toFixed(1)} mm`, k === S.E.length - 1 ? (S.trans_err[k] < 10 ? 'good' : 'bad') : '');
    }

    function load({ at = 'end' } = {}) {
        yaw0.set(S.yaw0); dx0.set(S.dx0); dy0.set(S.dy0); noise.set(S.noise); outliers.set(S.outliers);
        metric.set(S.metric); reject.set(S.reject); distance.set(S.reject_distance); worst.set(S.reject_worst);
        distance.disable(S.reject !== 'distance'); worst.disable(S.reject !== 'worst');
        runReadouts.set('it', S.converged ? String(S.iterations) : `${S.iterations} (limit)`);
        const kept = S.n_kept[S.n_kept.length - 1];
        runCard.note.textContent = `${S.n_scene} scene points (${S.n_outliers} outliers) · ${S.model.length} model points · ${kept} pairs kept at the end`;
        if (S.found) {
            status.className = 'run-status good';
            status.textContent = S.converged ? `✓ converged to the true pose in ${S.iterations} iterations`
                : '✓ close to the true pose (iteration limit reached)';
        } else {
            status.className = 'run-status bad';
            const lower = S.rms_true < S.rms[S.rms.length - 1];
            status.textContent = S.converged
                ? `✗ stopped at a wrong pose${lower ? ` (local minimum: the true pose has RMS ${S.rms_true.toFixed(1)} mm)` : ''}`
                : '✗ no convergence within the iteration limit';
        }
        player.load(S.T.length, PERIOD, { at });
    }
    load();
}
