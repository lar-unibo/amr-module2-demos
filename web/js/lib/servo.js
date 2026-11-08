// Shared pieces of the closed-loop demos: playback of a simulated run, the 3-D
// scene (target, desired and current camera, camera path), the image plane
// (desired and current points, image paths, field of view), and time plots.
// Colours of the slides: red = current, blue = desired.
import { alpha } from './theme.js';
import { button, h, segmented } from './ui.js';

export const IMAGE_RECT = { x0: -0.78, x1: 0.78, y0: -0.6, y1: 0.6 };
const IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];

export const servoColors = (p) => ({
    current: p.red, desired: p.rod, path: alpha(p.red, 0.55), estimate: p.gripL,
    target: p.inkSoft, trans: p.gripR, rot: p.gripL, other: p.aqua,
});

const STATUS = {
    converged: ['converged', 'good'],
    settled: ['settled (noisy measurements)', 'good'],
    running: ['time ran out', ''],
    stalled: ['stopped with e ≠ 0', 'bad'],
    'point lost': ['a point went behind the camera', 'bad'],
    'camera lost': ['the camera went to infinity', 'bad'],
};
export const statusText = (status) => STATUS[status] || [status, ''];
// 'running' runs whose error is already small are only kept moving by noise.
export const runStatus = (run) => (run.status === 'running' && run.e_norm[run.e_norm.length - 1] < 2e-3 ? 'settled' : run.status);

// How close the points come to the image border: 1 = on the border.
export function borderRatio(frame, fov) {
    return Math.max(...frame.map(([x, y]) => Math.max(Math.abs(x) / fov[0], Math.abs(y) / fov[1])));
}

// ------------------------------------------------------------------ playback
// Play / pause, a time slider, and the playback speed. onFrame(k) draws step k.
export function playback({ onFrame, label = 't' }) {
    let n = 1, k = 0, playing = false, last = 0, speed = 1, raf = 0, dt = 0.04;
    const play = button('▶ Play', () => (playing ? stop() : start()), { primary: true });
    const slider = h('input', { type: 'range', min: 0, max: 0, step: 1, value: 0, class: 'time-slider', 'aria-label': 'time' });
    const clock = h('output', { class: 'time-readout' }, `${label} = 0.00 s`);
    const speeds = segmented({ options: [{ value: 0.5, label: '½×' }, { value: 1, label: '1×' }, { value: 3, label: '3×' }], value: 1, onChange: (v) => { speed = v; } });
    slider.addEventListener('input', () => { stop(); set(Number(slider.value)); });
    const el = h('div', { class: 'playback' }, play, slider, clock, speeds.el);

    function set(index) {
        k = Math.max(0, Math.min(n - 1, index));
        slider.value = String(k);
        clock.textContent = `${label} = ${(k * dt).toFixed(2)} s`;
        onFrame(k);
    }
    function start() {
        if (k >= n - 1) set(0);
        playing = true;
        play.firstChild.textContent = '❚❚ Pause';
        last = performance.now();
        let acc = 0;
        const tick = (now) => {
            if (!playing) return;
            acc += (now - last) / 1000 * speed / dt;
            last = now;
            if (acc >= 1) { const steps = Math.floor(acc); acc -= steps; set(k + steps); }
            if (k >= n - 1) { stop(); return; }
            raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
    }
    function stop() {
        playing = false;
        cancelAnimationFrame(raf);
        play.firstChild.textContent = '▶ Play';
    }
    return {
        el, set, start, stop,
        get: () => k,
        // A new run: keep the time if possible, or go to the end (the result) / the start.
        load(length, period, { at = 'end' } = {}) {
            n = Math.max(1, length);
            dt = period;
            slider.max = String(n - 1);
            stop();
            set(at === 'end' ? n - 1 : at === 'start' ? 0 : Math.min(k, n - 1));
        },
    };
}

// ------------------------------------------------------------------ 3-D scene
// run: {T: [K][4][4], positions: [K][3]}; points: target points (n x 3).
export function drawServoScene(g, { points, T_od, runs, k, scale = 1 }) {
    const c = servoColors(g.p);
    g.floor({ level: 0.45 * scale, extent: 1.6 * scale, step: 0.25 * scale, zFrom: -2.6 * scale, zTo: 0.6 * scale });
    // target: a light square plate with the points
    const plate = points.length === 4 ? points : null;
    if (plate) g.polygon(plate, { fill: alpha(g.p.ink, 0.06), color: alpha(g.p.ink, 0.35) });
    points.forEach((q, i) => { g.point(q, { r: 4.5, color: g.p.surface, ring: g.p.ink }); g.label(q, String(i + 1), { size: 10, dx: 5, dy: -5 }); });
    const size = 0.16 * scale;
    g.camera(T_od, { color: c.desired, size, axes: false, width: 1.8 });
    for (const run of runs) {
        const i = Math.min(k, run.T.length - 1);
        const color = run.color || c.current;
        g.polyline(run.positions.slice(0, i + 1), { color: alpha(color, 0.75), width: 1.8 });
        g.polyline(run.positions.slice(i), { color: alpha(color, 0.18), width: 1.2, dash: [3, 4] });
        g.camera(run.T[i], { color, size, axes: true, width: 1.8 });
        if (run.estimate) g.camera(run.estimate[i], { color: c.estimate, size, axes: false, dash: [4, 3], width: 1.2 });
    }
}

// ------------------------------------------------------------------ image plane
export function drawServoImage(g, { s, s_star, k, fov, color, trail = true }) {
    const c = servoColors(g.p);
    const col = color || c.current;
    g.frame({ step: 0.1, axes: false });
    // field of view of the camera
    const [fx, fy] = fov;
    g.polyline([[-fx, -fy], [fx, -fy], [fx, fy], [-fx, fy], [-fx, -fy]], { color: g.p.lineStrong, width: 1.6 });
    g.text([-fx, -fy], 'image border', { dy: -5, size: 10 });
    const i = Math.min(k, s.length - 1);
    const n = s_star.length;
    s_star.forEach((q, j) => {                                   // desired points: blue diamonds
        const [x, y] = g.view.toScreen(q);
        const ctx = g.ctx;
        ctx.beginPath(); ctx.moveTo(x, y - 7); ctx.lineTo(x + 7, y); ctx.lineTo(x, y + 7); ctx.lineTo(x - 7, y); ctx.closePath();
        ctx.fillStyle = alpha(c.desired, 0.15); ctx.fill();
        ctx.strokeStyle = c.desired; ctx.lineWidth = 1.8; ctx.stroke();
        g.text(q, String(j + 1), { dx: 9, dy: -6, color: c.desired, size: 10 });
    });
    for (let j = 0; j < n; j++) {
        const path = s.map((frame) => frame[j]);
        if (trail) g.polyline(path.slice(0, i + 1), { color: alpha(col, 0.7), width: 1.6 });
        g.polyline(path.slice(i), { color: alpha(col, 0.15), width: 1.2, dash: [3, 4] });
        g.point(s[0][j], { r: 3, color: g.p.surface, ring: alpha(col, 0.6) });
        g.point(s[i][j], { r: 5, color: col, ring: g.p.surface });
    }
}

// ------------------------------------------------------------------ time plots
// A vertical cursor at time t on each plot.
export function cursor(t, p) { return [{ x: t, color: alpha(p.ink, 0.45), dash: [3, 3] }]; }

export const IDENTITY_POSE = IDENTITY;
