// Translates the text that is written straight into pages (not through t()). Each language has a phrase list in
// ./phrases/<code>.json that maps the English wording to the translation. While a language other than English is
// chosen, every text node and the placeholder, title, aria-label and alt attributes on the page are looked up in that list
// (exact wording, ignoring spaces around it) and swapped. Wording with no entry stays English. Choosing English puts every
// original back. Add a phrase by adding it to the file for each language; see scripts/i18n_extract.py for finding the gaps.
const loaders = import.meta.glob('./phrases/*.json');

const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'] as const;
const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'CODE', 'PRE', 'NOSCRIPT']);

type Phrases = Record<string, string>;
const cache = new Map<string, Phrases>();
let phrases: Phrases | null = null;
let observer: MutationObserver | null = null;
let wording: ((text: string) => string) | null = null;                // the school's regional wording (Date Sheet -> Exam Schedule)

/** Give the school's regional wording a way to rewrite page text before it is translated (see utils/region.ts). */
export function setRegionWording(fn: ((text: string) => string) | null) { wording = fn; }

// What each node showed in English, and what we put there, so we can tell our own writes from the page's.
const textOriginal = new WeakMap<Text, { en: string; shown: string }>();
const attrOriginal = new WeakMap<Element, Map<string, { en: string; shown: string }>>();

const lookup = (en: string): string | null => {
  if (!phrases) return null;
  const core = en.trim();
  if (!core) return null;
  const hit = phrases[core] ?? phrases[core.replace(/\s+/g, ' ')];
  if (!hit || hit === core) return null;
  return (en.match(/^\s*/)?.[0] ?? '') + hit + (en.match(/\s*$/)?.[0] ?? '');
};

const skipped = (el: Element | null): boolean => {
  for (let n = el; n; n = n.parentElement) {
    if (SKIP.has(n.tagName) || n.getAttribute('translate') === 'no' || n.hasAttribute('data-no-translate')) return true;
  }
  return false;
};

/** What this English wording shows as right now: regional wording first, then the chosen language (null = leave it). */
function render(en: string): string | null {
  const local = wording ? wording(en) : en;
  const out = phrases ? (lookup(local) ?? lookup(en)) : null;
  if (out !== null) return out;
  return local !== en ? local : null;
}

function doText(node: Text) {
  const known = textOriginal.get(node);
  const current = node.nodeValue ?? '';
  const en = known && current === known.shown ? known.en : current;     // the page changed it: that is the new English
  const out = render(en);
  if (out === null) {
    if (known && known.shown !== en) { node.nodeValue = en; }
    if (known) textOriginal.delete(node);
    return;
  }
  if (out !== current) node.nodeValue = out;
  textOriginal.set(node, { en, shown: out });
}

function doAttrs(el: Element) {
  for (const name of ATTRS) {
    const current = el.getAttribute(name);
    if (current === null) continue;
    const mem = attrOriginal.get(el)?.get(name);
    const en = mem && current === mem.shown ? mem.en : current;
    const out = render(en);
    if (out === null) {
      if (mem) { if (mem.shown !== en) el.setAttribute(name, en); attrOriginal.get(el)?.delete(name); }
      continue;
    }
    if (out !== current) el.setAttribute(name, out);
    const map = attrOriginal.get(el) ?? new Map();
    map.set(name, { en, shown: out });
    attrOriginal.set(el, map);
  }
}

function walk(root: Node) {
  if (root.nodeType === Node.TEXT_NODE) {
    if (!skipped(root.parentElement)) doText(root as Text);
    return;
  }
  if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;
  const el = root as Element;
  if (el.nodeType === Node.ELEMENT_NODE && skipped(el)) return;
  const tree = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  if (el.nodeType === Node.ELEMENT_NODE) doAttrs(el);
  for (let n = tree.nextNode(); n; n = tree.nextNode()) {
    if (n.nodeType === Node.TEXT_NODE) { if (!skipped(n.parentElement)) doText(n as Text); }
    else if (!skipped(n as Element)) doAttrs(n as Element);
  }
}

function watch() {
  if (observer || typeof MutationObserver === 'undefined') return;
  observer = new MutationObserver((records) => {
    observer?.disconnect();                                        // our own edits must not loop back in
    try {
      for (const r of records) {
        if (r.type === 'characterData') { if (!skipped(r.target.parentElement)) doText(r.target as Text); }
        else if (r.type === 'attributes') { if (!skipped(r.target as Element)) doAttrs(r.target as Element); }
        else r.addedNodes.forEach(walk);
      }
    } finally { connect(); }
  });
  connect();
}

function connect() {
  observer?.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...ATTRS] });
}

async function load(code: string): Promise<Phrases | null> {
  if (code === 'en') return null;
  if (cache.has(code)) return cache.get(code)!;
  const loader = loaders[`./phrases/${code}.json`];
  if (!loader) return null;
  const mod = (await loader()) as { default: Phrases };
  cache.set(code, mod.default);
  return mod.default;
}

/** Use this language's phrase list for the text written into pages (English restores the original wording). */
export async function applyPageText(code: string) {
  if (typeof document === 'undefined') return;
  phrases = await load(code);
  refreshPageText();
}

/** Look at the whole page again (after a language or region change). */
export function refreshPageText() {
  if (typeof document === 'undefined' || !document.body) return;
  if (observer) observer.disconnect();
  walk(document.body);
  watch();
  if (observer) connect();
}

/** For tests: how many phrases a language has. */
export const phraseCount = (code: string) => Object.keys(cache.get(code) ?? {}).length;
