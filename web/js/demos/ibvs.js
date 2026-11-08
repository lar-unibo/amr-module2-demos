// Lecture 2, demo 4 - IBVS control law and its issues: v_c = -lambda L_hat^+ (s - s*).
import { cursor, drawServoImage, drawServoScene, IMAGE_RECT, playback, servoColors, statusText } from '../lib/servo.js';
import { palette } from '../lib/theme.js';
import { card, h, label, readouts, segmented, slider, fmt } from '../lib/ui.js';
import { planeCard, plotCard, plotsGrid, view3dCard } from '../lib/widgets.js';

const PRESET_ORDER = ['general', 'translation', 'rot_z_1', 'rot_z_2.8', 'rot_z_pi', 'tilt'];
const INTERACTIONS = [
    { value: 'current', label: '$\\vL(\\vs)$ current' },
    { value: 'desired', label: '$\\vL(\\vs^{*})$ desired' },
    { value: 'mean', label: 'mean $\\tfrac12(\\vL+\\vL^{*})$' },
];
const V_TEX = ['\\nu_x', '\\nu_y', '\\nu_z', '\\omega_x', '\\omega_y', '\\omega_z'];

export async function mount({ workspace, session, state, options = {} }) {
    let S = state;
    let k = 0;

    const scene = view3dCard('Camera and target', { center: [0, 0, -0.55], extent: 2.3, yaw: -0.85, pitch: 0.38 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'desired camera', color: servoColors(p).desired, kind: 'line' },
            { label: 'current camera and its path', color: servoColors(p).current, kind: 'line' },
        ],
    });
    const image = planeCard('Image plane', { rect: IMAGE_RECT }, {
        legendItems: (p) => [
            { label: 'desired $\\vs^{*}$', color: servoColors(p).desired, kind: 'ring' },
            { label: 'current $\\vs$ and image paths', color: servoColors(p).current, kind: 'dot' },
        ],
    });
    const player = playback({ onFrame: (i) => { k = i; draw(); } });
    const statusEl = h('span', { class: 'run-status' });
    const runCard = card('Run', '');
    runCard.body.append(player.el, h('div', { class: 'toolbar' }, statusEl));

    // ---- controls
    const send = session.stream('set', (next) => { S = next; load(); });
    const presets = segmented({
        options: PRESET_ORDER.map((id) => ({ value: id, label: S.presets[id] })),
        value: S.preset, onChange: (preset) => send({ preset }),
    });
    const interaction = segmented({ options: INTERACTIONS, value: S.interaction, onChange: (v) => send({ interaction: v }) });
    const gain = slider({ label: 'gain $\\lambda$', min: 0.1, max: 2.0, step: 0.05, value: S.lam, format: (v) => v.toFixed(2),
        onInput: (lam) => send({ lam }) });
    const controls = card('Start pose and controller', '$\\vv_c=-\\lambda\\,\\Lhp(\\vs-\\vs^{*})$');
    controls.body.append(
        h('p', { class: 'slider-group-title' }, 'start pose (relative to the desired camera)'), presets.el,
        h('p', { class: 'slider-group-title' }, label('interaction matrix used in $\\Lhp$')), interaction.el,
        h('div', { style: 'margin-top:8px' }, gain.el));
    const result = readouts([
        { key: 'status', label: 'result' },
        { key: 'time', label: 'time to converge' },
        { key: 'retreat', label: 'largest camera retreat' },
        { key: 'error', label: 'final $\\norm{\\ve}$' },
    ]);
    controls.body.append(result.el);

    // ---- plots
    const errorPlot = plotCard('Feature error $\\norm{\\ve}$', { xLabel: 't (s)', logY: true }, { size: 'short' });
    const velocityPlot = plotCard('Camera velocity $\\vv_c$', { xLabel: 't (s)' }, { size: 'short' });
    const depthPlot = plotCard('Camera position along the optical axis', { xLabel: 't (s)', yLabel: 'z in F_d (m)' },
        { size: 'short', note: 'negative: backward, away from the target' });

    workspace.append(
        h('section', { class: 'views' }, scene.el, image.el),
        runCard.el,
        h('section', { class: 'plots' }, controls.el, errorPlot.el),
        plotsGrid(velocityPlot, depthPlot));
    scene.view.redraw = drawScene;
    image.view.redraw = drawImage;

    function drawScene() {
        scene.view.draw((g) => drawServoScene(g, { points: S.points, T_od: S.T_od, runs: [{ T: S.T, positions: S.positions }], k }));
    }
    function drawImage() {
        image.view.draw((g) => drawServoImage(g, { s: S.s, s_star: S.s_star, k, fov: S.fov }));
    }
    function drawPlots() {
        const p = palette();
        const t = S.times;
        const now = t[Math.min(k, t.length - 1)];
        errorPlot.plot.set({ series: [{ x: t, y: S.e_norm, color: servoColors(p).current, width: 2 }], vlines: cursor(now, p) });
        velocityPlot.plot.set({
            series: V_TEX.map((_, j) => ({ x: t, y: S.v.map((v) => v[j]), color: p.series[j], width: 1.6, dash: j >= 3 ? [5, 3] : null })),
            vlines: cursor(now, p),
        });
        velocityPlot.setLegend(V_TEX.map((name, j) => ({ label: `$${name}$`, color: p.series[j], dash: j >= 3 ? 'dashed' : '' })));
        depthPlot.plot.set({
            series: [{ x: t, y: S.camera_in_desired.map((q) => q[2]), color: servoColors(p).current, width: 2 }],
            hlines: [{ y: 0 }], vlines: cursor(now, p),
        });
    }
    function draw() { drawScene(); drawImage(); drawPlots(); }

    function load() {
        presets.set(S.preset);
        interaction.set(S.interaction);
        gain.set(S.lam);
        const [text, tone] = statusText(S.status);
        statusEl.className = `run-status ${tone}`;
        statusEl.textContent = `Result: ${text}`;
        result.set('status', text, tone);
        result.set('time', S.status === 'converged' ? `${S.times[S.times.length - 1].toFixed(1)} s` : '—');
        const zmin = Math.min(...S.camera_in_desired.map((q) => q[2]));
        result.set('retreat', zmin < -1e-3 ? `${(-zmin).toFixed(2)} m` : 'none');
        result.set('error', fmt(S.e_norm[S.e_norm.length - 1], 4));
        player.load(S.s.length, S.times[1] - S.times[0] || 0.04, { at: 'start' });
        player.start();
    }

    if (options.preset && S.presets[options.preset]) S = await session.call('set', { preset: options.preset });
    if (options.interaction) S = await session.call('set', { interaction: options.interaction });
    load();
}
