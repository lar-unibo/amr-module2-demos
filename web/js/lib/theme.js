// Light / dark theme (light by default; the choice is remembered in this
// browser), and the colour palette read from the CSS variables, so canvases
// and HTML always share one set of colours.

const KEY = 'course-demos-theme';
const listeners = new Set();
let cached = null;

export function initTheme() {
    let saved = null;
    try { saved = localStorage.getItem(KEY); } catch { /* storage unavailable */ }
    document.documentElement.dataset.theme = saved === 'dark' ? 'dark' : 'light';
}

export function toggleTheme() {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(KEY, next); } catch { /* storage unavailable */ }
    cached = null;
    listeners.forEach((fn) => fn());
}

export function onThemeChange(fn) { listeners.add(fn); }

const NAMES = ['bg', 'surface', 'surface-soft', 'ink', 'ink-soft', 'muted', 'line', 'line-strong',
    'accent', 'accent-strong', 'accent-soft', 'canvas', 'grid', 'grid-strong', 'robot', 'robot-deep',
    'joint', 'rod', 'feature', 'feature-ring', 'target', 'target-point', 'grip-l', 'grip-r', 'red',
    'aqua', 'green', 'rep-points', 'rep-edges', 'rep-angles', 'div-neg', 'div-pos', 'div-mid'];

// palette().rod, palette().red, ... (CSS names in camelCase), read from the
// CSS variables of the element's context.
export function palette(el = document.documentElement) {
    const host = (el && el.closest && el.closest('[data-part]')) || document.documentElement;
    const key = host.dataset.part || 'root';
    if (!cached) cached = new Map();
    if (cached.has(key)) return cached.get(key);
    const style = getComputedStyle(host);
    const p = { dark: document.documentElement.dataset.theme === 'dark' };
    for (const name of NAMES) {
        const name2 = name.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        p[name2] = style.getPropertyValue(`--${name}`).trim();
    }
    // One colour per robot coordinate, left gripper violet tones, right orange.
    p.dof = p.dark
        ? ['#8d80ee', '#b3aaf5', '#6b5ed6', '#f08a5a', '#f5b08f', '#d9692f']
        : ['#4a3aa7', '#8a7fd6', '#2e2270', '#eb6834', '#f2a07c', '#b84a1c'];
    // Plot series.
    p.series = p.dark
        ? ['#4b93ea', '#2bbd88', '#f2b52a', '#4caf63', '#8d80ee', '#ec6b6a']
        : ['#2a78d6', '#1baf7a', '#eda100', '#2e8540', '#4a3aa7', '#e34948'];
    cached.set(key, p);
    return p;
}

// colour helpers
const toRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
export function mix(a, b, t) {
    const x = toRgb(a), y = toRgb(b);
    return '#' + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, '0')).join('');
}
export function alpha(hex, a) {
    const [r, g, b] = toRgb(hex);
    return `rgba(${r}, ${g}, ${b}, ${a})`;
}
