// Lecture 3, demo 1 - Form and force closure of a planar grasp.
import { matrixTex, setTex } from '../lib/cams.js';
import { alpha, palette } from '../lib/theme.js';
import { button, card, fmt, h, label, readouts, segmented, slider, toggle } from '../lib/ui.js';
import { planeCard, view3dCard } from '../lib/widgets.js';

const RECT = { x0: -1.3, x1: 1.3, y0: -1.18, y1: 1.18 };
const FINGER_R = 0.075;
// the colours of the slide figures: brown fingers, grey object
const look = (p) => (p.dark
    ? { finger: '#b8743f', fingerEdge: '#e0a274', object: '#4a4c5c', objectEdge: '#8a8ca0' }
    : { finger: '#8b4513', fingerEdge: '#5a2c0c', object: '#c4c4cc', objectEdge: '#8e8e9a' });

export async function mount({ workspace, session, state, options }) {
    let S = state;
    if (options.preset) S = await session.call('preset', { name: options.preset });

    const scene = planeCard('Object and fingers', { rect: RECT, flipY: true }, {
        note: 'drag a finger along the boundary',
        legendItems: (p) => [
            { label: 'inward normal $n_i$', color: p.ink, kind: 'line' },
            { label: 'friction cone', color: p.aqua, kind: 'line' },
            { label: 'squeeze, contact force', color: p.accent, kind: 'line' },
            { label: 'weight $mg$', color: p.gripR, kind: 'line' },
            { label: 'free motion', color: p.red, kind: 'dashed' },
        ],
    });
    scene.canvas.style.height = 'clamp(380px, 56vh, 560px)';
    const space = view3dCard('Wrench space', { up: 'z', center: [0, 0, 0], extent: 3.4, yaw: -0.9, pitch: 0.42 }, {
        note: 'drag to orbit',
        legendItems: (p) => [
            { label: 'primitive wrenches', color: p.series[0], kind: 'dot' },
            { label: 'their convex hull', color: p.accent, kind: 'line' },
            { label: 'origin', color: p.green, kind: 'ring' },
        ],
    });
    space.canvas.style.height = 'clamp(260px, 32vh, 330px)';

    const verdict = card('Closure test', '');
    const status = h('div', { class: 'run-status' });
    const why = h('p', { class: 'equation-note' });
    const counts = readouts([
        { key: 'nc', label: 'contacts $n_c$' }, { key: 'nl', label: 'transmitted $n_l$' },
        { key: 'rank', label: '$\\mathrm{rank}\\,G$' }, { key: 'null', label: '$\\dim\\mathcal N(G)$' },
    ]);
    verdict.body.append(status, why, counts.el);

    // controls
    const send = session.stream('set', (next) => { S = next; load(); });
    const drag = session.stream('move', (next) => { S = next; load(); });
    const model = segmented({ options: [{ value: 'PwoF', label: 'frictionless (PwoF)' }, { value: 'HF', label: 'with friction (HF)' }],
        value: S.model, onChange: (v) => send({ model: v }) });
    const mu = slider({ label: 'friction coefficient $\\mu$', min: 0, max: 1.2, step: 0.01, value: S.mu,
        format: (v) => `${v.toFixed(2)}  (cone ${(Math.atan(v) * 180 / Math.PI).toFixed(1)}°)`, onInput: (v) => send({ mu: v }) });
    const shape = segmented({ options: [{ value: 'ellipse', label: 'ellipse' }, { value: 'hourglass', label: 'hourglass' }, { value: 'box', label: 'box' }],
        value: S.shape, onChange: (v) => send({ shape: v }) });
    const curvature = slider({ label: 'side curvature $k$ (hourglass)', min: -0.15, max: 0.8, step: 0.05, value: S.k,
        format: (v) => `${v.toFixed(2)}  ${Math.abs(v) < 1e-9 ? 'box' : v > 0 ? 'hourglass' : 'barrel'}`, onInput: (v) => send({ k: v }) });
    const fingers = segmented({ options: [2, 3, 4, 5, 6].map((n) => ({ value: n, label: String(n) })),
        value: S.contacts.length, onChange: (v) => send({ fingers: v }) });
    const weight = toggle({ label: 'weight $mg$ at the centre: forces that hold it', value: S.load, onChange: (v) => send({ load: v }) });
    const preset = (name) => async () => { S = await session.call('preset', { name }); load(); };
    const presets = h('div', { class: 'toolbar', style: 'padding-top:4px' },
        h('span', { class: 'card-note' }, 'slide 8:'),
        button('(a)', preset('a'), { small: true, title: 'four frictionless fingers on an ellipse' }),
        button('(b)', preset('b'), { small: true, title: 'two frictionless fingers at the waist of an hourglass' }),
        button('(c)', preset('c'), { small: true, title: 'two frictionless fingers at the tips of an ellipse' }),
        h('span', { class: 'toolbar-divider' }),
        button('pinch', preset('pinch'), { small: true, title: 'two hard fingers, antipodal and collinear' }),
        button('tilted pinch', preset('tilted'), { small: true, title: 'two hard fingers, normals not along the line between them' }),
        button('three fingers', preset('three'), { small: true, title: 'three hard fingers' }),
        h('span', { class: 'toolbar-divider' }),
        h('span', { class: 'card-note' }, 'slide 28:'),
        button('box', preset('box'), { small: true, title: 'two fingers with friction hold a box against its weight' }));
    const controls = card('Grasp', 'fingers are fixed; contacts are points');
    controls.body.append(
        h('div', { class: 'choice-row' }, h('span', {}, 'contact model'), model.el), mu.el,
        h('div', { class: 'choice-row' }, h('span', {}, 'object'), shape.el, h('span', {}, 'fingers'), fingers.el), curvature.el,
        weight.el, presets);

    const matrices = card('Grasp matrix', 'moments about the centre of the object');
    const gTex = h('div', { class: 'matrix-tex' });
    const extraTex = h('div', { class: 'matrix-tex' });
    const matrixNote = h('p', { class: 'equation-note' });
    matrices.body.append(gTex, extraTex, matrixNote);

    workspace.append(h('section', { class: 'views' }, scene.el, h('div', {}, space.el, verdict.el)),
        h('section', { class: 'plots' }, controls.el, matrices.el));
    scene.view.redraw = drawScene;
    space.view.redraw = drawSpace;
    // a finger's disk sits outside the object, touching it at the contact point
    const fingerCentre = (i) => [S.contacts[i][0] - FINGER_R * S.normals[i][0], S.contacts[i][1] - FINGER_R * S.normals[i][1]];
    scene.view.enableDragMany({
        getPoints: () => S.contacts.map((_, i) => fingerCentre(i)), radius: 20,
        onDrag: (index, [x, y]) => drag({ index, x, y }),
    });

    function drawScene() {
        scene.view.draw((g) => {
            const p = g.p, c = look(p);
            g.frame({ step: 0.25, axes: false });
            const E = S.escape, L = S.statics;
            // the free motion: the object moved along nu_B, with the fingers fixed
            if (E.kind === 'twist') {
                E.ghosts.forEach((ghost, k) => g.polyline(ghost, { color: alpha(p.red, 0.3 + 0.25 * k), width: 1.4, dash: [5, 4] }));
            }
            g.polygon(S.outline, { fill: c.object, color: c.objectEdge, width: 1.4 });
            if (E.kind !== 'wrench' && !L) {                        // frame {B} (a wrench is drawn there otherwise)
                g.arrow([0, 0], [0.22, 0], { color: alpha(p.red, 0.8), width: 1.5, head: 6 });
                g.arrow([0, 0], [0, 0.22], { color: alpha(p.aqua, 0.8), width: 1.5, head: 6 });
                g.text([0, 0], '{B}', { dx: -22, dy: 14, size: 10 });
            }
            if (S.contacts.length === 2) g.line(S.contacts[0], S.contacts[1], { color: alpha(p.ink, 0.35), width: 1, dash: [3, 4] });
            S.contacts.forEach((ci, i) => {
                const n = S.normals[i], t = S.tangents[i];
                if (S.model === 'HF') {
                    const L = 0.5, edge = (s) => { const v = [n[0] + s * S.mu * t[0], n[1] + s * S.mu * t[1]]; const k = L / Math.hypot(...v); return [ci[0] + k * v[0], ci[1] + k * v[1]]; };
                    g.polygon([ci, edge(1), edge(-1)], { fill: alpha(p.aqua, 0.18), color: alpha(p.aqua, 0.75), width: 1.2 });
                }
                // squeeze (internal force): a wide band under the normal (they coincide without friction)
                if (S.internal && !L) {
                    const f = S.internal.world[i];
                    g.arrow(ci, [ci[0] + 0.5 * f[0], ci[1] + 0.5 * f[1]], { color: alpha(p.accent, 0.45), width: 7, head: 13 });
                }
                g.arrow(ci, [ci[0] + 0.3 * n[0], ci[1] + 0.3 * n[1]], { color: p.ink, width: 1.5, head: 7 });
            });
            if (E.kind === 'wrench') drawWrench(g, E.wrench);
            if (L) drawLoad(g, L);
            S.contacts.forEach((_, i) => {
                const q = fingerCentre(i);
                const inside = E.kind === 'twist' && E.ghost_fingers_in[i];
                g.point(q, { r: FINGER_R * g.view.k, color: c.finger, ring: inside ? p.red : c.fingerEdge });
                g.text(q, String(i + 1), { size: 10, align: 'center', dy: 3.5, color: '#ffffff' });
            });
        });
    }

    // slide 28: the weight at the centre (orange) and the contact forces that hold it (blue):
    // the squeeze (wide), then -G^# w (dashed) from its tip, ending at the total force (solid)
    function drawLoad(g, L) {
        const p = g.p;
        const len = (v) => Math.hypot(v[0], v[1]);
        const forces = [L.total, L.carry, L.squeeze].filter(Boolean).flat();
        // longest arrow: under half the distance between two fingers, so opposite forces do not cross
        let gap = Infinity;
        S.contacts.forEach((a, i) => S.contacts.forEach((b, j) => { if (j > i) gap = Math.min(gap, Math.hypot(a[0] - b[0], a[1] - b[1])); }));
        const k = Math.min(0.5, 0.45 * gap) / Math.max(1, ...forces.map(len));
        const at = (q, v) => [q[0] + k * v[0], q[1] + k * v[1]];
        g.arrow([0, 0], [0, -k], { color: p.gripR, width: 3, head: 10 });
        g.text([0, -k], 'mg', { dx: 7, dy: 2, size: 12, color: p.gripR });
        if (!L.feasible) return;
        S.contacts.forEach((ci, i) => {
            if (L.squeeze) {
                const tip = at(ci, L.squeeze[i]);
                if (k * len(L.squeeze[i]) > 0.01) g.arrow(ci, tip, { color: alpha(p.accent, 0.45), width: 7, head: 13 });
                if (k * len(L.carry[i]) > 0.01) g.arrow(tip, at(tip, L.carry[i]), { color: p.accent, width: 1.5, head: 7, dash: [4, 3] });
            }
            if (k * len(L.total[i]) > 0.01) g.arrow(ci, at(ci, L.total[i]), { color: p.accent, width: 2.5, head: 9 });
        });
    }

    // an external wrench w = (f, m) applied at the centre: an arrow for f, an arc for m
    function drawWrench(g, w) {
        const p = g.p;
        const f = Math.hypot(w[0], w[1]);
        const k = 0.55 / Math.max(f, Math.abs(w[2]) / S.rho, 1e-9);
        if (f * k > 0.04) g.arrow([0, 0], [k * w[0], k * w[1]], { color: p.red, width: 3, head: 10 });
        const m = (w[2] / S.rho) * k;                              // signed, in the units of the arrow
        if (Math.abs(m) > 0.04) {
            const r = 0.3, sweep = Math.sign(m) * Math.min(Math.abs(m) / 0.55, 1) * 1.6 * Math.PI;
            const arc = Array.from({ length: 41 }, (_, i) => { const a = -Math.PI / 2 + sweep * i / 40; return [r * Math.cos(a), r * Math.sin(a)]; });
            g.polyline(arc, { color: p.red, width: 2.5 });
            const a1 = -Math.PI / 2 + sweep, a0 = a1 - Math.sign(m) * 0.25;
            g.arrow([r * Math.cos(a0), r * Math.sin(a0)], [r * Math.cos(a1), r * Math.sin(a1)], { color: p.red, width: 2.5, head: 9 });
        }
        g.text([0, 0], 'w', { dx: 8, dy: 22, size: 12, color: p.red });
    }

    function drawSpace() {
        space.view.draw((g) => {
            const p = g.p;
            const A = 1.5;
            g.arrow([-A, 0, 0], [A, 0, 0], { color: alpha(p.ink, 0.45), width: 1, head: 6 });
            g.arrow([0, -A, 0], [0, A, 0], { color: alpha(p.ink, 0.45), width: 1, head: 6 });
            g.arrow([0, 0, -A], [0, 0, A], { color: alpha(p.ink, 0.45), width: 1, head: 6 });
            g.label([A, 0, 0], 'f_x', { size: 11, color: p.muted });
            g.label([0, A, 0], 'f_y', { size: 11, color: p.muted });
            g.label([0, 0, A], 'm/ρ', { size: 11, color: p.muted });
            const W = S.wrenches;
            const depth = (face) => face.reduce((s, i) => s + (g.view.project(W[i])?.[2] ?? 0), 0) / face.length;
            const faces = [...S.hull.faces].sort((a, b) => depth(b) - depth(a));
            const tone = S.closed ? p.accent : p.red;
            for (const face of faces) {
                const pts = face.map((i) => W[i]);
                if (pts.length >= 3) g.polygon(pts, { fill: alpha(tone, 0.13), color: alpha(tone, 0.55), width: 1 });
                else g.line(pts[0], pts[pts.length - 1], { color: alpha(tone, 0.7), width: 2 });
            }
            W.forEach((w, k) => {
                g.line([0, 0, 0], w, { color: alpha(p.series[S.owner[k] % 6], 0.35), width: 1 });
                g.point(w, { r: 4.5, color: p.series[S.owner[k] % 6], ring: p.surface });
                // finger number (once per finger: on its first cone edge)
                if (k === 0 || S.owner[k] !== S.owner[k - 1]) g.label(w, String(S.owner[k] + 1), { size: 10, color: p.inkSoft });
            });
            g.point([0, 0, 0], { r: 5, color: S.closed ? p.green : p.red, ring: p.surface });
        });
    }

    const deg = (v) => `${v.toFixed(1)}°`;
    const vec = (v, digits = 2) => `\\begin{bmatrix} ${v.map((x) => fmtTex(x, digits)).join(' & ')} \\end{bmatrix}`;
    const fmtTex = (x, digits) => (Math.abs(x) < 0.5 * 10 ** -digits ? '0' : x.toFixed(digits));

    function load() {
        model.set(S.model); mu.set(S.mu); mu.disable(S.model !== 'HF'); shape.set(S.shape);
        curvature.set(S.k); curvature.disable(S.shape !== 'hourglass'); fingers.set(S.contacts.length); weight.set(S.load);
        const test = S.model === 'PwoF' ? 'form closure (first order)' : 'force closure';
        status.className = `run-status ${S.closed ? 'good' : 'bad'}`;
        status.textContent = S.closed ? `✓ ${test}` : `✗ no ${test}`;
        verdict.note.replaceChildren(label(S.model === 'PwoF' ? 'slide 29: $G^T\\nu_B\\geq 0\\Rightarrow\\nu_B=0$'
            : 'slide 30: $\\forall w\\;\\exists\\lambda\\in\\mathcal F: G\\lambda=-w$'));
        counts.set('nc', String(S.contacts.length));
        counts.set('nl', String(S.n_l));
        counts.set('rank', String(S.rank_G), S.rank_G === 3 ? 'good' : 'bad');
        counts.set('null', String(S.nullity));
        why.replaceChildren(label(explain()));
        setTex(gTex, matrixTex('G', S.G, 2));
        const E = S.escape, L = S.statics;
        matrices.note.replaceChildren(label(L ? 'slide 28: $w+G\\lambda=0$, weight $w=[0,\\,-mg,\\,0]^T$' : 'moments about the centre of the object'));
        if (L && L.feasible) {
            setTex(extraTex, L.carry
                ? `\\begin{aligned} -G^{\\#}w &= ${vec(L.lambda_carry)}^T \\\\ \\text{squeeze} &= ${vec(L.lambda_squeeze)}^T \\\\ \\lambda &= ${vec(L.lambda)}^T \\end{aligned}`
                : `\\lambda = ${vec(L.lambda)}^T,\\quad w + G\\lambda = 0`);
            matrixNote.replaceChildren(label(statics(L)));
        } else if (L) {
            setTex(extraTex, '');
            matrixNote.replaceChildren(label(statics(L)));
        } else if (S.internal) {
            setTex(extraTex, `\\lambda_{\\text{int}} = ${vec(S.internal.lambda)}^T,\\quad G\\lambda_{\\text{int}} = 0`);
            matrixNote.textContent = S.model === 'PwoF'
                ? 'A squeeze (internal force): positive normal forces with no net wrench on the object (largest = 1).'
                : 'A squeeze (internal force) strictly inside the friction cones (blue; largest = 1).';
        } else if (E.kind === 'twist') {
            setTex(extraTex, `\\nu_B = ${vec(E.twist)}^T,\\quad G^T\\nu_B = ${vec(E.normal_speeds)}^T`);
            matrixNote.textContent = 'A free motion: normal velocities at the contacts ≥ 0, so no finger is penetrated (first order).';
        } else if (E.kind === 'wrench') {
            setTex(extraTex, `w = ${vec(E.wrench)}^T`);
            matrixNote.textContent = 'No contact forces inside the friction cones can balance this external wrench (red, at the centre).';
        }
        drawScene(); drawSpace();
    }

    // slide 28, in words (forces in units of mg)
    function statics(L) {
        const list = (flags) => flags.map((v, i) => (v ? null : i + 1)).filter(Boolean);
        if (!L.feasible) {
            if (S.escape.second_order === 'held') {
                return 'No contact forces balance the weight in this exact configuration. The curvature still holds the object: it sinks slightly, which takes a little deformation, until the normals can carry the weight.';
            }
            return `No contact forces inside the cones balance the weight: these fingers cannot hold it${S.model === 'HF' && S.mu === 0 ? ' without friction' : ''}.`;
        }
        if (!L.closed) {
            return `Not closed, yet this weight alone can be balanced (solid arrows; total normal force ${fmt(L.grip, 2)} $mg$). A wrench in another direction could not be.`;
        }
        const out = list(L.carry_inside);
        let text = '$-G^{\\#}w$ (dashed) carries the weight with the smallest forces' +
            (out.length === 0 ? ', already inside the cones.'
                : S.model === 'HF' ? `, but outside the friction cone at finger ${out.join(', ')}.` : `, but it pulls at finger ${out.join(', ')}.`);
        if (L.gamma !== null) {
            const slide = S.model === 'HF' && Math.abs(L.gamma - 1 / (2 * S.mu)) < 1e-6 * Math.max(1, L.gamma);
            text += ` The squeeze (wide) adds normal force until every contact force (solid) is in its cone: $\\gamma = ${L.gamma.toFixed(2)}\\,mg$` +
                (slide ? ' $=\\frac{mg}{2\\mu}$ (slide 28).' : ', the largest normal force of the squeeze.');
        } else {
            text += ` Of all the squeezes in $\\mathcal N(G)$ (dimension ${S.nullity}), the one shown brings every contact force (solid) into its cone with the smallest total normal force, ${fmt(L.grip, 2)} $mg$.`;
        }
        return text;
    }

    function explain() {
        const E = S.escape;
        const nc = S.contacts.length;
        let text = '';
        if (S.closed) {
            text = S.model === 'PwoF'
                ? `The normal wrenches positively span the wrench space: the origin is inside their hull (margin ${fmt(S.hull.margin, 2)}). No motion is possible without pushing into a finger.`
                : `The friction-cone edges positively span the wrench space (margin ${fmt(S.hull.margin, 2)}): squeezing as needed, the fingers can balance any external wrench.`;
        } else if (E.kind === 'twist') {
            if (E.second_order === 'held') {
                text = `Every first-order free motion is tangential at all contacts ($G^T\\nu_B=0$). On the true shape each of them pushes into a finger, and no small extra shift avoids it (drawn: the motion closest to escaping): the curvature holds the object, as in grasp (b).`;
            } else if (E.second_order === 'escapes') {
                const shifted = E.correction.some((x) => Math.abs(x) > 1e-6);
                text = `Every first-order free motion is tangential at all contacts ($G^T\\nu_B=0$), and on the true shape the object ${E.clearance.every((x) => Math.abs(x) < 2e-3) ? 'slides' : 'escapes'} (dashed)` +
                    (shifted ? ', with a small extra shift that uses the room it gains at another finger.' : '.');
            } else {
                const lost = E.normal_speeds.map((v, i) => (v > 1e-6 ? i + 1 : null)).filter(Boolean);
                const pushed = E.ghost_fingers_in.map((v, i) => (v ? i + 1 : null)).filter(Boolean);
                text = `The object can move (dashed) leaving ${lost.length === 1 ? 'finger' : 'fingers'} ${lost.join(', ')}` +
                    (pushed.length ? `; on the true shape it pushes into finger ${pushed.join(', ')}, so the curvature may still hold it.` : '.');
                if (nc < 4) text += ` First order needs at least 4 contacts in the plane.`;
            }
        } else {
            text = S.hull.rank < 3 ? 'The contact wrenches span only a plane: the wrenches outside it cannot be balanced.'
                : 'The origin is outside the hull of the cone edges: the external wrench drawn in red cannot be balanced.';
        }
        if (S.angles && S.model === 'HF') {
            const half = S.cone_half_angle;
            const ok = S.angles.every((a) => a < half - 1e-9);
            text += ` Line between the fingers vs the normals: ${deg(S.angles[0])}, ${deg(S.angles[1])}; cone half-angle $\\arctan\\mu$ = ${deg(half)}${ok ? ': inside both cones.' : ': outside.'}`;
        }
        return text;
    }

    load();
}
