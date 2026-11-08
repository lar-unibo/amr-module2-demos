// The "⋯" menu of the top bar: a link to the current view, and figure and
// animation export.
import { h } from './ui.js';

const pad2 = (n) => String(n).padStart(2, '0');

async function copy(text, button) {
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const area = h('textarea', { style: 'position:fixed;opacity:0' });
        area.value = text;
        document.body.append(area);
        area.select();
        document.execCommand('copy');
        area.remove();
    }
    toastCopied(button);
}

function toastCopied(button) {
    const note = h('span', { class: 'copied-note' }, 'Link copied ✓');
    (button?.parentElement || document.body).append(note);
    setTimeout(() => note.remove(), 1600);
}

// ------------------------------------------------------------------ figure and animation export
// One image of the workspace canvases at their places on screen, without the
// controls between them: empty horizontal bands (toolbars, sliders) collapse
// to a small gap, so the figure keeps the arrangement of the demo.
function composer(root) {
    const canvases = [...root.querySelectorAll('canvas')].filter((c) => c.clientWidth > 0 && c.clientHeight > 0);
    if (!canvases.length) return null;
    const GAP = 12;
    const boxes = canvases.map((c) => {
        const r = c.getBoundingClientRect();
        return { c, x: r.left + c.clientLeft, y: r.top + c.clientTop, w: c.clientWidth, h: c.clientHeight };
    });
    const bands = [];
    for (const b of [...boxes].sort((a, z) => a.y - z.y)) {
        const last = bands[bands.length - 1];
        if (last && b.y <= last.y1) last.y1 = Math.max(last.y1, b.y + b.h);
        else bands.push({ y0: b.y, y1: b.y + b.h });
    }
    let y = GAP;
    for (const band of bands) { band.top = y; y += band.y1 - band.y0 + GAP; }
    for (const b of boxes) {
        const band = bands.find((s) => b.y >= s.y0 && b.y < s.y1 + 0.5);
        b.y = band.top + b.y - band.y0;
    }
    const x0 = Math.min(...boxes.map((b) => b.x)) - GAP;
    const width = Math.max(...boxes.map((b) => b.x + b.w)) + GAP - x0, height = y;
    const scale = Math.max(1, ...canvases.map((c) => c.width / c.clientWidth));
    const out = document.createElement('canvas');
    out.width = 2 * Math.round(width * scale / 2);          // even sizes suit video encoders
    out.height = 2 * Math.round(height * scale / 2);
    const ctx = out.getContext('2d');
    const background = getComputedStyle(root).getPropertyValue('--surface').trim() || '#ffffff';
    const draw = () => {
        ctx.setTransform(out.width / width, 0, 0, out.height / height, 0, 0);
        ctx.fillStyle = background;
        ctx.fillRect(0, 0, width, height);
        for (const b of boxes) ctx.drawImage(b.c, b.x - x0, b.y, b.w, b.h);
    };
    draw();
    return { canvas: out, draw };
}

