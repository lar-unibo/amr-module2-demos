// Composite widgets shared by the demos: canvas cards (3-D view, plane view,
// line plot), and the grid of cards under the stage.
import { LinePlot } from './plot.js';
import { PlaneView } from './plane.js';
import { View3D } from './view3d.js';
import { card, h, label, legend, seriesLegend } from './ui.js';
import { palette } from './theme.js';

function canvasCard(title, { note = '', guide = '', legendItems = null } = {}) {
    const c = card(title, note);
    const canvas = h('canvas', { class: 'view-canvas' });
    const toolbar = h('div', { class: 'toolbar' });
    if (guide) c.body.append(h('p', { class: 'interaction-guide' }, label(guide)));
    c.body.append(canvas);
    if (legendItems) c.body.append(legend(legendItems(palette())));
    c.body.append(toolbar);
    return { ...c, canvas, toolbar };
}

export function view3dCard(title, viewOptions = {}, cardOptions = {}) {
    const c = canvasCard(title, cardOptions);
    return { ...c, view: new View3D(c.canvas, viewOptions) };
}

export function planeCard(title, viewOptions = {}, cardOptions = {}) {
    const c = canvasCard(title, cardOptions);
    return { ...c, view: new PlaneView(c.canvas, viewOptions) };
}

export function plotCard(title, opts = {}, { note = '', size = '', legendItems = null } = {}) {
    const c = card(title, note);
    const canvas = h('canvas', { class: `plot-canvas ${size}` });
    c.body.append(canvas);
    let legendEl = null;
    const setLegend = (items) => {
        const next = seriesLegend(items);
        if (legendEl) legendEl.replaceWith(next); else c.body.append(next);
        legendEl = next;
    };
    if (legendItems) setLegend(legendItems);
    return { ...c, plot: new LinePlot(canvas, opts), setLegend };
}

export function plotsGrid(...cards) {
    return h('section', { class: 'plots' }, cards.map((x) => x.el));
}
