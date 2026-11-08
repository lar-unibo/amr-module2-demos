// The menu: one section per lecture, one card per demo, in course order.
import { catalog } from './lib/api.js';
import { renderMath } from './lib/math.js';
import { initTheme, toggleTheme } from './lib/theme.js';
import { initTools } from './lib/tools.js';
import { h, label } from './lib/ui.js';

initTheme();
document.getElementById('themeButton').addEventListener('click', toggleTheme);
initTools(document.getElementById('toolsButton'));

const pad2 = (n) => String(n).padStart(2, '0');
const data = await catalog();
const { course, lectures } = data;
document.title = course.title;
document.getElementById('brandTitle').textContent = course.title;
document.getElementById('courseTitle').textContent = course.title;
document.getElementById('courseKicker').textContent = course.subtitle;
document.getElementById('courseByline').replaceChildren(
    [course.author, course.affiliation, course.programme].filter(Boolean).join(' · '),
    ...(course.url ? [' · ', h('a', { href: course.url, target: '_blank', rel: 'noopener' }, 'course page')] : []));

const root = document.getElementById('lectures');
for (const lecture of lectures) {
    const heading = h('div', { class: 'part-heading' },
        h('h2', { id: `lecture${lecture.number}` }, h('span', { class: 'part-tag' }, `Lecture ${lecture.number}`), lecture.title),
        h('p', {}, lecture.summary));
    const cards = lecture.demos.length
        ? h('div', { class: 'card-grid' }, lecture.demos.map((demo) => h('a', { class: 'demo-card', href: `demo.html?id=${demo.id}` },
            h('div', { class: 'demo-card-body' },
                h('div', { class: 'demo-card-top' },
                    h('span', { class: 'demo-index' }, pad2(demo.number)),
                    h('h3', {}, demo.title)),
                h('p', {}, label(demo.summary)),
                h('div', { class: 'concepts' },
                    demo.slides ? h('span', { class: 'slide-ref' }, `slides ${demo.slides.replace('-', '–')}`) : null,
                    demo.concepts.map((c) => h('span', { class: 'concept' }, label(c))))))))
        : h('p', { class: 'lecture-empty' }, 'Demos for this lecture are in preparation.');
    root.append(h('section', { class: 'part', 'aria-labelledby': `lecture${lecture.number}` }, heading, cards));
}
renderMath(document);

// Warm the browser cache with the Python runtime while the menu is open, so the
// first demo starts faster (the files are not executed here).
const vendor = 'vendor/pyodide/';
fetch(`${vendor}pyodide-lock.json`).then((r) => r.json()).then((lock) => {
    const files = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip',
        ...Object.values(lock.packages).map((p) => p.file_name)];
    for (const file of files) document.head.append(h('link', { rel: 'prefetch', href: vendor + file }));
}).catch(() => { /* prefetching is optional */ });
