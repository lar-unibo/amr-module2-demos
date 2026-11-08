// Shared pieces of the camera demos of lecture 1: matrices and tables typeset
// with KaTeX, and number formatting.
import { tex } from './math.js';
import { h, label } from './ui.js';

const num = (v, digits) => {
    if (v === null || v === undefined || !Number.isFinite(v)) return '\\text{--}';
    if (Math.abs(v) < 0.5 * 10 ** -digits) return '0';
    const a = Math.abs(v);
    if (a >= 1e5 || (a < 1e-3)) return v.toExponential(2).replace(/e([+-]\d+)/, '\\!\\times\\!10^{$1}').replace('+', '');
    return v.toFixed(digits);
};

// \name = [ ... ] with the entries of M (rows of numbers).
export function matrixTex(name, M, digits = 3) {
    const rows = M.map((row) => row.map((v) => num(v, digits)).join(' & ')).join(' \\\\ ');
    return `${name} = \\begin{bmatrix} ${rows} \\end{bmatrix}`;
}

export function setTex(el, source, display = true) { el.innerHTML = tex(source, display); }

// A small table: columns [{key, label (tex allowed), digits}], rows of objects.
export function dataTable(columns, rows, { highlight = null } = {}) {
    const head = h('tr', {}, columns.map((c) => h('th', {}, label(c.label))));
    const body = rows.map((r, i) => h('tr', { class: i === highlight ? 'highlight' : (r.className || '') },
        columns.map((c) => {
            const v = r[c.key];
            const text = typeof v === 'number' ? (Number.isFinite(v) ? v.toFixed(c.digits ?? 2) : '—') : (v ?? '—');
            return h('td', {}, text);
        })));
    return h('table', { class: 'data-table' }, h('thead', {}, head), h('tbody', {}, body));
}

export { num };
