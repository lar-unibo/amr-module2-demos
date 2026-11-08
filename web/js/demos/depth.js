// Lecture 2, demo 5 - The depth in the interaction matrix: true Z, constant Z_hat, online estimate.
import { cursor, drawServoImage, drawServoScene, IMAGE_RECT, playback, runStatus, servoColors, statusText } from '../lib/servo.js';
import { palette } from '../lib/theme.js';
import { button, card, h, label, readouts, segmented, slider } from '../lib/ui.js';
import { planeCard, plotCard, plotsGrid, view3dCard } from '../lib/widgets.js';

const MODES = [
    { value: 'true', label: 'true depths (3-D sensor)' },
    { value: 'constant', label: 'constant guess $\\hat Z$' },
    { value: 'online', label: 'online estimate' },
];

export async function mount({ workspace, session, state, options = {} }) {
    let S = state;
    let k = 0;

    const scene = view3dCard('Camera and target', { center: [0, 0, -1.7], extent: 7, yaw: -0.85, pitch: 0.38 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'desired camera', color: servoColors(p).desired, kind: 'line' },
            { label: 'current camera and its path', color: servoColors(p).current, kind: 'line' },
        ],
    });
    const image = planeCard('Image plane', { rect: IMAGE_RECT }, {
        legendItems: (p) => [
            { label: 'desired $\\vs^{*}$', color: servoColors(p).desired, kind: 'ring' },
            { label: 'current $\\vs$', color: servoColors(p).current, kind: 'dot' },
        ],
    });
    const player = playback({ onFrame: (i) => { k = i; draw(); } });
    const statusEl = h('span', { class: 'run-status' });
    const runCard = card('Run', '');
    runCard.body.append(player.el, h('div', { class: 'toolbar' }, statusEl));

    // ---- controls
    const send = session.stream('set', (next) => { S = next; load(); });
    const mode = segmented({ options: MODES, value: S.mode, onChange: (m) => send({ mode: m }) });
    const zhat = slider({ label: '$\\hat Z$ (constant, or initial value of the estimate)', min: 0.3, max: 30, value: S.Z_hat0, log: true,
        format: (v) => `${v.toFixed(2)} m`, onInput: (Z_hat) => send({ Z_hat }) });
    const quick = [1, 3, 10].map((z) => button(`$\\hat Z=${z}$`, () => send({ mode: 'constant', Z_hat: z }), { small: true }));
    const controls = card('Depth used in $\\vL_p$', 'true depth at the goal: $Z=3$ m');
    controls.body.append(mode.el, h('div', { style: 'margin-top:8px' }, zhat.el),
        h('div', { class: 'toolbar' }, h('span', { class: 'card-note' }, 'slide 33:'), ...quick));
    const result = readouts([
        { key: 'status', label: 'result' },
        { key: 'time', label: 'time to converge (true depths)' },
        { key: 'speed', label: 'largest $\\norm{\\nu_c}$ (true depths)' },
        { key: 'accuracy', label: 'final position error' },
    ]);
    controls.body.append(result.el);

    // ---- plots
    const errorPlot = plotCard('Feature error $\\norm{\\ve}$', { xLabel: 't (s)', logY: true }, { size: 'short' });
    const speedPlot = plotCard('Translation speed $\\norm{\\nu_c}$', { xLabel: 't (s)', yLabel: 'm/s' }, { size: 'short' });
    const depthPlot = plotCard('Depths: true (solid) and used in $\\vL_p$ (dashed)', { xLabel: 't (s)', yLabel: 'm' }, { size: 'short' });

    workspace.append(
        h('section', { class: 'views' }, scene.el, image.el),
        runCard.el,
        h('section', { class: 'plots' }, controls.el, errorPlot.el),
        plotsGrid(speedPlot, depthPlot));
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;

    function drawScene() {
        scene.view.draw((g) => drawServoScene(g, { points: S.points, T_od: S.T_od, runs: [{ T: S.T, positions: S.positions }], k, scale: 3 }));
    }
    function drawImage() {
        image.view.draw((g) => drawServoImage(g, { s: S.s, s_star: S.s_star, k, fov: S.fov }));
    }
    function drawPlots() {
        const p = palette();
        const c = servoColors(p);
        const t = S.times, R = S.reference;
        const now = t[Math.min(k, t.length - 1)];
        const same = S.mode === 'true';
        errorPlot.plot.set({
            series: [{ x: t, y: S.e_norm, color: c.current, width: 2 },
                ...(same ? [] : [{ x: R.times, y: R.e_norm, color: c.desired, width: 1.6, dash: [6, 4] }])],
            vlines: cursor(now, p),
        });
        errorPlot.setLegend(same ? [{ label: 'true depths', color: c.current }]
            : [{ label: 'this run', color: c.current }, { label: 'true depths', color: c.desired, dash: 'dashed' }]);
        speedPlot.plot.set({
            series: [{ x: t, y: S.nu_norm, color: c.current, width: 2 },
                ...(same ? [] : [{ x: R.times, y: R.nu_norm, color: c.desired, width: 1.6, dash: [6, 4] }])],
            vlines: cursor(now, p),
        });
        depthPlot.plot.set({
            series: [0, 1, 2, 3].flatMap((j) => [
                { x: t, y: S.Z.map((z) => z[j]), color: p.series[j], width: 1.8 },
                { x: t, y: (S.mode === 'true' ? S.Z : S.Z_hat).map((z) => z[j]), color: p.series[j], width: 1.6, dash: [6, 4] },
            ]),
            vlines: cursor(now, p),
        });
        depthPlot.setLegend([0, 1, 2, 3].map((j) => ({ label: `point ${j + 1}`, color: p.series[j] })));
    }
    function draw() { drawScene(); drawImage(); drawPlots(); }

    function load() {
        mode.set(S.mode);
        zhat.set(S.Z_hat0);
        zhat.disable(S.mode === 'true');
        const status = runStatus(S);
        const [text, tone] = statusText(status);
        statusEl.className = `run-status ${tone}`;
        statusEl.textContent = `Result: ${text}`;
        result.set('status', text, tone);
        const R = S.reference;
        const time = (run) => (run.status === 'converged' ? `${run.times[run.times.length - 1].toFixed(1)} s` : '—');
        result.set('time', `${time(S)} (${time(R)})`);
        result.set('speed', `${Math.max(...S.nu_norm).toFixed(2)} (${Math.max(...R.nu_norm).toFixed(2)}) m/s`);
        result.set('accuracy', `${(1000 * S.final_position_error).toFixed(1)} mm`, S.final_position_error < 0.005 ? 'good' : 'bad');
        player.load(S.s.length, S.times[1] - S.times[0] || 0.04, { at: 'start' });
        player.start();
    }

    if (options.mode) S = await session.call('set', { mode: options.mode, ...(options.Z_hat ? { Z_hat: Number(options.Z_hat) } : {}) });
    load();
}
