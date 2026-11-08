// Lecture 2, demo 7 - Stability of IBVS: e' = L_hat^+ e, the 8x8 and 6x6 conditions, an error the controller cannot see.
import { tex } from '../lib/math.js';
import { cursor, drawServoImage, drawServoScene, IMAGE_RECT, playback, runStatus, servoColors, statusText } from '../lib/servo.js';
import { palette } from '../lib/theme.js';
import { card, h, label, readouts, segmented, slider } from '../lib/ui.js';
import { planeCard, plotCard, plotsGrid, view3dCard } from '../lib/widgets.js';

const PRESET_ORDER = ['general', 'translation', 'rot_z_1', 'rot_z_pi', 'tilt'];
const INTERACTIONS = [
    { value: 'current', label: '$\\vL(\\vs)$' },
    { value: 'desired', label: '$\\vL(\\vs^{*})$' },
    { value: 'mean', label: 'mean' },
];

export async function mount({ workspace, session, state, options = {} }) {
    let S = state;
    let k = 0;
    let analysis = null;

    const scene = view3dCard('Camera and target', { center: [0, 0, -0.55], extent: 2.4, yaw: -0.85, pitch: 0.38 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'desired camera', color: servoColors(p).desired, kind: 'line' },
            { label: 'current camera and its path', color: servoColors(p).current, kind: 'line' },
        ],
    });
    const image = planeCard('Image plane', { rect: IMAGE_RECT }, {
        note: 'drag desired point 1',
        legendItems: (p) => [
            { label: 'desired $\\vs^{*}$', color: servoColors(p).desired, kind: 'ring' },
            { label: 'current $\\vs$', color: servoColors(p).current, kind: 'dot' },
        ],
    });
    const player = playback({ onFrame: (i) => { k = i; draw(); requestAnalysis(); } });
    const statusEl = h('span', { class: 'run-status' });
    const runCard = card('Run', '');
    runCard.body.append(player.el, h('div', { class: 'toolbar' }, statusEl));

    // ---- controls
    const send = session.stream('set', (next) => { S = next; load(); });
    const analyze = session.stream('analyze', (a) => { analysis = a; showAnalysis(); });
    const requestAnalysis = () => analyze({ k });
    const presets = segmented({ options: PRESET_ORDER.map((id) => ({ value: id, label: S.presets[id] })), value: S.preset, onChange: (preset) => send({ preset }) });
    const interaction = segmented({ options: INTERACTIONS, value: S.interaction, onChange: (v) => send({ interaction: v }) });
    const depth = segmented({ options: [{ value: 'true', label: 'true $Z$' }, { value: 'constant', label: 'constant $\\hat Z$' }], value: S.depth, onChange: (v) => send({ depth: v }) });
    const zhat = slider({ label: '$\\hat Z$', min: 0.1, max: 30, value: S.Z_hat_constant, log: true, format: (v) => `${v.toFixed(2)} m`, onInput: (Z_hat) => send({ Z_hat }) });
    const target = readouts([
        { key: 'reachable', label: 'target reachable?' },
        { key: 'best', label: 'smallest $\\norm{\\ve}$ any pose can reach' },
        { key: 'final', label: 'final $\\norm{\\ve}$ of IBVS' },
    ]);
    const controls = card('Controller and target', '');
    controls.body.append(
        h('p', { class: 'slider-group-title' }, 'start pose'), presets.el,
        h('div', { class: 'choice-row' }, h('span', {}, label('$\\Lhp$ from')), interaction.el, depth.el),
        zhat.el,
        h('div', { class: 'toolbar' }, h('button', { class: 'button small', type: 'button', onclick: () => send({ offset: [0.12, 0.06] }) }, 'Make the target unreachable'),
            h('button', { class: 'button small', type: 'button', onclick: () => send({ offset: [0, 0] }) }, 'Reset desired point 1')),
        target.el);

    // ---- analysis at time t
    const condTex = h('div', { class: 'matrix-tex' });
    const result = readouts([
        { key: 'status', label: 'result' },
        { key: 'e', label: '$\\norm{\\ve}$ at $t$' },
        { key: 'ep', label: "$\\norm{\\ve'}=\\norm{\\Lhp\\ve}$ at $t$" },
        { key: 'invisible', label: 'error outside $\\Range(\\vL)$' },
    ]);
    const conditions = card('Conditions at time $t$', 'eigenvalues of the symmetric parts');
    conditions.body.append(condTex, result.el);

    // ---- plots
    const errorPlot = plotCard("$\\norm{\\ve}$ and $\\norm{\\ve'}$", { xLabel: 't (s)', logY: true }, { size: 'short' });
    const marginPlot = plotCard('Smallest eigenvalue of $\\Sym(\\Lhp\\vL)$', { xLabel: 't (s)' }, { size: 'short', note: 'at the goal: > 0 ⇒ local stability; along the path: an instantaneous check only' });

    workspace.append(
        h('section', { class: 'views' }, scene.el, image.el),
        runCard.el,
        h('section', { class: 'plots' }, controls.el, conditions.el),
        plotsGrid(errorPlot, marginPlot));
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;
    image.view.enableDrag({
        getPoint: () => S.s_star[0],
        onDrag: ([x, y]) => send({ offset: [x - (S.s_star[0][0] - S.offset[0]), y - (S.s_star[0][1] - S.offset[1])] }),
    });

    function drawScene() {
        scene.view.draw((g) => drawServoScene(g, { points: S.points, T_od: S.T_od, runs: [{ T: S.T, positions: S.positions }], k }));
    }
    function drawImage() {
        image.view.draw((g) => {
            drawServoImage(g, { s: S.s, s_star: S.s_star, k, fov: S.fov });
            if (!S.target_reachable) {                       // where desired point 1 was, and where it is now
                const c = servoColors(g.p);
                const from = S.s_star_original[0], to = S.s_star[0];
                g.line(from, to, { color: c.desired, width: 1.2, dash: [4, 3] });
                g.point(from, { r: 4, color: g.p.surface, ring: c.desired });
                g.text(from, 'original', { dx: -18, dy: 16, color: c.desired, size: 10 });
            }
        });
    }
    function drawPlots() {
        const p = palette();
        const c = servoColors(p);
        const t = S.times;
        const now = t[Math.min(k, t.length - 1)];
        errorPlot.plot.set({
            series: [{ x: t, y: S.e_norm, color: c.current, width: 2 }, { x: t, y: S.e_proj_norm, color: c.other, width: 2, dash: [6, 4] }],
            vlines: cursor(now, p),
        });
        errorPlot.setLegend([{ label: '$\\norm{\\ve}$ (8-D)', color: c.current }, { label: "$\\norm{\\ve'}$ (6-D)", color: c.other, dash: 'dashed' }]);
        marginPlot.plot.set({
            series: [{ x: S.margin_times, y: S.margin, color: c.other, width: 2 }],
            hlines: [{ y: 0, color: p.red, dash: [5, 4] }], vlines: cursor(now, p),
        });
    }
    function showAnalysis() {
        if (!analysis) return;
        const fmtList = (values) => values.map((v) => (Math.abs(v) < 5e-4 ? '\\mathbf{0}' : v.toFixed(2))).join(',\\,');
        condTex.innerHTML = tex(`\\begin{aligned}\\Sym(\\vL\\Lhp)_{8\\times8}&:\\ ${fmtList(analysis.global)}\\\\`
            + `\\Sym(\\Lhp\\vL)_{6\\times6}&:\\ ${fmtList(analysis.local)}\\end{aligned}`, true);
        result.set('e', analysis.e_norm.toExponential(2));
        result.set('ep', analysis.e_proj_norm.toExponential(2));
        result.set('invisible', analysis.invisible.toExponential(2), analysis.invisible > 1e-3 ? 'bad' : '');
    }
    function draw() { drawScene(); drawImage(); drawPlots(); }

    function load() {
        presets.set(S.preset);
        interaction.set(S.interaction);
        depth.set(S.depth);
        zhat.set(S.Z_hat_constant);
        zhat.disable(S.depth !== 'constant');
        const finalError = S.e_norm[S.e_norm.length - 1];
        const bestFit = !S.target_reachable && ['stalled', 'running'].includes(S.status) && Math.abs(finalError - S.best_error) < 1e-3;
        const [text, tone] = bestFit ? ['best fit reached: the target is unreachable', ''] : statusText(runStatus(S));
        statusEl.className = `run-status ${tone}`;
        statusEl.textContent = `Result: ${text}`;
        result.set('status', bestFit ? 'best fit' : text, tone);
        target.set('reachable', S.target_reachable ? 'yes' : 'no: no pose sees this image', S.target_reachable ? 'good' : 'bad');
        target.set('best', S.best_error.toFixed(4));
        target.set('final', finalError.toFixed(4), bestFit || S.status === 'converged' ? 'good' : 'bad');
        player.load(S.s.length, S.times[1] - S.times[0] || 0.04, { at: 'end' });
        requestAnalysis();
    }

    if (options.unreachable !== undefined) S = await session.call('set', { offset: [0.12, 0.06] });
    load();
}