function download(blob, name) {
    const url = URL.createObjectURL(blob);
    const link = h('a', { href: url, download: name });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function savePng(root, name) {
    composer(root)?.canvas.toBlob((blob) => blob && download(blob, `${name}.png`), 'image/png');
}

const VIDEO_TYPES = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm', 'video/mp4'];
const MAX_SECONDS = 60;
const videoType = () => (window.MediaRecorder && HTMLCanvasElement.prototype.captureStream
    ? VIDEO_TYPES.find((t) => MediaRecorder.isTypeSupported(t)) : undefined);
let recording = null;

// Records the composed canvases until the user stops (or MAX_SECONDS), then saves the video.
function startRecording(root, name) {
    const type = videoType(), frame = composer(root);
    if (!type || !frame) return;
    const recorder = new MediaRecorder(frame.canvas.captureStream(30), { mimeType: type, videoBitsPerSecond: 8e6 });
    const chunks = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    const clock = h('span', {}, 'REC 0:00');
    const pill = h('button', { class: 'rec-pill', type: 'button', title: 'Stop recording and save the video' },
        h('i', { class: 'rec-dot', 'aria-hidden': 'true' }), clock, h('span', { class: 'rec-stop' }, 'Stop'));
    const started = performance.now();
    let raf = 0;
    const loop = () => { frame.draw(); raf = requestAnimationFrame(loop); };
    const timer = setInterval(() => {
        const s = Math.floor((performance.now() - started) / 1000);
        clock.textContent = `REC ${Math.floor(s / 60)}:${pad2(s % 60)}`;
        if (s >= MAX_SECONDS) stop();
    }, 250);
    function stop() { if (recorder.state !== 'inactive') recorder.stop(); }
    recorder.onstop = () => {
        cancelAnimationFrame(raf);
        clearInterval(timer);
        pill.remove();
        recording = null;
        download(new Blob(chunks, { type }), `${name}.${type.startsWith('video/mp4') ? 'mp4' : 'webm'}`);
    };
    pill.addEventListener('click', stop);
    document.body.append(pill);
    loop();
    recorder.start(500);
    recording = { stop };
}

// ------------------------------------------------------------------ the menu
export function initTools(button, { demo = null, workspace = null } = {}) {
    if (!button) return;
    const wrap = h('span', { class: 'tools' });
    button.replaceWith(wrap);
    const menu = h('div', { class: 'tools-menu', role: 'menu', id: 'toolsMenu', hidden: true, 'aria-label': 'More options' });
    wrap.append(button, menu);
    button.setAttribute('aria-haspopup', 'menu');
    button.setAttribute('aria-controls', 'toolsMenu');
    button.setAttribute('aria-expanded', 'false');
    const name = demo ? `lecture${pad2(demo.lectureNumber)}-demo${pad2(demo.number)}-${demo.id}` : 'course-demos';

    const item = (icon, text, onSelect, { checked, title, disabled = false } = {}) => {
        const el = h('button', {
            type: 'button', role: checked === undefined ? 'menuitem' : 'menuitemcheckbox',
            'aria-checked': checked === undefined ? null : String(checked), title, disabled, tabindex: '-1',
        }, h('span', { class: 'tools-icon', 'aria-hidden': 'true' }, icon), h('span', {}, text));
        el.addEventListener('click', () => { close(); onSelect(); });
        return el;
    };

    function render() {
        const entries = [item('🔗', demo ? 'Copy link to this view' : 'Copy link to this page',
            () => copy(location.href, button), { title: 'Paste it in slides or notes' })];
        if (demo && workspace) {
            const canExport = !!workspace.querySelector('canvas');
            entries.push(
                item('⤓', 'Save figure (PNG)', () => savePng(workspace, name),
                    { disabled: !canExport, title: 'The canvases of this demo as one image, without the controls' }),
                recording
                    ? item('■', 'Stop recording', () => recording?.stop())
                    : item('●', 'Record animation', () => startRecording(workspace, name),
                        { disabled: !canExport || !videoType(),
                            title: videoType() ? `Record the canvases as a video (up to ${MAX_SECONDS} s); stop with the REC button`
                                : 'Video recording is not supported by this browser' }));
        }
        menu.replaceChildren(...entries);
    }

    const items = () => [...menu.querySelectorAll('button:not(:disabled)')];
    const onOutside = (event) => { if (!wrap.contains(event.target)) close(); };
    function open() {
        render();
        menu.hidden = false;
        button.setAttribute('aria-expanded', 'true');
        document.addEventListener('pointerdown', onOutside);
        items()[0]?.focus();
    }
    function close(refocus = false) {
        if (menu.hidden) return;
        menu.hidden = true;
        button.setAttribute('aria-expanded', 'false');
        document.removeEventListener('pointerdown', onOutside);
        if (refocus) button.focus();
    }
    button.addEventListener('click', () => (menu.hidden ? open() : close()));
    menu.addEventListener('keydown', (event) => {
        const list = items(), i = list.indexOf(document.activeElement);
        const moves = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: list.length - 1 };
        if (event.key in moves) {
            event.preventDefault();
            list[(moves[event.key] + list.length) % list.length]?.focus();
        } else if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();
            close(true);
        } else if (event.key === 'Tab') {
            close();
        }
    });
}
