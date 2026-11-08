// Demo page: lesson on the left (lessons/<id>.html), interactive workspace on
// the right (js/demos/<id>.js), backed by a Python session running in the
// browser (lib/api.js). Python starts first, while the page is assembled.
import { catalog, onRuntime, Session, warmUp } from './lib/api.js';
import { renderMath } from './lib/math.js';
import { initTheme, toggleTheme } from './lib/theme.js';
import { initTools } from './lib/tools.js';

warmUp();
initTheme();
document.getElementById('themeButton').addEventListener('click', toggleTheme);

// The lesson column can be hidden; the choice is remembered in this browser.
const LESSON_KEY = 'course-demos-lesson';
const lessonToggle = document.getElementById('lessonToggle');
function setLesson(open) {
    document.documentElement.classList.toggle('lesson-hidden', !open);
    lessonToggle.setAttribute('aria-expanded', String(open));
    lessonToggle.textContent = open ? '◧ Hide lesson' : '◨ Show lesson';
    try { localStorage.setItem(LESSON_KEY, open ? 'open' : 'closed'); } catch { /* storage unavailable */ }
}
let lessonOpen = true;
try { lessonOpen = localStorage.getItem(LESSON_KEY) !== 'closed'; } catch { /* storage unavailable */ }
setLesson(lessonOpen);
lessonToggle.addEventListener('click', () => setLesson(document.documentElement.classList.contains('lesson-hidden')));

// Runtime status in the top bar, with the timings (visible on any device).
const pill = document.getElementById('runtimePill');
const seconds = (ms) => `${(ms / 1000).toFixed(1)} s`;
onRuntime((r) => {
    pill.className = `runtime-pill ${r.stage === 'ready' ? 'ready' : r.stage === 'error' ? 'error' : 'loading'}`;
    let text = r.text;
    if (r.stage === 'ready' && r.pageReady !== null) {
        text = `Python ready in ${seconds(r.pageReady)}` + (r.lastCall !== null ? ` · ${r.lastCall.toFixed(0)} ms per update` : '');
        document.documentElement.dataset.pyReadyMs = String(Math.round(r.pageReady));
    }
    pill.lastChild.textContent = text;
    const t = r.timings || {};
    pill.title = `Python (Pyodide ${t.version || ''}) runs in this browser.\n`
        + `Inside the worker: runtime ${t.runtime ?? '-'} ms, numpy ${t.numpy ?? '-'} ms, ready ${t.ready ?? '-'} ms.`;
    const loading = document.getElementById('pyLoadingText');
    if (loading && r.stage !== 'idle') loading.textContent = r.text;
});

const pad2 = (n) => String(n).padStart(2, '0');
const { course, lectures } = await catalog();
const demos = lectures.flatMap((lecture) => lecture.demos.map((d) => ({ ...d, lectureNumber: lecture.number, lectureTitle: lecture.title })));
const requested = new URLSearchParams(location.search).get('id');
const index = Math.max(0, demos.findIndex((d) => d.id === requested));
const demo = demos[index];
const prev = demos[index - 1], next = demos[index + 1];

document.title = `${demo.title} · ${course.title}`;
const slides = demo.slides ? ` · slides ${demo.slides.replace('-', '–')}` : '';
document.getElementById('topbarTitle').innerHTML = `<span class="part-tag">Lecture ${demo.lectureNumber}</span>${demo.lectureTitle} · <strong>${pad2(demo.number)} ${demo.title}</strong>`;
document.getElementById('lessonKicker').textContent = `Lecture ${demo.lectureNumber} · ${demo.lectureTitle} · Demo ${pad2(demo.number)}${slides}`;
document.getElementById('lessonTitle').textContent = demo.title;
document.getElementById('lessonIntro').textContent = demo.summary.replace(/\$/g, '');

for (const [id, target, text] of [['prevDemo', prev, '◀ Previous'], ['prevLesson', prev, '◀ Previous'],
    ['nextDemo', next, 'Next ▶'], ['nextLesson', next, 'Next demo ▶']]) {
    const link = document.getElementById(id);
    if (target) { link.href = `demo.html?id=${target.id}`; link.title = target.title; link.textContent = text; }
    else if (id.startsWith('next')) { link.href = 'index.html'; link.textContent = 'Back to all demos'; }
    else link.style.visibility = 'hidden';
}
const workspace = document.getElementById('workspace');
initTools(document.getElementById('toolsButton'), { demo, workspace });

const lessonBody = document.getElementById('lessonBody');
lessonBody.innerHTML = await (await fetch(`lessons/${demo.id}.html`)).text();
renderMath(lessonBody);

const module = await import(`./demos/${demo.id}.js`);
const options = Object.fromEntries(new URLSearchParams(location.search));
const { session, state } = await Session.start(demo.id);
document.getElementById('pyLoading')?.remove();
await module.mount({ workspace, lesson: lessonBody, session, state, demo, options });
document.documentElement.dataset.demoMounted = '1';
