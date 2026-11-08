// Web worker that runs the course's Python code (course/ and sessions/) with
// Pyodide, off the page's main thread. Messages from the page:
//     {id, type: 'start', demo, options}            -> sessions.runtime.start
//     {id, type: 'call', token, action, payload}    -> sessions.runtime.call
// Replies: {id, ok, result: <JSON text>, ms} or {id, ok: false, error}.
// Progress while booting: {status: {stage, text, timings}}.
import { loadPyodide } from '../../vendor/pyodide/pyodide.mjs';

const t0 = performance.now();
const timings = {};
const APP = '/home/pyodide/app';
const here = (path) => new URL(path, import.meta.url).href;
const elapsed = () => Math.round(performance.now() - t0);
const status = (stage, text) => self.postMessage({ status: { stage, text, timings: { ...timings } } });

// The Python sources are fetched while Pyodide starts.
const sources = (async () => {
    const manifest = await (await fetch(here('../../py/manifest.json'))).json();
    return Promise.all(manifest.files.map(async (file) => {
        const response = await fetch(here(`../../py/${file}`));
        if (!response.ok) throw new Error(`cannot load py/${file} (${response.status})`);
        return [file, await response.text()];
    }));
})();

let runtime = null;
const booted = (async () => {
    status('runtime', 'Python: starting…');
    const pyodide = await loadPyodide({ indexURL: here('../../vendor/pyodide/') });
    timings.runtime = elapsed();
    status('numpy', 'Python: loading numpy…');
    await pyodide.loadPackage('numpy', { messageCallback: () => {} });
    timings.numpy = elapsed();
    for (const [file, text] of await sources) {
        const path = `${APP}/${file}`;
        pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf('/')));
        pyodide.FS.writeFile(path, text);
    }
    pyodide.runPython(`import sys\nsys.path.insert(0, ${JSON.stringify(APP)})`);
    runtime = pyodide.pyimport('sessions.runtime');
    timings.ready = elapsed();
    timings.version = pyodide.version;
    status('ready', 'Python ready');
})();
booted.catch((error) => status('error', `Python failed to start: ${error?.message || error}`));

self.onmessage = async ({ data }) => {
    const { id, type } = data;
    try {
        await booted;
        const t = performance.now();
        let result;
        if (type === 'start') result = runtime.start(data.demo, JSON.stringify(data.options ?? {}));
        else if (type === 'call') result = runtime.call(data.token, data.action, JSON.stringify(data.payload ?? {}));
        else throw new Error(`unknown request: ${type}`);
        self.postMessage({ id, ok: true, result, ms: performance.now() - t });
    } catch (error) {
        self.postMessage({ id, ok: false, error: String(error?.message || error) });
    }
};
