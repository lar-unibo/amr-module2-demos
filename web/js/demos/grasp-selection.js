// Lecture 3, demo 4 - Grasp selection from point clouds: normals, curvature, antipodal grasps, pregrasp.
import { dataTable } from '../lib/cams.js';
import { alpha, mix } from '../lib/theme.js';
import { card, h, label, readouts, segmented, slider, toggle } from '../lib/ui.js';
import { planeCard } from '../lib/widgets.js';

const MAIN = { x0: -0.11, x1: 0.11, y0: -0.012, y1: 0.222 };          // x and z (m), z up
const SCENE = { x0: -0.25, x1: 0.25, y0: -0.03, y1: 0.47 };
const cm = (v, d = 1) => `${(100 * v).toFixed(d)} cm`;

// surface variation: blue on flat patches, yellow, then red on edges and rims
function sigmaColor(p, s) {
    const t = Math.min(Math.max(s / 0.25, 0), 1);
    return t < 0.5 ? mix(p.rod, p.feature, 2 * t) : mix(p.feature, p.red, 2 * t - 1);
}

export async function mount({ workspace, session, state, options }) {
    let S = state;
    if (options.preset) S = await session.call('preset', { name: options.preset });
    let selected = 0;

    const main = planeCard('Point cloud and grasp', { rect: MAIN, flipY: true }, {
        note: 'drag the ring: the probe of local PCA · 1 cm grid',
        legendItems: (p) => [
            { label: 'flat ($\\sigma_i\\approx 0$)', color: p.rod, kind: 'dot' },
            { label: 'edge, rim ($\\sigma_i\\geq 0.25$)', color: p.red, kind: 'dot' },
            { label: 'antipodal pairs', color: p.aqua, kind: 'line' },
            { label: 'gripper at the grasp', color: p.accent, kind: 'line' },
            { label: 'pregrasp', color: p.accent, kind: 'dashed' },
        ],
    });
    main.canvas.style.height = 'auto';                                  // the frame fills the canvas
    main.canvas.style.aspectRatio = `${(MAIN.x1 - MAIN.x0 + 0.012) / (MAIN.y1 - MAIN.y0 + 0.012)}`;
    const scene = planeCard('Depth cameras', { rect: SCENE, flipY: true }, { note: 'rays every 14 pixels' });
    scene.canvas.style.height = '230px';
    const zoom = planeCard('Local PCA at the probe', { rect: { x0: -0.01, x1: 0.01, y0: -0.01, y1: 0.01 }, flipY: true }, {
        note: 'k nearest points · $v_0$ dashed, $n_i$ orange, $v_1$ blue',
    });
    zoom.canvas.style.height = '190px';
    const pcaReadouts = readouts([
        { key: 'l0', label: '$\\lambda_0$' }, { key: 'l1', label: '$\\lambda_1$' },
        { key: 'sigma', label: '$\\sigma_i$' }, { key: 'err', label: 'normal error' },
    ]);
    const pcaNote = h('p', { class: 'equation-note' });
    zoom.body.append(pcaReadouts.el, pcaNote);

    // ---- controls
    const send = session.stream('set', (next) => { S = next; selected = 0; load(); });
    const probe = session.stream('probe', (next) => { S = next; load(); });
    const sl = (key, text, min, max, step, format, scale = 1) => slider({
        label: text, min, max, step, value: S[key] * scale, format, onInput: (v) => send({ [key]: v / scale }),
    });
    const object = segmented({ options: [{ value: 'box', label: 'box' }, { value: 'blob', label: 'blob' }, { value: 'cup', label: 'cup' }],
        value: S.object, onChange: (v) => send({ object: v }) });
    const cameras = segmented({ options: [{ value: 1, label: 'one (left)' }, { value: 2, label: 'two' }],
        value: S.cameras, onChange: (v) => send({ cameras: v }) });
    const noise = sl('noise', 'depth noise', 0, 3, 0.1, (v) => `${v.toFixed(1)} mm`, 1000);
    const k = sl('k', 'neighbours $k$', 3, 40, 1, (v) => String(Math.round(v)));
    const orient = toggle({ label: 'orient the normals towards the camera', value: S.orient, onChange: (v) => send({ orient: v }) });
    const cloudCard = card('Point cloud', 'table points removed');
    cloudCard.body.append(h('div', { class: 'choice-row' }, h('span', {}, 'object'), object.el, h('span', {}, 'cameras'), cameras.el),
        h('div', { class: 'slider-group' }, noise.el, k.el), orient.el);

    const mu = sl('mu', 'friction coefficient $\\mu$', 0.05, 1.2, 0.01, (v) => `${v.toFixed(2)} (cone ${(Math.atan(v) * 180 / Math.PI).toFixed(1)}°)`);
    const opening = sl('opening', 'maximum opening', 2, 12, 0.1, (v) => `${v.toFixed(1)} cm`, 100);
    const d = sl('d', 'pregrasp distance $d$', 2, 15, 0.5, (v) => `${v.toFixed(1)} cm`, 100);
    const aReach = sl('alpha_reach', 'weight $\\alpha_2$: top-down', 0, 2, 0.05, (v) => v.toFixed(2));
    const aClear = sl('alpha_clear', 'weight $\\alpha_3$: clearance', 0, 2, 0.05, (v) => v.toFixed(2));
    const gripCard = card('Gripper and cost', '$C=C_{\\text{antipodal}}+\\alpha_2C_{\\text{reach}}+\\alpha_3C_{\\text{clear}}$');
    gripCard.body.append(h('div', { class: 'slider-group' }, mu.el, opening.el, d.el, aReach.el, aClear.el));

    const candCard = card('Candidates', 'click a row · $C_a$ antipodal, $C_r$ reach, $C_c$ clearance');
    const counts = readouts([
        { key: 'points', label: 'points' }, { key: 'within', label: 'pairs that fit' },
        { key: 'anti', label: 'antipodal' }, { key: 'free', label: 'poses without collision' },
    ]);
    const tableHolder = h('div', { class: 'table-scroll' });
    const candNote = h('p', { class: 'equation-note' });
    candCard.body.append(counts.el, tableHolder, candNote);

    workspace.append(h('section', { class: 'views' }, main.el, h('div', {}, scene.el, zoom.el)),
        h('section', { class: 'plots' }, cloudCard.el, gripCard.el, candCard.el));
    main.view.redraw = drawMain;
    scene.view.redraw = drawScene;
    zoom.view.redraw = drawZoom;
    main.view.enableDrag({ getPoint: () => S.probe.point, radius: 18, onDrag: ([x, z]) => probe({ x, z }) });

    // ---- drawing helpers
    const at = (o, xg, zg, x, z) => [o[0] + x * xg[0] + z * zg[0], o[1] + x * xg[1] + z * zg[1]];
    // the gripper of the slides: two fingers, a palm and a wrist (frame: x_g closing, z_g approach)
    function gripper(g, o, xg, zg, open, { color, fill, dash, width = 1.5 }) {
        const G = S.gripper, tf = G.finger_width, L = G.finger_length, tip = G.tip, tp = G.palm_height;
        const hp = G.max_opening / 2 + tf, w = open / 2;
        const rects = [[w, w + tf, -L, tip], [-w - tf, -w, -L, tip], [-hp, hp, -L - tp, -L],
            [-G.wrist_width / 2, G.wrist_width / 2, -L - tp - G.wrist_length, -L - tp]];
        for (const [x0, x1, z0, z1] of rects) {
            g.polygon([at(o, xg, zg, x0, z0), at(o, xg, zg, x1, z0), at(o, xg, zg, x1, z1), at(o, xg, zg, x0, z1)], { fill, color, width, dash });
        }
    }
    function clipToRect(g, rect) {
        const [x0, y0] = g.view.toScreen([rect.x0, rect.y1]), [x1, y1] = g.view.toScreen([rect.x1, rect.y0]);
        g.ctx.save();
        g.ctx.beginPath();
        g.ctx.rect(x0, y0, x1 - x0, y1 - y0);
        g.ctx.clip();
    }
    function table(g, rect) {
        const [x0, y0] = g.view.toScreen([rect.x0, 0]), [x1, y1] = g.view.toScreen([rect.x1, rect.y0]);
        g.ctx.fillStyle = alpha(g.p.robot, 0.25);
        g.ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
        g.line([rect.x0, 0], [rect.x1, 0], { color: g.p.robotDeep, width: 2 });
    }

    function drawMain() {
        main.view.draw((g) => {
            const p = g.p;
            g.frame({ step: 0.01, axes: false });
            clipToRect(g, MAIN);
            table(g, MAIN);
            S.rays.forEach((hits, c) => hits.forEach((q) => g.line(S.camera_positions[c], q, { color: alpha(p.muted, 0.18), width: 1 })));
            g.polyline(S.outline, { color: alpha(p.ink, 0.35), width: 1, dash: [4, 3] });
            for (const q of S.table) g.point(q, { r: 1.6, color: alpha(p.muted, 0.6), ring: null });
            for (const [i, j, free] of S.pairs) {               // antipodal pairs (grey: every pose collides)
                g.line(S.cloud[i], S.cloud[j], { color: free ? alpha(p.aqua, 0.25) : alpha(p.muted, 0.07), width: 1 });
            }
            const pr = S.probe, nb = new Set(pr.neighbours);
            S.cloud.forEach((q, i) => {
                const n = S.normals[i];
                g.line(q, [q[0] + 0.006 * n[0], q[1] + 0.006 * n[1]], { color: alpha(p.inkSoft, 0.55), width: 1 });
            });
            S.cloud.forEach((q, i) => g.point(q, { r: nb.has(i) ? 3.4 : 2.4, color: sigmaColor(p, S.sigma[i]), ring: nb.has(i) ? p.ink : null }));
            const t = S.top[selected];
            if (t) {
                const half = S.cone_half_angle * Math.PI / 180, L = 0.016;
                t.contacts.forEach((c, m) => {
                    const n = t.normals[m], a = Math.atan2(-n[1], -n[0]);
                    const e = (s) => [c[0] + L * Math.cos(a + s * half) / Math.cos(half), c[1] + L * Math.sin(a + s * half) / Math.cos(half)];
                    g.polygon([c, e(1), e(-1)], { fill: alpha(p.aqua, 0.2), color: alpha(p.aqua, 0.8), width: 1 });
                });
                gripper(g, t.pregrasp, t.xg, t.zg, t.opening, { color: alpha(p.accent, 0.7), dash: [4, 3], width: 1.2 });
                g.arrow(t.pregrasp, [t.centre[0] - 0.012 * t.zg[0], t.centre[1] - 0.012 * t.zg[1]], { color: p.accent, width: 1.8, head: 8 });
                gripper(g, t.centre, t.xg, t.zg, t.distance, { color: p.accent, fill: alpha(p.accent, 0.28) });
                t.contacts.forEach((c) => g.point(c, { r: 4, color: p.gripR, ring: p.surface }));
                g.text(t.pregrasp, 'pregrasp', { dx: 10, dy: -4, size: 10, color: p.accent });
            }
            // the probe: neighbours (black rings), normal, ring
            g.arrow(pr.point, [pr.point[0] + 0.012 * pr.normal[0], pr.point[1] + 0.012 * pr.normal[1]], { color: p.ink, width: 2, head: 7 });
            g.point(pr.point, { r: 8, color: 'rgba(0,0,0,0)', ring: p.ink });
            g.ctx.restore();
            S.camera_positions.forEach((c, i) => {
                const x = Math.max(MAIN.x0 + 0.004, Math.min(MAIN.x1 - 0.004, c[0] > 0 ? MAIN.x1 - 0.004 : MAIN.x0 + 0.004));
                g.text([x, MAIN.y1], `camera ${i + 1} ${c[0] < 0 ? '↖' : '↗'}`, { dy: 13, dx: c[0] < 0 ? 4 : -4, size: 10, align: c[0] < 0 ? 'left' : 'right' });
            });
        });
    }

    function drawScene() {
        scene.view.draw((g) => {
            const p = g.p;
            g.frame({ step: 0.05, axes: false });
            clipToRect(g, SCENE);
            table(g, SCENE);
            g.polygon(S.outline, { fill: alpha(p.robot, 0.5), color: p.robotDeep, width: 1 });
            S.rays.forEach((hits, c) => hits.forEach((q) => g.line(S.camera_positions[c], q, { color: alpha(p.series[c], 0.35), width: 1 })));
            S.cloud.forEach((q, i) => g.point(q, { r: 1.3, color: p.series[S.camera_of[i]], ring: null }));
            S.camera_positions.forEach((c, i) => {
                const a = Math.atan2(S.target[1] - c[1], S.target[0] - c[0]);
                const tri = [-0.45, 0.45].map((s) => [c[0] + 0.035 * Math.cos(a + s), c[1] + 0.035 * Math.sin(a + s)]);
                g.polygon([c, ...tri], { fill: p.surface, color: p.series[i], width: 1.8 });
                g.text(c, `camera ${i + 1}`, { dx: c[0] < 0 ? 10 : -10, dy: -6, size: 10, align: c[0] < 0 ? 'left' : 'right', color: p.series[i] });
            });
            g.ctx.restore();
        });
    }

    function drawZoom() {
        const pr = S.probe;
        const pts = pr.neighbours.map((i) => S.cloud[i]);
        const r = Math.max(0.004, 1.35 * Math.max(...pts.map((q) => Math.hypot(q[0] - pr.mean[0], q[1] - pr.mean[1]))));
        zoom.view.rect = { x0: pr.mean[0] - r, x1: pr.mean[0] + r, y0: pr.mean[1] - r, y1: pr.mean[1] + r };
        zoom.view.draw((g) => {
            const p = g.p;
            g.frame({ step: r > 0.012 ? 0.005 : 0.002, axes: false });
            clipToRect(g, zoom.view.rect);
            if (pr.mean[1] - r < 0) table(g, zoom.view.rect);
            g.polyline(S.outline, { color: alpha(p.ink, 0.3), width: 1, dash: [4, 3] });
            S.cloud.forEach((q) => g.point(q, { r: 2.2, color: alpha(p.muted, 0.5), ring: null }));
            // ellipse with semi-axes 2 sqrt(lambda) along v0, v1
            const a0 = 2 * Math.sqrt(Math.max(pr.lam[0], 0)), a1 = 2 * Math.sqrt(Math.max(pr.lam[1], 0));
            const ell = Array.from({ length: 61 }, (_, i) => {
                const t = 2 * Math.PI * i / 60;
                return [pr.mean[0] + a0 * Math.cos(t) * pr.v0[0] + a1 * Math.sin(t) * pr.v1[0], pr.mean[1] + a0 * Math.cos(t) * pr.v0[1] + a1 * Math.sin(t) * pr.v1[1]];
            });
            g.polygon(ell, { fill: alpha(p.accent, 0.1), color: alpha(p.accent, 0.7), width: 1.2 });
            g.line([pr.mean[0] - a1 * pr.v1[0], pr.mean[1] - a1 * pr.v1[1]], [pr.mean[0] + a1 * pr.v1[0], pr.mean[1] + a1 * pr.v1[1]], { color: p.rod, width: 1.6 });
            pts.forEach((q) => g.point(q, { r: 4, color: sigmaColor(p, S.sigma[pr.index]), ring: p.ink }));
            const L = 0.55 * r;
            g.line([pr.point[0] - L * pr.v0[0], pr.point[1] - L * pr.v0[1]], [pr.point[0] + L * pr.v0[0], pr.point[1] + L * pr.v0[1]], { color: alpha(p.ink, 0.5), width: 1.2, dash: [4, 3] });
            g.arrow(pr.point, [pr.point[0] + L * pr.normal[0], pr.point[1] + L * pr.normal[1]], { color: p.gripR, width: 2.4, head: 9 });
            g.point(pr.point, { r: 6, color: 'rgba(0,0,0,0)', ring: p.ink });
            g.ctx.restore();
        });
    }

    function drawTable() {
        const rows = S.top.map((t, i) => ({
            rank: String(i + 1), dist: 100 * t.distance, th1: t.theta1, th2: t.theta2,
            ca: t.c_antipodal, cr: t.c_reach, cc: t.c_clear, c: t.cost,
        }));
        const table = dataTable([
            { key: 'rank', label: '#' }, { key: 'dist', label: 'cm', digits: 1 },
            { key: 'th1', label: '$\\theta_1$°', digits: 1 }, { key: 'th2', label: '$\\theta_2$°', digits: 1 },
            { key: 'ca', label: '$C_a$', digits: 2 }, { key: 'cr', label: '$C_r$', digits: 2 },
            { key: 'cc', label: '$C_c$', digits: 2 }, { key: 'c', label: '$C$', digits: 2 },
        ], rows, { highlight: selected });
        table.querySelectorAll('tbody tr').forEach((tr, i) => {
            tr.style.cursor = 'pointer';
            tr.addEventListener('click', () => { selected = i; drawTable(); drawMain(); });
        });
        tableHolder.replaceChildren(table);
    }

    function load() {
        object.set(S.object); cameras.set(S.cameras); noise.set(S.noise * 1000); k.set(S.k); orient.set(S.orient);
        mu.set(S.mu); opening.set(S.opening * 100); d.set(S.d * 100); aReach.set(S.alpha_reach); aClear.set(S.alpha_clear);
        if (selected >= S.top.length) selected = 0;
        const C = S.counts;
        counts.set('points', String(C.points));
        counts.set('within', String(C.within_opening));
        counts.set('anti', String(C.antipodal), C.antipodal ? '' : 'bad');
        counts.set('free', String(C.free), C.free ? 'good' : 'bad');
        const pr = S.probe;
        const mm2 = (v) => { const x = 1e6 * Math.max(v, 0); return `${x >= 0.01 ? x.toFixed(2) : x.toExponential(1)} mm²`; };
        pcaReadouts.set('l0', mm2(pr.lam[0]));
        pcaReadouts.set('l1', mm2(pr.lam[1]));
        pcaReadouts.set('sigma', pr.sigma.toFixed(3), pr.sigma < 0.05 ? 'good' : pr.sigma > 0.15 ? 'bad' : '');
        pcaReadouts.set('err', `${pr.error_deg.toFixed(1)}°`, pr.error_deg < 10 ? 'good' : 'bad');
        pcaNote.replaceChildren(label(S.orient
            ? `Seen by camera ${pr.camera + 1}: $v_0$ ${pr.flipped ? 'was flipped' : 'already pointed'} towards it. Median normal error of the cloud: ${S.normal_error.median.toFixed(1)}°.`
            : `Not oriented: the sign of $v_0$ is arbitrary. ${(100 * S.normal_error.inward).toFixed(0)}% of the normals point inside the object.`));
        if (!S.top.length) {
            candNote.replaceChildren(label(C.antipodal
                ? 'Every antipodal pair needs a gripper pose that hits the object or the table.'
                : C.within_opening ? 'No pair of points has both normals inside the friction cones of the other: no antipodal grasp. Is the far side of the object seen?'
                    : 'No two points are closer than the maximum opening.'));
        } else {
            const t = S.top[selected];
            candNote.replaceChildren(label(`Shown: candidate ${selected + 1}, opening ${cm(t.distance)} between the contacts, approach ${(90 * t.c_reach).toFixed(0)}° from vertical, clearance ${(1000 * t.clearance).toFixed(0)} mm. Pregrasp: ${cm(S.d, 0)} back along $z_g$.`));
        }
        drawTable(); drawMain(); drawScene(); drawZoom();
    }
    load();
}
