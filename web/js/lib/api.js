// The page's link to its Python session. The Python code runs in the browser,
// in a web worker with Pyodide (pyworker.js); there is no server, so the site
// can be served as static files (GitHub Pages, or `python serve.py`).
import { toast } from './ui.js';

let worker = null;
let nextId = 1;
const pending = new Map();
const listeners = new Set();
const opened = performance.now();
let readyAt = Infinity;
// pageReady: ms from page start to Python ready; lastCall: round trip of the
// latest request, counted from when Python was ready (not the boot wait).
export const runtime = { stage: 'idle', text: 'Python: not started', timings: {}, pageReady: null, lastCall: null };

function notify() { listeners.forEach((fn) => fn(runtime)); }

// Start Python as early as possible (the demo page calls this first).
export function warmUp() {
    if (worker) return;
    worker = new Worker(new URL('./pyworker.js', import.meta.url), { type: 'module' });
    worker.onmessage = ({ data }) => {
        if (data.status) {
            Object.assign(runtime, data.status);
            if (data.status.stage === 'ready') {
                readyAt = performance.now();
                runtime.pageReady = readyAt - opened;
            }
            notify();
            return;
        }
        const entry = pending.get(data.id);
        if (!entry) return;
        pending.delete(data.id);
        runtime.lastCall = performance.now() - Math.max(entry.sent, readyAt);
        notify();
        if (data.ok) entry.resolve(data.result); else entry.reject(new Error(data.error));
    };
    worker.onerror = (event) => {
        Object.assign(runtime, { stage: 'error', text: `Python worker error: ${event.message || 'unknown'}` });
        notify();
        for (const entry of pending.values()) entry.reject(new Error(runtime.text));
        pending.clear();
    };
    runtime.stage = 'loading';
    runtime.text = 'Python: loading…';
    notify();
}

export function onRuntime(fn) { listeners.add(fn); fn(runtime); }

async function request(message) {
    warmUp();
    const text = await new Promise((resolve, reject) => {
        const id = nextId++;
        pending.set(id, { resolve, reject, sent: performance.now() });
        worker.postMessage({ id, ...message });
    }).catch((error) => { toast(error.message); throw error; });
    const data = JSON.parse(text);
    if (data && typeof data === 'object' && 'error' in data && Object.keys(data).length === 1) {
        toast(data.error);
        throw new Error(data.error);
    }
    return data;
}

export class Session {
    static async start(demoId, options = {}) {
        const { session, state } = await request({ type: 'start', demo: demoId, options });
        return { session: new Session(session), state };
    }

    constructor(token) { this.token = token; }

    call(action, payload = {}) {
        return request({ type: 'call', token: this.token, action, payload });
    }

    // For continuous input (drags, sliders): at most one request in flight;
    // while it runs, only the newest payload is kept. onResult gets each answer.
    stream(action, onResult) {
        let busy = false;
        let queued = null;
        const send = async (payload) => {
            busy = true;
            try { onResult(await this.call(action, payload)); } catch { /* reported by request */ }
            busy = false;
            if (queued) { const next = queued; queued = null; send(next); }
        };
        return (payload) => { if (busy) queued = payload; else send(payload); };
    }
}

// The course structure (written by tools/build_site.py): no Python needed.
export async function catalog() {
    const response = await fetch('catalog.json');
    return response.json();
}
