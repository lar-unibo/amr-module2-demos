// Line plots on a canvas, in the style of the cv-page signal panels.
import { palette, alpha, onThemeChange } from './theme.js';

const PAD = { l: 50, r: 14, t: 10, b: 32 };

export class LinePlot {
    // opts: {xLabel, yLabel, x: [min, max] | null (auto), y: [min, max] | null, logY}
    constructor(canvas, opts = {}) {
        this.canvas = canvas;
        this.opts = { x: null, y: null, logY: false, ...opts };
        this.series = []; this.markers = []; this.hlines = []; this.vlines = []; this.bands = [];
        new ResizeObserver(() => this.draw()).observe(canvas);
        onThemeChange(() => this.draw());
    }

    set({ series, markers, hlines, vlines, bands } = {}) {
        if (series) this.series = series;
        if (markers) this.markers = markers;
        if (hlines) this.hlines = hlines;
        if (vlines) this.vlines = vlines;
        if (bands) this.bands = bands;
        this.draw();
    }

    range() {
        const { opts } = this;
        const xs = [], ys = [];
        for (const s of this.series) {
            s.x.forEach((v, i) => {
                const y = s.y[i];
                if (Number.isFinite(v)) xs.push(v);
                if (Number.isFinite(y) && (!opts.logY || y > 0)) ys.push(y);
            });
        }
        let [x0, x1] = opts.x || [Math.min(...xs, 0), Math.max(...xs, 1)];
        let [y0, y1] = opts.y || (opts.logY
            ? [10 ** Math.floor(Math.log10(Math.min(...ys, 1))), 10 ** Math.ceil(Math.log10(Math.max(...ys, 1)))]
            : niceRange(Math.min(...ys, opts.yIncludeZero === false ? Infinity : 0), Math.max(...ys, 1e-9)));
        if (opts.yMinSpan && !opts.y && !opts.logY && y1 - y0 < opts.yMinSpan) y1 = y0 + opts.yMinSpan;
        if (x1 <= x0) x1 = x0 + 1;
        if (y1 <= y0) y1 = y0 + 1;
        return { x0, x1, y0, y1 };
    }

