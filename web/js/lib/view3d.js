// A small 3-D view on a 2-D canvas, with perspective: drag to orbit, wheel to zoom.
// By default points are given in the camera-frame convention of the slides
// (x right, y down, z forward along the optical axis) and the view shows "up"
// as -y; with up: 'z' the world is z-up (e.g. a target lying on a table).
// Points behind the viewer are skipped (lines are broken there).
import { alpha, onThemeChange, palette } from './theme.js';

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export class View3D {
    // opts: {yaw, pitch, center: [x, y, z], extent (m across the view), onChange}
    constructor(canvas, { yaw = -0.75, pitch = 0.32, center = [0, 0, 1.2], extent = 3.2, up = 'cam', onChange } = {}) {
        Object.assign(this, { canvas, yaw, pitch, center, extent, up, zoom: 1, distance: 6 });
        this.redraw = () => {};
        this.onChange = onChange;
        new ResizeObserver(() => this.redraw()).observe(canvas);
        onThemeChange(() => this.redraw());
        this._interaction();
    }

    _interaction() {
        const c = this.canvas;
        let last = null;
        c.classList.add('orbit');
        c.addEventListener('pointerdown', (e) => { last = [e.clientX, e.clientY]; c.setPointerCapture(e.pointerId); });
        c.addEventListener('pointermove', (e) => {
            if (!last) return;
            this.yaw += (e.clientX - last[0]) * 0.008;
            this.pitch = clamp(this.pitch + (e.clientY - last[1]) * 0.008, -1.45, 1.45);
            last = [e.clientX, e.clientY];
            this.redraw();
        });
        const end = () => { last = null; };
        c.addEventListener('pointerup', end);
        c.addEventListener('pointercancel', end);
        c.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.zoom = clamp(this.zoom * Math.exp(-e.deltaY * 0.0012), 0.35, 4);
            this.redraw();
        }, { passive: false });
    }

    setView({ yaw, pitch, zoom } = {}) {
        if (yaw !== undefined) this.yaw = yaw;
        if (pitch !== undefined) this.pitch = pitch;
        if (zoom !== undefined) this.zoom = zoom;
        this.redraw();
    }

    // world point -> [screen x, screen y, depth], or null behind the viewer
    project(p) {
        const d = [p[0] - this.center[0], p[1] - this.center[1], p[2] - this.center[2]];
        let [X, Y, Z] = this.up === 'z' ? [d[0], d[2], d[1]] : [d[0], -d[1], d[2]];
        const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw);
        [X, Z] = [cy * X - sy * Z, sy * X + cy * Z];
        const cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
        [Y, Z] = [cp * Y - sp * Z, sp * Y + cp * Z];
        if (this.distance + Z < 0.3) return null;
        const k = this.unit * this.zoom * this.distance / (this.distance + Z);
        return [this.w / 2 + k * X, this.h / 2 - k * Y, Z];
    }

    draw(paint) {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
        if (!w || !h) return;
        if (this.canvas.width !== Math.round(w * dpr) || this.canvas.height !== Math.round(h * dpr)) {
            this.canvas.width = Math.round(w * dpr);
            this.canvas.height = Math.round(h * dpr);
        }
        Object.assign(this, { w, h, unit: Math.min(w, h) / this.extent });
        const ctx = this.canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        paint(new Painter(this, ctx, palette(this.canvas)));
    }
}

class Painter {
    constructor(view, ctx, p) { Object.assign(this, { view, ctx, p }); }

    _stroke(color, width, dash) {
        const { ctx } = this;
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.setLineDash(dash || []);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
    }

    line(a, b, { color = this.p.ink, width = 1.5, dash } = {}) { this.polyline([a, b], { color, width, dash }); }

    polyline(points, { color = this.p.ink, width = 1.5, dash, closed = false } = {}) {
        const pts = points.map((q) => (q ? this.view.project(q) : null));
        if (pts.filter(Boolean).length < 2) return;
        const { ctx } = this;
        this._stroke(color, width, dash);
        ctx.beginPath();
        let pen = false;
        for (const q of pts) {
            if (!q) { pen = false; continue; }
            if (pen) ctx.lineTo(q[0], q[1]); else ctx.moveTo(q[0], q[1]);
            pen = true;
        }
        if (closed && pts.every(Boolean)) ctx.closePath();
        ctx.stroke();
        ctx.setLineDash([]);
    }

    polygon(points, { fill, color, width = 1 } = {}) {
        const pts = points.map((q) => this.view.project(q));
        if (!pts.every(Boolean)) return;
        const { ctx } = this;
        ctx.beginPath();
        pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.closePath();
        if (fill) { ctx.fillStyle = fill; ctx.fill(); }
        if (color) { this._stroke(color, width); ctx.stroke(); }
    }

