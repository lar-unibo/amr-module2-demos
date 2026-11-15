// Lecture 3, demo 2 - Point-cloud registration with known correspondences (closed form, SVD).
import { matrixTex, setTex } from '../lib/cams.js';
import { alpha } from '../lib/theme.js';
import { button, card, fmt, h, readouts, segmented, slider, toggle } from '../lib/ui.js';
import { view3dCard } from '../lib/widgets.js';

const IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
const apply = (R, t, q) => [0, 1, 2].map((i) => R[i][0] * q[0] + R[i][1] * q[1] + R[i][2] * q[2] + t[i]);
const homogeneous = (R, t) => [[...R[0], t[0]], [...R[1], t[1]], [...R[2], t[2]], [0, 0, 0, 1]];

export async function mount({ workspace, session, state, options }) {
    let S = state;
    if (options.preset) S = await session.call('preset', { name: options.preset });

    const scene = view3dCard('Model and scene points', { up: 'z', center: [0.13, 0.03, 0.07], extent: 0.4, yaw: -0.5, pitch: 0.5 }, {
        note: 'drag to orbit · wheel to zoom',
        legendItems: (p) => [
            { label: 'model $m_i$ (object frame)', color: p.red, kind: 'dot' },
            { label: 'scene $s_i$', color: p.rod, kind: 'dot' },
            { label: 'pairs (wrong ones orange)', color: p.muted, kind: 'dashed' },
            { label: 'aligned model $R^*m_i+t^*$', color: p.red, kind: 'ring' },
        ],
    });
    scene.canvas.style.height = 'clamp(380px, 56vh, 560px)';

    // the closed form, step by step
    const steps = card('Closed-form solution', 'slide 44');
    const tex = Array.from({ length: 5 }, () => h('div', { class: 'matrix-tex', style: 'font-size:0.82rem' }));
    const stepTitle = (n, text) => h('p', { class: 'slider-group-title' }, `${n}. ${text}`);
    const status = h('div', { class: 'run-status' });
    const result = readouts([
        { key: 'rot', label: 'rotation error' }, { key: 'trans', label: 'translation error' },
        { key: 'rms', label: 'RMS residual' }, { key: 'det', label: '$\\det(UV^T)$' },
    ]);
    steps.body.append(
        stepTitle(1, 'centroids'), tex[0], stepTitle(2, 'cross-covariance'), tex[1],
        stepTitle(3, 'SVD'), tex[2], stepTitle(4, 'rotation'), tex[3], stepTitle(5, 'translation'), tex[4],
        status, result.el);

    // controls
    const send = session.stream('set', (next) => { S = next; load(); });
    const sl = (key, text, min, max, step, format) => slider({ label: text, min, max, step, value: S[key], format, onInput: (v) => send({ [key]: v }) });
    const object = segmented({ options: [{ value: 'bracket', label: 'bracket' }, { value: 'plate', label: 'flat plate (2 mm)' }],
        value: S.object, onChange: (v) => send({ object: v }) });
    const n = sl('n', 'pairs $N$', 3, 120, 1, (v) => String(Math.round(v)));
    const noise = sl('noise', 'noise on $s_i$ (σ)', 0, 20, 0.5, (v) => `${v.toFixed(1)} mm`);
    const wrong = sl('wrong', 'wrong pairs', 0, 60, 1, (v) => String(Math.round(v)));
    const yaw = sl('yaw', 'true rotation about $z$', -180, 180, 1, (v) => `${v.toFixed(0)}°`);
    const tilt = sl('tilt', 'true rotation about $x$', -90, 90, 1, (v) => `${v.toFixed(0)}°`);
    const tx = sl('tx', 'true translation $x$', 0, 0.4, 0.005, (v) => `${(100 * v).toFixed(1)} cm`);
    const tz = sl('tz', 'true translation $z$', -0.1, 0.25, 0.005, (v) => `${(100 * v).toFixed(1)} cm`);
    const correct = toggle({ label: 'correction $D$, so that $\\det R^*=+1$', value: S.correct, onChange: (v) => send({ correct: v }) });
    const preset = (name) => async () => { S = await session.call('preset', { name }); load(); };
    const controls = card('Points and true pose', '$s_i = T_{obj}\\,m_i$ + noise');
    controls.body.append(
        h('div', { class: 'choice-row' }, h('span', {}, 'object'), object.el),
        h('div', { class: 'slider-group' }, n.el, noise.el, wrong.el),
        h('p', { class: 'slider-group-title' }, 'true pose T_obj (unknown to the solver)'),
        h('div', { class: 'slider-group' }, yaw.el, tilt.el, tx.el, tz.el),
        h('div', { style: 'margin-top:8px' }, correct.el),
        h('div', { class: 'toolbar' },
            button('default', preset('default'), { small: true }),
            button('3 pairs', preset('three'), { small: true, title: 'three exact pairs: the pose is determined' }),
            button('noisy', preset('noisy'), { small: true }),
            button('wrong pairs', preset('wrong'), { small: true }),
            button('mirror', preset('mirror'), { small: true, title: 'flat plate, noise, and no correction D' }),
            h('span', { class: 'toolbar-divider' }),
            button('new noise', async () => { S = await session.call('resample'); load(); }, { small: true, title: 'draw new noise and new wrong pairs' })));

    workspace.append(h('section', { class: 'views' }, scene.el, steps.el), h('section', { class: 'plots' }, controls.el));
    scene.view.redraw = drawScene;

    function drawScene() {
        scene.view.draw((g) => {
            const p = g.p;
            const R = S.R, t = S.t;
            // the object: its edges in the object frame and at the estimate
            for (const [a, b] of S.edges) {
                g.line(a, b, { color: alpha(p.red, 0.22), width: 1 });
                g.line(apply(R, t, a), apply(R, t, b), { color: alpha(p.red, 0.45), width: 1.2, dash: [4, 3] });
            }
            g.frame(IDENTITY, { size: 0.05, label: 'object frame' });
            g.frame(homogeneous(R, t), { size: 0.05, label: S.is_rotation ? 'R*, t*' : 'R, t (mirrored)', color: S.is_rotation ? p.inkSoft : p.red });
            S.m.forEach((m, i) => {
                const wrong = S.wrong_mask[i];
                g.line(m, S.s[i], { color: wrong ? alpha(p.gripR, 0.85) : alpha(p.muted, 0.35), width: wrong ? 1.5 : 1, dash: [3, 4] });
            });
            S.m.forEach((m) => g.point(m, { r: 3.2, color: p.red, ring: null }));
            S.s.forEach((s) => g.point(s, { r: 3.4, color: p.rod, ring: null }));
            S.aligned.forEach((q) => g.point(q, { r: 5, color: 'rgba(0,0,0,0)', ring: p.red }));
            g.point(S.m_bar, { r: 6, color: p.surface, ring: p.red });
            g.label(S.m_bar, 'm̄', { color: p.red, size: 13 });
            g.point(S.s_bar, { r: 6, color: p.surface, ring: p.rod });
            g.label(S.s_bar, 's̄', { color: p.rod, size: 13 });
        });
    }

    const vec = (v, digits = 3) => `\\begin{bmatrix} ${v.map((x) => (Math.abs(x) < 0.5 * 10 ** -digits ? '0' : x.toFixed(digits))).join(' \\\\ ')} \\end{bmatrix}`;
    function load() {
        object.set(S.object); n.set(S.n); noise.set(S.noise); wrong.set(S.wrong);
        yaw.set(S.yaw); tilt.set(S.tilt); tx.set(S.tx); tz.set(S.tz); correct.set(S.correct);
        setTex(tex[0], `\\bar m = ${vec(S.m_bar)},\\quad \\bar s = ${vec(S.s_bar)}\\ \\text{m}`);
        setTex(tex[1], `${matrixTex('M = \\textstyle\\sum_i \\tilde s_i\\tilde m_i^T', S.M, 4)}\\ \\text{m}^2`);
        const sig = S.sigma.map((x) => x.toExponential(2).replace(/e([+-]\d+)/, '\\!\\times\\!10^{$1}').replace('+', ''));
        setTex(tex[2], `\\begin{gathered} ${matrixTex('U', S.U, 2)},\\quad ${matrixTex('V^T', S.Vt, 2)} \\\\ \\Sigma = \\mathrm{diag}(${sig.join(',\\ ')}) \\end{gathered}`);
        const d = S.D[2][2];
        setTex(tex[3], `\\begin{gathered} \\det(UV^T) = ${S.det_UVt > 0 ? '+1' : '-1'},\\quad D = ${S.correct ? '' : '(\\text{off})\\ '}\\mathrm{diag}(1, 1, ${d > 0 ? '1' : '-1'}) \\\\ ${matrixTex(S.correct ? 'R^* = UDV^T' : 'R = UV^T', S.R, 3)} \\end{gathered}`);
        setTex(tex[4], `${S.correct ? 't^* = \\bar s - R^*\\bar m' : 't = \\bar s - R\\bar m'} = ${vec(S.t)}\\ \\text{m}`);
        if (S.is_rotation) {
            status.className = 'run-status good';
            status.textContent = S.correct && S.det_UVt < 0 ? '✓ D flipped the smallest singular value: a rotation, det R* = +1' : '✓ a rotation: det R* = +1';
        } else {
            status.className = 'run-status bad';
            status.textContent = '✗ R = UVᵀ is a reflection (det R = −1): the model is mirrored';
        }
        result.set('rot', S.rot_err === null ? 'not a rotation' : `${S.rot_err.toFixed(2)}°`, S.rot_err === null ? 'bad' : '');
        result.set('trans', `${S.trans_err.toFixed(1)} mm`);
        result.set('rms', `${S.rms.toFixed(2)} mm`);
        result.set('det', S.det_UVt > 0 ? '+1' : '−1', S.det_UVt > 0 ? '' : 'bad');
        steps.note.textContent = S.det_UVt < 0
            ? `slide 44 · with D the cost is ${fmt(4e6 * S.sigma[2], 1)} mm² higher (4σ₃): ${S.correct ? 'RMS' : 'RMS with D'} ${(S.correct ? S.rms : S.rms_other).toFixed(2)} vs ${(S.correct ? S.rms_other : S.rms).toFixed(2)} mm`
            : 'slide 44';
        drawScene();
    }
    load();
}
