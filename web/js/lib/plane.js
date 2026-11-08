// A 2-D view of a rectangle of world coordinates (e.g. the image plane), with
// optional dragging of a point. Image coordinates point right (x) and down (y),
// as on the slides, so the y axis is not flipped.
import { onThemeChange, palette } from './theme.js';

export class PlaneView {
    // rect: {x0, x1, y0, y1}; flipY: true for "y up" plots; keepAspect: false
    // stretches the axes independently to fill the canvas (e.g. a narrow
    // baseline next to a deep scene)
    constructor(canvas, { rect, flipY = false, margin = 18, keepAspect = true } = {}) {
        Object.assign(this, { canvas, rect, flipY, margin, keepAspect });
        this.redraw = () => {};
        new ResizeObserver(() => this.redraw()).observe(canvas);
        onThemeChange(() => this.redraw());
    }

    // world -> screen (one scale for both axes unless keepAspect is false)
    toScreen([x, y]) {
        const { rect, flipY } = this;
        const sx = this.x0 + (x - rect.x0) * this.kx;
        const sy = flipY ? this.y0 + (rect.y1 - y) * this.ky : this.y0 + (y - rect.y0) * this.ky;
        return [sx, sy];
    }

    toWorld([sx, sy]) {
        const { rect, flipY } = this;
        const x = rect.x0 + (sx - this.x0) / this.kx;
        const y = flipY ? rect.y1 - (sy - this.y0) / this.ky : rect.y0 + (sy - this.y0) / this.ky;
        return [x, y];
    }

    // Drag: onDrag([x, y]) while a pointer moves near the point getPoint() returns.
    enableDrag({ getPoint, onDrag, radius = 16 }) {
        const c = this.canvas;
        let active = false;
        const local = (e) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
        c.addEventListener('pointerdown', (e) => {
            const [sx, sy] = this.toScreen(getPoint());
            const [mx, my] = local(e);
            if (Math.hypot(sx - mx, sy - my) > radius) return;
            active = true;
            c.setPointerCapture(e.pointerId);
            e.preventDefault();
        });
        c.addEventListener('pointermove', (e) => {
            const [sx, sy] = this.toScreen(getPoint());
            const [mx, my] = local(e);
            c.style.cursor = active ? 'grabbing' : (Math.hypot(sx - mx, sy - my) <= radius ? 'grab' : '');
            if (active) onDrag(this.toWorld([mx, my]));
        });
        const end = () => { active = false; };
        c.addEventListener('pointerup', end);
        c.addEventListener('pointercancel', end);
    }

    draw(paint) {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
        if (!w || !h) return;
        if (this.canvas.width !== Math.round(w * dpr) || this.canvas.height !== Math.round(h * dpr)) {
            this.canvas.width = Math.round(w * dpr);
            this.canvas.height = Math.round(h * dpr);
        }
        const { rect, margin } = this;
        const kx = (w - 2 * margin) / (rect.x1 - rect.x0), ky = (h - 2 * margin) / (rect.y1 - rect.y0);
        this.k = Math.min(kx, ky);
        [this.kx, this.ky] = this.keepAspect ? [this.k, this.k] : [kx, ky];
        this.x0 = (w - this.kx * (rect.x1 - rect.x0)) / 2;
        this.y0 = (h - this.ky * (rect.y1 - rect.y0)) / 2;
        const ctx = this.canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        paint(new PlanePainter(this, ctx, palette(this.canvas)));
    }
}

class PlanePainter {
    constructor(view, ctx, p) { Object.assign(this, { view, ctx, p }); }

    _stroke(color, width, dash) {
        Object.assign(this.ctx, { strokeStyle: color, lineWidth: width, lineCap: 'round', lineJoin: 'round' });
        this.ctx.setLineDash(dash || []);
    }

    // The rectangle as an image (frame and grid), with the principal point.
    frame({ step = 0.1, axes = true } = {}) {
        const { rect } = this.view;
        const { ctx, p } = this;
        const [x0, y0] = this.view.toScreen([rect.x0, rect.y0]);
        const [x1, y1] = this.view.toScreen([rect.x1, rect.y1]);
        ctx.fillStyle = p.surface;
        ctx.fillRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
        for (let x = Math.ceil(rect.x0 / step) * step; x <= rect.x1 + 1e-9; x += step) this.line([x, rect.y0], [x, rect.y1], { color: p.grid, width: 1 });
        for (let y = Math.ceil(rect.y0 / step) * step; y <= rect.y1 + 1e-9; y += step) this.line([rect.x0, y], [rect.x1, y], { color: p.grid, width: 1 });
        if (axes) {
            this.line([rect.x0, 0], [rect.x1, 0], { color: p.gridStrong, width: 1 });
            this.line([0, rect.y0], [0, rect.y1], { color: p.gridStrong, width: 1 });
        }
        this._stroke(p.lineStrong, 1.2);
        ctx.strokeRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
    }

    line(a, b, opts = {}) { this.polyline([a, b], opts); }

    // Segments with null entries are split (points that left the image or the scene).
    polyline(points, { color = this.p.ink, width = 1.6, dash } = {}) {
        const { ctx } = this;
        this._stroke(color, width, dash);
        ctx.beginPath();
        let pen = false;
        for (const q of points) {
            if (!q || q.some((v) => v === null || !Number.isFinite(v))) { pen = false; continue; }
            const [x, y] = this.view.toScreen(q);
            if (pen) ctx.lineTo(x, y); else ctx.moveTo(x, y);
            pen = true;
        }
        ctx.stroke();
        ctx.setLineDash([]);
    }

    point(q, { r = 5, color = this.p.feature, ring = this.p.featureRing } = {}) {
        if (!q || q.some((v) => v === null)) return;
        const [x, y] = this.view.toScreen(q);
        const { ctx } = this;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        if (ring) { this._stroke(ring, 1.3); ctx.stroke(); }
    }

    arrow(a, b, { color = this.p.ink, width = 2, head = 9, dash } = {}) {
        const [x0, y0] = this.view.toScreen(a), [x1, y1] = this.view.toScreen(b);
        const len = Math.hypot(x1 - x0, y1 - y0);
        if (len < 1.5) return;
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

    text(q, text, { color = this.p.muted, dx = 0, dy = 0, size = 11, align = 'left' } = {}) {
        const [x, y] = this.view.toScreen(q);
        const { ctx } = this;
        ctx.font = `600 ${size}px ${getComputedStyle(document.body).fontFamily}`;
        ctx.fillStyle = color;
        ctx.textAlign = align;
        ctx.fillText(text, x + dx, y + dy);
        ctx.textAlign = 'left';
    }
}
