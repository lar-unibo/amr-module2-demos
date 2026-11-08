// Lecture 2, demo 1 - PBVS: s = (d_t_c, theta m), nu = -lambda R^T t, omega = -lambda theta m.
import { borderRatio, cursor, drawServoImage, drawServoScene, IMAGE_RECT, playback, servoColors, statusText } from '../lib/servo.js';
import { tex } from '../lib/math.js';
import { alpha, palette } from '../lib/theme.js';
import { card, h, label, readouts, segmented, slider } from '../lib/ui.js';
import { planeCard, plotCard, plotsGrid, view3dCard } from '../lib/widgets.js';

const PRESET_ORDER = ['general', 'translation', 'rot_z_1', 'rot_z_2.8', 'rot_z_pi', 'tilt'];
const V_TEX = ['\\nu_x', '\\nu_y', '\\nu_z', '\\omega_x', '\\omega_y', '\\omega_z'];

export async function mount({ workspace, session, state, options = {} }) {
    let S = state;
    let k = 0;

    const scene = view3dCard('Camera and target', { center: [0, 0, -0.55], extent: 2.4, yaw: -0.85, pitch: 0.38 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'desired camera $\\mathcal F_d$', color: servoColors(p).desired, kind: 'line' },
            { label: 'current camera $\\mathcal F_c$ and its path', color: servoColors(p).current, kind: 'line' },
            { label: 'straight line to $\\mathcal F_d$', color: servoColors(p).other, kind: 'dashed' },
        ],
    });
    const image = planeCard('Image plane', { rect: IMAGE_RECT }, {
        note: 'not controlled by PBVS',
        legendItems: (p) => [
            { label: 'desired $\\vs^{*}$', color: servoColors(p).desired, kind: 'ring' },
            { label: 'current points and image paths', color: servoColors(p).current, kind: 'dot' },
        ],
    });
    const player = playback({ onFrame: (i) => { k = i; draw(); } });
    const statusEl = h('span', { class: 'run-status' });
    const runCard = card('Run', '');
    runCard.body.append(player.el, h('div', { class: 'toolbar' }, statusEl));

    // ---- controls and the features at time t
    const send = session.stream('set', (next) => { S = next; load(); });
    const presets = segmented({
        options: PRESET_ORDER.map((id) => ({ value: id, label: S.presets[id] })),
        value: S.preset, onChange: (preset) => send({ preset }),
    });
    const gain = slider({ label: 'gain $\\lambda$', min: 0.1, max: 2.0, step: 0.05, value: S.lam, format: (v) => v.toFixed(2),
        onInput: (lam) => send({ lam }) });
    const controls = card('Start pose and controller', '$\\nu_c=-\\lambda\\,{}^d\\vR_c^{T}\\,{}^d\\vt_c,\\ \\omega_c=-\\lambda\\,\\theta\\vm$');
    controls.body.append(h('p', { class: 'slider-group-title' }, 'start pose (relative to the desired camera)'), presets.el,
        h('div', { style: 'margin-top:8px' }, gain.el));
    const featureTex = h('div', { class: 'matrix-tex' });
    const result = readouts([
        { key: 'status', label: 'result' },
        { key: 'border', label: 'points stay in the image?' },
        { key: 'straight', label: 'camera path' },
    ]);
    const features = card('Features at time $t$', '$\\vs=({}^d\\vt_c,\\ \\theta\\vm)$, $\\vs^{*}=\\mathbf 0$');
    features.body.append(featureTex, result.el);

    // ---- plots
    const decayPlot = plotCard('Translation and rotation errors', { xLabel: 't (s)' }, { size: 'short' });
    const velocityPlot = plotCard('Camera velocity $\\vv_c$', { xLabel: 't (s)' }, { size: 'short' });
    const borderPlot = plotCard('Points relative to the image border', { xLabel: 't (s)', y: [0, 1.6] },
        { size: 'short', note: 'above 1: a point is outside the image' });

    workspace.append(
        h('section', { class: 'views' }, scene.el, image.el),
        runCard.el,
        h('section', { class: 'plots' }, controls.el, features.el),
        plotsGrid(decayPlot, velocityPlot, borderPlot));
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;

    function drawScene() {
        scene.view.draw((g) => {
            drawServoScene(g, { points: S.points, T_od: S.T_od, runs: [{ T: S.T, positions: S.positions }], k });
            const end = S.T_od.slice(0, 3).map((row) => row[3]);
            g.line(S.positions[0], end, { color: alpha(servoColors(g.p).other, 0.9), width: 1.2, dash: [5, 5] });
        });
    }
    function drawImage() {
        image.view.draw((g) => drawServoImage(g, { s: S.s, s_star: S.s_star, k, fov: S.fov }));
    }
    function drawPlots() {
        const p = palette();
        const t = S.times;
        const now = t[Math.min(k, t.length - 1)];
        decayPlot.plot.set({
            series: [
                { x: t, y: S.t_dc.map((v) => Math.hypot(...v)), color: servoColors(p).trans, width: 2 },
                { x: t, y: S.theta, color: servoColors(p).rot, width: 2, dash: [6, 4] },
            ],
            vlines: cursor(now, p),
        });
        decayPlot.setLegend([{ label: '$\\norm{{}^d\\vt_c}$ (m)', color: servoColors(p).trans }, { label: '$\\theta$ (rad)', color: servoColors(p).rot, dash: 'dashed' }]);
        velocityPlot.plot.set({
            series: V_TEX.map((_, j) => ({ x: t, y: S.v.map((v) => v[j]), color: p.series[j], width: 1.6, dash: j >= 3 ? [5, 3] : null })),
            vlines: cursor(now, p),
        });
        velocityPlot.setLegend(V_TEX.map((name, j) => ({ label: `$${name}$`, color: p.series[j], dash: j >= 3 ? 'dashed' : '' })));
        borderPlot.plot.set({
            series: [{ x: t, y: S.s.map((frame) => borderRatio(frame, S.fov)), color: servoColors(p).current, width: 2 }],
            hlines: [{ y: 1, color: p.red, dash: [5, 4] }], vlines: cursor(now, p),
        });
    }
    function drawFeatures() {
        const i = Math.min(k, S.t_dc.length - 1);
        const n = (v) => (Math.abs(v) < 5e-4 ? '0' : v.toFixed(3));
        const t = S.t_dc[i], m = S.axis[i];
        featureTex.innerHTML = tex(`{}^d\\vt_c=\\begin{bmatrix}${t.map(n).join('\\\\')}\\end{bmatrix}\\ \\text{m},\\quad `
            + `\\theta=${(S.theta[i] * 180 / Math.PI).toFixed(1)}^\\circ,\\quad \\vm=\\begin{bmatrix}${m.map(n).join('\\\\')}\\end{bmatrix}`, true);
    }
    function draw() { drawScene(); drawImage(); drawPlots(); drawFeatures(); }

    function load() {
        presets.set(S.preset);
        gain.set(S.lam);
        const [text, tone] = statusText(S.status);
        statusEl.className = `run-status ${tone}`;
        statusEl.textContent = `Result: ${text}`;
        result.set('status', text, tone);
        const worst = Math.max(...S.s.map((frame) => borderRatio(frame, S.fov)));
        result.set('border', worst <= 1 ? 'yes' : `no: up to ${(100 * (worst - 1)).toFixed(0)}% beyond`, worst <= 1 ? 'good' : 'bad');
        result.set('straight', 'straight line');
        player.load(S.s.length, S.times[1] - S.times[0] || 0.04, { at: 'start' });
        player.start();
    }

    if (options.preset && S.presets[options.preset]) S = await session.call('set', { preset: options.preset });
    load();
}
