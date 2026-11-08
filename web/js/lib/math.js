// Equations with KaTeX (vendored, offline), with macros for the notation of
// the lecture slides, so that lessons and labels can quote the slides.

export const MACROS = {
    '\\R': '\\mathbb{R}',
    '\\norm': '\\lVert #1 \\rVert',
    '\\vs': '\\mathbf{s}', '\\ve': '\\mathbf{e}', '\\vv': '\\mathbf{v}', '\\vx': '\\mathbf{x}',
    '\\vL': '\\mathbf{L}', '\\vP': '\\mathbf{P}', '\\vI': '\\mathbf{I}', '\\vR': '\\mathbf{R}',
    '\\vt': '\\mathbf{t}', '\\vT': '\\mathbf{T}', '\\vm': '\\mathbf{m}', '\\vM': '\\mathbf{M}',
    '\\Lhp': '\\widehat{\\mathbf{L}^{+}}',
    '\\vK': '\\mathbf{K}', '\\vC': '\\mathbf{C}', '\\vH': '\\mathbf{H}', '\\vB': '\\mathbf{B}',
    '\\vA': '\\mathbf{A}', '\\vX': '\\mathbf{X}', '\\vh': '\\mathbf{h}', '\\vr': '\\mathbf{r}', '\\vp': '\\mathbf{p}',
    '\\Null': '\\operatorname{Null}', '\\Range': '\\operatorname{Range}',
    '\\rank': '\\operatorname{rank}', '\\Sym': '\\operatorname{Sym}',
};

export function tex(source, display = false) {
    return window.katex.renderToString(source, {
        displayMode: display, macros: { ...MACROS }, throwOnError: false, strict: 'ignore',
    });
}

// Render every <span class="tex"> (inline) and <div class="tex-block"> (display)
// below root, once.
export function renderMath(root = document) {
    for (const el of root.querySelectorAll('.tex, .tex-block')) {
        if (el.dataset.rendered) continue;
        el.innerHTML = tex(el.textContent, el.classList.contains('tex-block'));
        el.dataset.rendered = '1';
    }
}