    draw() {
        const canvas = this.canvas;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const w = canvas.clientWidth, h = canvas.clientHeight;
        if (!w || !h) return;
        if (canvas.width !== Math.round(w * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
        const ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        const p = palette();
        const font = getComputedStyle(document.body).fontFamily;
        ctx.clearRect(0, 0, w, h);

        const { x0, x1, y0, y1 } = this.range();
        const L = PAD.l, R = w - PAD.r, T = PAD.t, B = h - PAD.b;
        const { logY, logX } = this.opts;
        const fy = (v) => (logY ? Math.log10(Math.max(v, 1e-300)) : v);
        const fx = (v) => (logX ? Math.log10(Math.max(v, 1e-300)) : v);
        const X = (v) => L + (fx(v) - fx(x0)) / (fx(x1) - fx(x0)) * (R - L);
        const Y = (v) => Math.min(B + 40, Math.max(T - 40, B - (fy(v) - fy(y0)) / (fy(y1) - fy(y0)) * (B - T)));

        // bands and grid
        for (const band of this.bands) {
            ctx.fillStyle = band.color;
            ctx.fillRect(X(Math.max(band.x0, x0)), T, X(Math.min(band.x1, x1)) - X(Math.max(band.x0, x0)), B - T);
        }
        const yTicks = logY ? logTicks(y0, y1) : niceTicks(y0, y1, 4);
        const xTicks = logX ? logTicks(x0, x1) : niceTicks(x0, x1, 5);
        ctx.strokeStyle = p.grid; ctx.lineWidth = 1;
        for (const t of yTicks) { ctx.beginPath(); ctx.moveTo(L, Y(t)); ctx.lineTo(R, Y(t)); ctx.stroke(); }
        if (!logY && y0 < 0 && y1 > 0) {
            ctx.strokeStyle = p.gridStrong;
            ctx.beginPath(); ctx.moveTo(L, Y(0)); ctx.lineTo(R, Y(0)); ctx.stroke();
        }

        ctx.save();
        ctx.beginPath(); ctx.rect(L, T - 2, R - L, B - T + 4); ctx.clip();
        for (const line of this.hlines) {
            ctx.strokeStyle = line.color || alpha(p.ink, 0.3); ctx.lineWidth = line.width || 1;
            ctx.setLineDash(line.dash || [4, 4]);
            ctx.beginPath(); ctx.moveTo(L, Y(line.y)); ctx.lineTo(R, Y(line.y)); ctx.stroke();
        }
        for (const line of this.vlines) {
            ctx.strokeStyle = line.color || alpha(p.ink, 0.3); ctx.lineWidth = line.width || 1;
            ctx.setLineDash(line.dash || [3, 4]);
            ctx.beginPath(); ctx.moveTo(X(line.x), T); ctx.lineTo(X(line.x), B); ctx.stroke();
        }
        ctx.setLineDash([]);
        ctx.lineJoin = 'round'; ctx.lineCap = 'round';
        for (const s of this.series) {
            ctx.strokeStyle = s.color; ctx.lineWidth = s.width || 1.8;
            ctx.globalAlpha = s.alpha ?? 1;
            ctx.setLineDash(s.dash || []);
            ctx.beginPath();
            let pen = false;
            s.x.forEach((xv, i) => {
                const yv = s.y[i];
                if (!Number.isFinite(yv) || (logY && yv <= 0)) { pen = false; return; }
                if (pen) ctx.lineTo(X(xv), Y(yv)); else { ctx.moveTo(X(xv), Y(yv)); pen = true; }
            });
            ctx.stroke();
        }
        ctx.globalAlpha = 1; ctx.setLineDash([]);
        for (const m of this.markers) {
            if (!Number.isFinite(m.y)) continue;
            ctx.fillStyle = m.color; ctx.strokeStyle = p.surface; ctx.lineWidth = 1.5;
            ctx.beginPath(); ctx.arc(X(m.x), Y(m.y), m.r || 4, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        }
        ctx.restore();

        // axes
        ctx.fillStyle = p.muted;
        ctx.font = `10px ${font}`;
        ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        for (const t of yTicks) ctx.fillText(formatTick(t, logY), L - 6, Y(t));
        ctx.textAlign = 'center'; ctx.textBaseline = 'top';
        for (const t of xTicks) ctx.fillText(formatTick(t, logX), X(t), B + 5);
        ctx.font = `600 10px ${font}`;
        if (this.opts.xLabel) ctx.fillText(this.opts.xLabel, (L + R) / 2, h - 13);
        if (this.opts.yLabel) {
            ctx.save(); ctx.translate(11, (T + B) / 2); ctx.rotate(-Math.PI / 2);
            ctx.textBaseline = 'middle'; ctx.fillText(this.opts.yLabel, 0, 0); ctx.restore();
        }
        ctx.strokeStyle = p.lineStrong; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(L, T); ctx.lineTo(L, B); ctx.lineTo(R, B); ctx.stroke();
    }
}

function niceStep(span, count) {
    const raw = span / Math.max(count, 1);
    const mag = 10 ** Math.floor(Math.log10(raw));
    const norm = raw / mag;
    return (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
}
export function niceRange(lo, hi) {
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [0, 1];
    if (hi - lo < 1e-12) { hi = lo + 1; }
    const step = niceStep(hi - lo, 4);
    return [Math.floor(lo / step) * step, Math.ceil(hi / step) * step];
}
function niceTicks(lo, hi, count) {
    const step = niceStep(hi - lo, count);
    const out = [];
    for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + 1e-9 * step; v += step) out.push(Math.abs(v) < 1e-12 ? 0 : v);
    return out;
}
function logTicks(lo, hi) {
    const out = [];
    for (let e = Math.ceil(Math.log10(lo) - 1e-9); e <= Math.log10(hi) + 1e-9; e++) out.push(10 ** e);
    return out;
}
function formatTick(v, log) {
    if (log) {
        const e = Math.round(Math.log10(v));
        return e >= -2 && e <= 3 ? String(10 ** e >= 1 ? 10 ** e : (10 ** e).toFixed(-e)) : `1e${e}`;
    }
    const a = Math.abs(v);
    if (a === 0) return '0';
    if (a >= 1000 || a < 0.01) return v.toExponential(0);
    return String(Number(v.toPrecision(3)));
}
