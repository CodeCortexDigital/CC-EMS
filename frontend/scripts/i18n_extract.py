"""Collect UI text that is hardcoded in the frontend: JSX text, text-bearing props, and label-like string literals."""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
OUT = sys.argv[1]
SKIP_DIRS = {'i18n', 'test', 'node_modules'}

jsx_text = re.compile(r'>\s*([^<>{}\n][^<>{}]*?)\s*<')
jsx_text_multi = re.compile(r'>\n\s*([A-Za-z][^<>{}\n]{2,})\n')
prop = re.compile(r'\b(?:placeholder|title|aria-label|alt|label|hint|description|text|message|emptyText|helperText|heading|subtitle|tooltip|name)\s*[:=]\s*[\'"]([^\'"\n]{2,90})[\'"]')
# A quoted string never contains its own quote, so a match cannot run on into the next string.
lit = re.compile(r"""(?<![\w$.\-/])(?:'([A-Z][^'\n\\]{2,300})'|"([A-Z][^"\n\\]{2,300})"|`([A-Z][^`$\n\\]{2,300})`)""")
# anything that is clearly code or a class list
bad = re.compile(r'(https?:|/api/|\.tsx?|\bclassName\b|^[A-Z_]{2,}$|^[A-Z][a-z]+[A-Z]\w+$|\$\{|=>|^\d|\bpx\b|^(?:GET|POST|PUT|PATCH|DELETE)$|^Bearer)')
cls = re.compile(r'\b(?:flex|grid|text-|bg-|px-|py-|rounded|border|w-\d|h-\d|gap-|items-|justify-|font-)')


def ok(s):
    s = s.strip()
    if len(s) < 3 or len(s) > 300:
        return False
    if bad.search(s) or cls.search(s):
        return False
    if not re.search(r'[A-Za-z]{3}', s):
        return False
    if s.islower() and ' ' not in s:      # identifiers like 'pending', 'asc'
        return False
    if re.fullmatch(r'[a-z]+(?:[-_][a-z]+)+', s):
        return False
    if re.search(r'[{}<>;=]', s):
        return False
    return True


found = {}
for dp, dn, fn in os.walk(ROOT):
    dn[:] = [d for d in dn if d not in SKIP_DIRS]
    for f in fn:
        if not f.endswith(('.tsx', '.ts')) or '.test.' in f or f.endswith('.d.ts'):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT).replace('\\', '/')
        src = open(p, encoding='utf8').read()
        tsx = f.endswith('.tsx')
        cands = []
        if tsx:
            cands += jsx_text.findall(src) + jsx_text_multi.findall(src)
        cands += prop.findall(src)
        cands += [next(g for g in m.groups() if g) for m in lit.finditer(src)]
        for c in cands:
            c = re.sub(r'\s+', ' ', c).strip()
            if ok(c):
                found.setdefault(c, set()).add(rel.split('/')[0])

items = sorted(found)
json.dump(items, open(OUT, 'w', encoding='utf8'), ensure_ascii=False, indent=0)
print(len(items), 'phrases')
