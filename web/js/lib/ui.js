// Small DOM toolkit: element builder, controls, readouts, cards.
import { renderMath } from './math.js';

// h('div', {class: 'card', onclick: fn}, child, 'text', ...)
export function h(tag, props = {}, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
        if (value === undefined || value === null || value === false) continue;
        if (key === 'class') el.className = value;
        else if (key === 'style') el.style.cssText = value;
        else if (key === 'html') el.innerHTML = value;
        else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
        else el.setAttribute(key, value === true ? '' : value);
    }
    for (const child of children.flat()) {
        if (child === null || child === undefined || child === false) continue;
        el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
}

// Inline maths inside labels: 'gain $\\alpha$' -> text + KaTeX span.
export function label(text) {
    const span = h('span');
    text.split(/(\$[^$]+\$)/).forEach((part) => {
        if (part.startsWith('$')) span.append(h('span', { class: 'tex' }, part.slice(1, -1)));
        else if (part) span.append(part);
    });
    renderMath(span);
    return span;
}

export function card(title, note = '') {
    const noteEl = h('span', { class: 'card-note' }, note ? label(note) : '');
    const body = h('div');
    const el = h('section', { class: 'card' },
        title ? h('div', { class: 'card-heading' }, h('h3', {}, label(title)), noteEl) : null, body);
    return { el, body, note: noteEl };
}

export function button(text, onClick, { primary = false, small = false, title } = {}) {
    const cls = ['button', primary && 'primary', small && 'small'].filter(Boolean).join(' ');
    const el = h('button', { class: cls, type: 'button', title, onclick: onClick });
    el.append(label(text));
    return el;
}

// slider({label: 'gain $\\alpha$', min, max, step, value, format, log, onInput})
export function slider({ label: text, description = '', min, max, step = 0.01, value, format = (v) => v.toFixed(2),
    log = false, onInput }) {
    const toInput = (v) => (log ? Math.log10(v) : v);
    const fromInput = (v) => (log ? 10 ** v : v);
    const input = h('input', { type: 'range', min: toInput(min), max: toInput(max), step: log ? 0.001 : step, value: toInput(value) });
    const output = h('output', {}, format(value));
    const el = h('div', { class: 'control' }, h('div', { class: 'control-head' }, h('label', {}, label(text)), output),
        description ? h('p', { class: 'control-help' }, label(description)) : null, input);
    const get = () => fromInput(Number(input.value));
    input.addEventListener('input', () => { output.textContent = format(get()); onInput?.(get()); });
    return {
        el, get,
        set(v) { input.value = toInput(v); output.textContent = format(v); },
        disable(flag) { input.disabled = flag; },
    };
}

// segmented({options: [{value, label}], value, onChange})
export function segmented({ options, value, onChange }) {
    const el = h('div', { class: 'segmented', role: 'group' });
    const buttons = options.map((opt) => {
        const b = h('button', { type: 'button', 'aria-pressed': String(opt.value === value) });
        b.append(label(opt.label));
        if (opt.color) b.style.color = opt.color;
        b.addEventListener('click', () => { set(opt.value); onChange?.(opt.value); });
        el.append(b);
        return b;
    });
    function set(v) { buttons.forEach((b, i) => b.setAttribute('aria-pressed', String(options[i].value === v))); }
    return { el, set };
}

export function toggle({ label: text, description = '', value = false, onChange }) {
    const input = h('input', { type: 'checkbox' });
    input.checked = value;
    input.addEventListener('change', () => onChange?.(input.checked));
    const switchEl = h('label', { class: 'switch' }, input, label(text));
    const el = description
        ? h('div', { class: 'control' }, switchEl, h('p', { class: 'control-help' }, label(description)))
        : switchEl;
    return { el, get: () => input.checked, set(v) { input.checked = v; } };
}

// readouts([{key, label}]) -> {el, set(key, text, tone)}
export function readouts(defs) {
    const values = {};
    const el = h('div', { class: 'readouts' }, defs.map((d) => {
        values[d.key] = h('strong', {}, d.value ?? '-');
        return h('div', { class: 'readout' }, h('span', {}, label(d.label)), values[d.key]);
    }));
    return {
        el,
        set(key, text, tone = '') { values[key].textContent = text; values[key].className = tone; },
    };
}

export function legend(items) {
    // items: [{label, color, kind: 'line'|'dashed'|'dot'|'ring'}]
    return h('div', { class: 'legend' }, items.map((it) => {
        const sw = h('i', { class: `swatch ${it.kind === 'line' ? '' : it.kind || ''}` });
        const item = h('span', { class: 'legend-item' }, sw, label(it.label));
        item.style.color = it.color;
        item.lastChild.style.color = 'var(--muted)';
        return item;
    }));
}

export function seriesLegend(items) {
    return h('div', { class: 'series-legend' }, items.map((it) => {
        const span = h('span', {}, h('i', { class: it.dash || '' }), label(it.label));
        span.firstChild.style.color = it.color;
        return span;
    }));
}

export function status() {
    const dot = h('i', { class: 'status-dot' });
    const text = h('span', {}, '');
    return {
        el: h('div', { class: 'status' }, dot, text),
        set(message, tone = '') { text.textContent = message; dot.className = `status-dot ${tone}`; },
    };
}

export function toast(message) {
    const el = h('div', { class: 'toast', role: 'alert' }, message);
    document.body.append(el);
    setTimeout(() => el.remove(), 6000);
}

export const fmt = (v, digits = 3) => (v === null || v === undefined || !Number.isFinite(v) ? '∞' : v.toFixed(digits));
export const pct = (v, digits = 0) => `${(100 * v).toFixed(digits)}%`;
