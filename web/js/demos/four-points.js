// Lecture 2, demo 3 - Why 4 points? P3P: up to four camera poses see the same image of 3 points.
import { cursor, drawServoImage, IMAGE_RECT, playback, servoColors, statusText } from '../lib/servo.js';
import { alpha, palette } from '../lib/theme.js';
import { card, h, label, readouts, segmented, slider } from '../lib/ui.js';
import { planeCard, plotCard, plotsGrid, view3dCard } from '../lib/widgets.js';

export async function mount({ workspace, session, state }) {
    let S = state;
    let k = 0;
    let which = 'three';                       // run shown in the image: 3 or 4 points

    const scene = view3dCard('Camera poses that see the same triangle', { up: 'z', center: [0, 0, 0.45], extent: 2.6, yaw: -0.55, pitch: 0.42 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'pose 1 (desired)', color: servoColors(p).desired, kind: 'line' },
            { label: 'other P3P solutions', color: p.muted, kind: 'dashed' },
            { label: 'selected solution', color: servoColors(p).current, kind: 'line' },
            { label: 'IBVS run, 3 / 4 points', color: p.gripR, kind: 'line' },
        ],
    });
    const image = planeCard('Image: desired (blue) and from the selected pose (red)', { rect: IMAGE_RECT }, {
        legendItems: (p) => [
            { label: 'seen from pose 1', color: servoColors(p).desired, kind: 'ring' },
            { label: 'seen from the selected pose / the run', color: servoColors(p).current, kind: 'dot' },
        ],
    });

    // ---- the desired pose and the solutions
    const send = session.stream('set', (next) => { S = next; load(); });
    const height = slider({ label: 'height of pose 1', min: 0.5, max: 2.5, step: 0.01, value: S.height, format: (v) => `${v.toFixed(2)} m`, onInput: (v) => send({ height: v }) });
    const dx = slider({ label: 'offset $x$', min: -0.4, max: 0.4, step: 0.01, value: S.dx, format: (v) => `${v.toFixed(2)} m`, onInput: (v) => send({ dx: v }) });
    const dy = slider({ label: 'offset $y$', min: -0.4, max: 0.4, step: 0.01, value: S.dy, format: (v) => `${v.toFixed(2)} m`, onInput: (v) => send({ dy: v }) });
    let solutionPicker = segmented({ options: [], value: null });
    const pickerSlot = h('div', {});
    const p3pReadouts = readouts([
        { key: 'count', label: 'poses that see points 1–3 identically' },
        { key: 'tri', label: 'points 1–3: image difference' },
        { key: 'four', label: 'point 4: image difference' },
    ]);
    const controls = card('Pose 1 and the P3P solutions', 'camera above the triangle, looking at its centre');
    controls.body.append(h('div', { class: 'slider-group' }, height.el, dx.el, dy.el),
        h('p', { class: 'slider-group-title' }, 'select a solution'), pickerSlot, p3pReadouts.el);

    // ---- IBVS from near the selected solution
    const player = playback({ onFrame: (i) => { k = i; draw(); } });
    const showRun = segmented({ options: [{ value: 'three', label: 'image: 3-point run' }, { value: 'four', label: 'image: 4-point run' }], value: which,
        onChange: (v) => { which = v; draw(); } });
    const runReadouts = readouts([
        { key: 'three', label: 'IBVS with 3 points ends' },
        { key: 'four', label: 'IBVS with 4 points ends' },
    ]);
    const runCard = card('IBVS started near the selected pose', 'desired image: the one seen from pose 1');
    runCard.body.append(player.el, h('div', { class: 'toolbar' }, showRun.el), runReadouts.el);

    const errorPlot = plotCard('Feature error $\\norm{\\ve}$', { xLabel: 't (s)', logY: true }, { size: 'short' });
    const distancePlot = plotCard('Distance from pose 1', { xLabel: 't (s)', yLabel: 'm' }, { size: 'short' });

    workspace.append(
        h('section', { class: 'views' }, scene.el, image.el),
        h('section', { class: 'plots' }, controls.el, runCard.el),
        plotsGrid(errorPlot, distancePlot));
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;

    const camAt = (T, x, y, z) => [0, 1, 2].map((i) => T[i][0] * x + T[i][1] * y + T[i][2] * z + T[i][3]);

    function drawScene() {
        scene.view.draw((g) => {
            const p = g.p, c = servoColors(p);
            g.polygon([[-1.1, -0.9, 0], [1.1, -0.9, 0], [1.1, 1.0, 0], [-1.1, 1.0, 0]], { fill: alpha(p.ink, 0.04), color: alpha(p.ink, 0.15) });
            const tri = S.points.slice(0, 3);
            g.polygon(tri, { fill: alpha(p.ink, 0.12), color: alpha(p.ink, 0.5), width: 1.4 });
            tri.forEach((q, i) => { g.point(q, { r: 4.5, color: p.ink, ring: null }); g.label(q, String(i + 1), { size: 11 }); });
            g.point(S.points[3], { r: 4.5, color: p.surface, ring: p.ink });
            g.label(S.points[3], '4', { size: 11 });
            S.solutions.forEach((T, j) => {
                const selected = j === S.selected;
                const color = j === 0 ? c.desired : selected ? c.current : p.muted;
                const o = camAt(T, 0, 0, 0);
                if (selected || j === 0) tri.forEach((q) => g.line(o, q, { color: alpha(color, 0.55), width: 1.1, dash: j === 0 ? null : [4, 3] }));
                g.camera(T, { color, size: 0.14, axes: false, width: selected || j === 0 ? 2 : 1.2, dash: selected || j === 0 ? null : [4, 3] });
                g.label(o, `pose ${j + 1}`, { color, size: 11, dy: -10 });
            });
            for (const [name, color] of [['three', p.gripR], ['four', p.aqua]]) {
                const run = S.runs[name];
                const i = Math.min(k, run.positions.length - 1);
                g.polyline(run.positions.slice(0, i + 1), { color, width: 2 });
                g.camera(run.T[i], { color, size: 0.12, axes: false, width: 1.6 });
            }
        });
    }
    function drawImage() {
        const run = S.runs[which];
        const i = Math.min(k, run.s4.length - 1);
        const frames = player && k > 0 ? run.s4.slice(0, i + 1) : [S.images[S.selected]];
        image.view.draw((g) => drawServoImage(g, { s: frames, s_star: S.images[0], k: frames.length - 1, fov: [0.6, 0.45], trail: k > 0 }));
    }
    function drawPlots() {
        const p = palette();
        const now = k * 0.04;
        const desired = S.solutions[0].slice(0, 3).map((row) => row[3]);
        const dist = (run) => run.positions.map((q) => Math.hypot(q[0] - desired[0], q[1] - desired[1], q[2] - desired[2]));
        errorPlot.plot.set({ series: [{ x: S.runs.three.times, y: S.runs.three.e_norm, color: p.gripR, width: 2 }, { x: S.runs.four.times, y: S.runs.four.e_norm, color: p.aqua, width: 2 }], vlines: cursor(now, p) });
        errorPlot.setLegend([{ label: '3 points', color: p.gripR }, { label: '4 points', color: p.aqua }]);
        distancePlot.plot.set({ series: [{ x: S.runs.three.times, y: dist(S.runs.three), color: p.gripR, width: 2 }, { x: S.runs.four.times, y: dist(S.runs.four), color: p.aqua, width: 2 }], vlines: cursor(now, p) });
        distancePlot.setLegend([{ label: '3 points', color: p.gripR }, { label: '4 points', color: p.aqua }]);
    }
    function draw() { drawScene(); drawImage(); drawPlots(); }

    function load() {
        height.set(S.height); dx.set(S.dx); dy.set(S.dy);
        const options = S.solutions.map((_, j) => ({ value: j, label: j === 0 ? 'pose 1 (desired)' : `pose ${j + 1}` }));
        solutionPicker = segmented({ options, value: S.selected, onChange: async (j) => { S = await session.call('select', { index: j }); load(); } });
        pickerSlot.replaceChildren(solutionPicker.el);
        p3pReadouts.set('count', String(S.solutions.length));
        p3pReadouts.set('tri', S.triangle_gap[S.selected].toExponential(0));
        p3pReadouts.set('four', S.point4_gap[S.selected].toFixed(3), S.point4_gap[S.selected] > 1e-3 ? 'bad' : 'good');
        for (const name of ['three', 'four']) {
            const run = S.runs[name];
            const [text] = statusText(run.status);
            const d = run.final_distance;
            runReadouts.set(name, run.status === 'converged' ? (d < 0.01 ? 'at pose 1 ✓' : `${d.toFixed(2)} m from pose 1, with e = 0`) : text,
                run.status === 'converged' && d < 0.01 ? 'good' : 'bad');
        }
        player.load(Math.max(S.runs.three.T.length, S.runs.four.T.length), 0.04, { at: 'start' });
        k = 0;
        draw();
    }
    load();
}
