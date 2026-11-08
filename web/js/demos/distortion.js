// Lecture 1, demo 3 - Lens distortion: radial (k1, k2, k3) and tangential (p1, p2).
import { setTex } from '../lib/cams.js';
import { alpha, palette } from '../lib/theme.js';
import { card, h, readouts, segmented, slider, toggle } from '../lib/ui.js';
import { planeCard } from '../lib/widgets.js';

const NAMES = ['k_1', 'k_2', 'k_3', 'p_1', 'p_2'];
const LIMITS = [0.5, 0.3, 0.1, 0.03, 0.03];
const STEPS = [0.005, 0.005, 0.001, 0.0005, 0.0005];

export async function mount({ workspace, session, state }) {
    let S = state;
    let showCorrected = false, showArrows = true;

    const image = planeCard('Image (640 × 480 pixels)', { rect: { x0: -10, x1: 650, y0: -10, y1: 490 } }, {
        note: 'u to the right, v down',
        legendItems: (p) => [
            { label: 'ideal grid (no distortion)', color: p.muted, kind: 'line' },
            { label: 'distorted grid', color: p.accent, kind: 'line' },
            { label: 'displacement', color: p.gripR, kind: 'line' },
            { label: 'corrected grid', color: p.aqua, kind: 'dashed' },
        ],
    });
    const send = session.stream('set', (next) => { S = next; load(); });
    const presets = segmented({ options: S.presets.map((n) => ({ value: n, label: n })), value: S.preset,
        onChange: async (name) => { S = await session.call('preset', { name }); load(); } });
    const sliders = NAMES.map((name, j) => slider({ label: `$${name}$`, min: -LIMITS[j], max: LIMITS[j], step: STEPS[j], value: S.D[j],
        format: (v) => (j >= 3 ? v.toFixed(4) : v.toFixed(3)), onInput: () => { presets.set(null); send({ D: sliders.map((s) => s.get()) }); } }));
    const corrected = toggle({ label: 'show the corrected grid (inverse model)', value: false, onChange: (v) => { showCorrected = v; draw(); } });
    const arrows = toggle({ label: 'show the displacement field', value: true, onChange: (v) => { showArrows = v; draw(); } });
    const controls = card('Distortion parameters $D=(k_1,k_2,k_3,p_1,p_2)$', 'applied to normalized coordinates');
    controls.body.append(h('div', { class: 'toolbar', style: 'padding-top:0' }, presets.el),
        h('p', { class: 'slider-group-title' }, 'radial'), h('div', { class: 'slider-group' }, sliders.slice(0, 3).map((s) => s.el)),
        h('p', { class: 'slider-group-title' }, 'tangential'), h('div', { class: 'slider-group' }, sliders.slice(3).map((s) => s.el)),
        h('div', { style: 'margin-top:8px' }, arrows.el, corrected.el));
    const formula = h('div', { class: 'matrix-tex' });
    const result = readouts([
        { key: 'corner', label: 'shift of the image corner' },
        { key: 'kind', label: 'radial distortion' },
        { key: 'correction', label: 'error after correction' },
    ]);
    const model = card('The model with these values', '$(x, y)$: normalized coordinates, $r^2=x^2+y^2$');
    model.body.append(formula, result.el);

    workspace.append(image.el, h('section', { class: 'plots' }, controls.el, model.el));
    image.view.redraw = draw;

    function draw() {
        image.view.draw((g) => {
            const p = g.p;
            g.frame({ step: 40, axes: false });
            g.polyline([[0, 0], [S.W, 0], [S.W, S.H], [0, S.H], [0, 0]], { color: p.lineStrong, width: 1.6 });
            for (const L of S.ideal_lines) g.polyline(L, { color: alpha(p.muted, 0.45), width: 1 });
            for (const L of S.distorted_lines) g.polyline(L, { color: p.accent, width: 1.6 });
            if (showArrows) S.arrows_from.forEach((a, i) => g.arrow(a, S.arrows_to[i], { color: p.gripR, width: 1.6, head: 7 }));
            if (showCorrected) for (const L of S.corrected_lines) g.polyline(L, { color: p.aqua, width: 1.6, dash: [5, 4] });
            g.point([S.u0, S.v0], { r: 4, color: p.ink, ring: null });
            g.text([S.u0, S.v0], 'principal point', { dx: 8, dy: -6 });
        });
    }

    function load() {
        S.D.forEach((v, j) => sliders[j].set(v));
        if (S.preset) presets.set(S.preset);
        const [k1, k2, k3, p1, p2] = S.D;
        const term = (c, body) => (Math.abs(c) < 1e-9 ? '' : ` ${c < 0 ? '-' : '+'} ${+Math.abs(c).toFixed(4)}${body}`);
        const radial = `(1${term(k1, 'r^2')}${term(k2, 'r^4')}${term(k3, 'r^6')})`;
        const tx = `${term(2 * p1, 'xy')}${term(p2, '(r^2+2x^2)')}`, ty = `${term(p1, '(r^2+2y^2)')}${term(2 * p2, 'xy')}`;
        setTex(formula, `\\begin{aligned}x_d &= x\\,${radial}${tx}\\\\ y_d &= y\\,${radial}${ty}\\end{aligned}`);
        result.set('corner', `${S.corner_shift_px.toFixed(1)} px`);
        result.set('kind', S.D[0] < -1e-9 ? 'barrel (k₁ < 0)' : S.D[0] > 1e-9 ? 'pincushion (k₁ > 0)' : 'none');
        result.set('correction', `${S.correction_error_px.toExponential(1)} px`, S.correction_error_px < 0.01 ? 'good' : 'bad');
        draw();
    }
    load();
}
