// Lecture 2, demo 6 - PBVS vs IBVS from the same start, with calibration errors.
import { borderRatio, cursor, drawServoImage, drawServoScene, IMAGE_RECT, playback, runStatus, servoColors, statusText } from '../lib/servo.js';
import { palette } from '../lib/theme.js';
import { card, h, label, readouts, segmented, slider } from '../lib/ui.js';
import { planeCard, plotCard, plotsGrid, view3dCard } from '../lib/widgets.js';

const PRESET_ORDER = ['general', 'translation', 'rot_z_1', 'tilt'];
const method = (p) => ({ pbvs: p.gripR, ibvs: p.aqua });

export async function mount({ workspace, session, state, options = {} }) {
    let S = state;
    let k = 0;

    const scene = view3dCard('Camera paths', { center: [0, 0, -0.55], extent: 2.4, yaw: -0.85, pitch: 0.38 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'desired camera', color: servoColors(p).desired, kind: 'line' },
            { label: 'PBVS', color: method(p).pbvs, kind: 'line' },
            { label: 'PBVS: estimated pose', color: servoColors(p).estimate, kind: 'dashed' },
            { label: 'IBVS', color: method(p).ibvs, kind: 'line' },
        ],
    });
    const imagePBVS = planeCard('(a) PBVS: image', { rect: IMAGE_RECT }, { note: 'controls the camera in 3-D' });
    const imageIBVS = planeCard('(b) IBVS: image', { rect: IMAGE_RECT }, { note: 'controls the image' });
    const player = playback({ onFrame: (i) => { k = i; draw(); } });
    const runCard = card('Run', 'both start from the same pose');
    runCard.body.append(player.el);

    // ---- controls
    const send = session.stream('set', (next) => { S = next; load(); });
    const presets = segmented({ options: PRESET_ORDER.map((id) => ({ value: id, label: S.presets[id] })), value: S.preset, onChange: (preset) => send({ preset }) });
    const focal = slider({ label: 'focal length error', min: -0.3, max: 0.3, step: 0.01, value: S.focal_error,
        format: (v) => `${v >= 0 ? '+' : ''}${(100 * v).toFixed(0)}%`, onInput: (focal_error) => send({ focal_error }) });
    const center = slider({ label: 'principal point error', min: -60, max: 60, step: 1, value: S.center_error,
        format: (v) => `${v.toFixed(0)} px`, onInput: (center_error) => send({ center_error }) });
    const noise = slider({ label: 'image noise', min: 0, max: 2, step: 0.05, value: S.noise,
        format: (v) => `${v.toFixed(2)} px`, onInput: (n) => send({ noise: n }) });
    const controls = card('Start pose and calibration', 'the controllers use the assumed intrinsics $\\hat{\\mathbf K}$');
    controls.body.append(presets.el, h('div', { class: 'slider-group', style: 'margin-top:8px' }, focal.el, center.el, noise.el));
    const result = readouts([
        { key: 'pbvs', label: 'PBVS final pose error' },
        { key: 'ibvs', label: 'IBVS final pose error' },
        { key: 'pbvs_view', label: 'PBVS: points in the image' },
        { key: 'ibvs_view', label: 'IBVS: points in the image' },
    ]);
    const results = card('Result', 'error of the final camera pose w.r.t. the true goal');
    results.body.append(result.el);

    // ---- plots
    const errorPlot = plotCard('Distance of the camera from the goal', { xLabel: 't (s)', yLabel: 'm' }, { size: 'short' });
    const borderPlot = plotCard('Points relative to the image border', { xLabel: 't (s)', y: [0, 1.6] }, { size: 'short', note: 'above 1: outside the image' });

    workspace.append(
        h('section', { class: 'views' }, imagePBVS.el, imageIBVS.el),
        runCard.el,
        h('section', { class: 'views' }, scene.el, h('div', {}, controls.el, results.el)),
        plotsGrid(errorPlot, borderPlot));
    scene.view.redraw = drawScene;
    imagePBVS.view.redraw = drawImages;
    imageIBVS.view.redraw = drawImages;

    const goal = () => S.T_od.slice(0, 3).map((row) => row[3]);
    const distance = (run) => run.positions.map((q) => Math.hypot(q[0] - goal()[0], q[1] - goal()[1], q[2] - goal()[2]));

    function drawScene() {
        scene.view.draw((g) => {
            const c = method(g.p);
            drawServoScene(g, { points: S.points, T_od: S.T_od, k, runs: [
                { T: S.pbvs.T, positions: S.pbvs.positions, color: c.pbvs, estimate: S.pbvs.estimate },
                { T: S.ibvs.T, positions: S.ibvs.positions, color: c.ibvs },
            ] });
        });
    }
    function drawImages() {
        imagePBVS.view.draw((g) => drawServoImage(g, { s: S.pbvs.s, s_star: S.s_star, k, fov: S.pbvs.fov, color: method(g.p).pbvs }));
        imageIBVS.view.draw((g) => drawServoImage(g, { s: S.ibvs.s, s_star: S.s_star, k, fov: S.ibvs.fov, color: method(g.p).ibvs }));
    }
    function drawPlots() {
        const p = palette();
        const c = method(p);
        const now = k * (S.pbvs.times[1] - S.pbvs.times[0]);
        errorPlot.plot.set({
            series: [{ x: S.pbvs.times, y: distance(S.pbvs), color: c.pbvs, width: 2 }, { x: S.ibvs.times, y: distance(S.ibvs), color: c.ibvs, width: 2 }],
            vlines: cursor(now, p),
        });
        errorPlot.setLegend([{ label: 'PBVS', color: c.pbvs }, { label: 'IBVS', color: c.ibvs }]);
        borderPlot.plot.set({
            series: [{ x: S.pbvs.times, y: S.pbvs.s.map((f) => borderRatio(f, S.pbvs.fov)), color: c.pbvs, width: 2 },
                { x: S.ibvs.times, y: S.ibvs.s.map((f) => borderRatio(f, S.ibvs.fov)), color: c.ibvs, width: 2 }],
            hlines: [{ y: 1, color: p.red, dash: [5, 4] }], vlines: cursor(now, p),
        });
        borderPlot.setLegend([{ label: 'PBVS', color: c.pbvs }, { label: 'IBVS', color: c.ibvs }]);
    }
    function draw() { drawScene(); drawImages(); drawPlots(); }

    function load() {
        presets.set(S.preset);
        focal.set(S.focal_error);
        center.set(S.center_error);
        noise.set(S.noise);
        for (const name of ['pbvs', 'ibvs']) {
            const e = S.errors[name];
            const [text] = statusText(runStatus(S[name]));
            const ok = e.position < 0.005 && e.rotation < 0.5;
            result.set(name, `${(1000 * e.position).toFixed(1)} mm, ${e.rotation.toFixed(2)}°`, ok ? 'good' : 'bad');
            if (!['converged', 'settled'].includes(runStatus(S[name]))) result.set(name, text, 'bad');
            const worst = Math.max(...S[name].s.map((f) => borderRatio(f, S[name].fov)));
            result.set(`${name}_view`, worst <= 1 ? 'always' : 'leaves the image', worst <= 1 ? 'good' : 'bad');
        }
        const n = Math.max(S.pbvs.s.length, S.ibvs.s.length);
        player.load(n, S.pbvs.times[1] - S.pbvs.times[0] || 0.04, { at: 'start' });
        player.start();
    }

    if (options.preset && S.presets[options.preset]) S = await session.call('set', { preset: options.preset });
    if (options.focal_error) S = await session.call('set', { focal_error: Number(options.focal_error) });
    load();
}