    point(q, { r = 4, color = this.p.feature, ring = this.p.featureRing } = {}) {
        const pr = this.view.project(q);
        if (!pr) return;
        const [x, y] = pr;
        const { ctx } = this;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        if (ring) { this._stroke(ring, 1.2); ctx.stroke(); }
    }

    arrow(a, b, { color = this.p.ink, width = 2, head = 8, dash } = {}) {
        const pa = this.view.project(a), pb = this.view.project(b);
        if (!pa || !pb) return;
        const [x0, y0] = pa, [x1, y1] = pb;
        const len = Math.hypot(x1 - x0, y1 - y0);
        if (len < 1) return;
        const { ctx } = this;
        this._stroke(color, width, dash);
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
        ctx.setLineDash([]);
        const ux = (x1 - x0) / len, uy = (y1 - y0) / len, hl = Math.min(head, len * 0.6);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x1 - hl * ux + hl * 0.45 * uy, y1 - hl * uy - hl * 0.45 * ux);
        ctx.lineTo(x1 - hl * ux - hl * 0.45 * uy, y1 - hl * uy + hl * 0.45 * ux);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
    }

    label(q, text, { color = this.p.inkSoft, dx = 6, dy = -6, size = 12, align = 'left' } = {}) {
        const pr = this.view.project(q);
        if (!pr) return;
        const [x, y] = pr;
        const { ctx } = this;
        ctx.font = `600 ${size}px ${getComputedStyle(document.body).fontFamily}`;
        ctx.fillStyle = color;
        ctx.textAlign = align;
        ctx.fillText(text, x + dx, y + dy);
        ctx.textAlign = 'left';
    }

    // A floor grid (plane y = level, the floor of the camera-frame convention).
    floor({ level = 0.8, extent = 2.5, step = 0.5, zFrom = -1, zTo = 4 } = {}) {
        const color = this.p.grid;
        for (let x = -extent; x <= extent + 1e-9; x += step) this.line([x, level, zFrom], [x, level, zTo], { color, width: 1 });
        for (let z = zFrom; z <= zTo + 1e-9; z += step) this.line([-extent, level, z], [extent, level, z], { color, width: 1 });
    }

    // A coordinate frame: x red, y green, z blue (T: 4x4 pose, nested arrays).
    frame(T, { size = 0.1, width = 1.8, label = null, color = this.p.inkSoft } = {}) {
        const o = [T[0][3], T[1][3], T[2][3]];
        const tip = (j) => [0, 1, 2].map((i) => T[i][3] + size * T[i][j]);
        this.arrow(o, tip(0), { color: this.p.red, width, head: 6 });
        this.arrow(o, tip(1), { color: this.p.aqua, width, head: 6 });
        this.arrow(o, tip(2), { color: this.p.rod, width, head: 6 });
        if (label) this.label(o, label, { color, size: 11, dx: -6, dy: 14 });
    }

    // A grid on the plane z = 0 (z-up worlds: the table).
    table({ extent = 0.6, step = 0.1, cx = 0, cy = 0 } = {}) {
        const color = this.p.grid;
        for (let a = -extent; a <= extent + 1e-9; a += step) {
            this.line([cx + a, cy - extent, 0], [cx + a, cy + extent, 0], { color, width: 1 });
            this.line([cx - extent, cy + a, 0], [cx + extent, cy + a, 0], { color, width: 1 });
        }
    }

    // A camera drawn as a frustum with its image plane at depth `size`, and its axes.
    // T: 4x4 pose in the reference camera frame (nested arrays).
    camera(T, { color = this.p.inkSoft, size = 0.35, aspect = 0.75, fill = null, axes = true, width = 1.6, dash } = {}) {
        const at = (x, y, z) => [0, 1, 2].map((i) => T[i][0] * x + T[i][1] * y + T[i][2] * z + T[i][3]);
        const o = at(0, 0, 0);
        const c = [at(-size * 0.5, -size * 0.5 * aspect, size), at(size * 0.5, -size * 0.5 * aspect, size),
            at(size * 0.5, size * 0.5 * aspect, size), at(-size * 0.5, size * 0.5 * aspect, size)];
        if (fill) this.polygon(c, { fill });
        for (const corner of c) this.line(o, corner, { color, width, dash });
        this.polyline(c, { color, width, dash, closed: true });
        if (axes) {
            const L = size * 0.9;
            this.arrow(o, at(L, 0, 0), { color: this.p.red, width: 1.6, head: 6 });
            this.arrow(o, at(0, L, 0), { color: this.p.aqua, width: 1.6, head: 6 });
            this.arrow(o, at(0, 0, L), { color: this.p.rod, width: 1.6, head: 6 });
        }
    }
}

export { alpha };
