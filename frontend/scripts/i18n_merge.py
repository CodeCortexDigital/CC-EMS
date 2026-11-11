"""Merge translated phrase files into src/i18n/phrases/<lang>.json and report anything suspect.

    python scripts/i18n_merge.py <folder with <lang>_<chunk>*.json files> <chunks folder with c*.json>

Checks every English phrase has a translation, that {placeholders} and %s survive, that nothing is empty, and that the
translation is not just the English echoed back (those are counted, since some phrases are meant to stay the same).
"""
import glob
import json
import os
import re
import sys

OUT, CHUNKS = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, '..', 'src', 'i18n', 'phrases')
LANGS = ['es', 'pt', 'fr', 'de', 'ar', 'ja']
ph = re.compile(r'\{[^}]*\}|%[sd]')

english = []
for f in sorted(glob.glob(os.path.join(CHUNKS, '*.json'))):
    english += json.load(open(f, encoding='utf8'))

for lang in LANGS:
    path = os.path.join(DEST, f'{lang}.json')
    merged = json.load(open(path, encoding='utf8')) if os.path.exists(path) else {}
    for f in sorted(glob.glob(os.path.join(OUT, f'{lang}_*.json'))):
        try:
            merged.update(json.load(open(f, encoding='utf8')))
        except Exception as e:
            print(lang, 'BAD FILE', os.path.basename(f), e)
    missing = [e for e in english if e not in merged]
    empty = [k for k, v in merged.items() if not str(v).strip()]
    broken = [k for k, v in merged.items() if sorted(ph.findall(k)) != sorted(ph.findall(str(v)))]
    same = sum(1 for k in english if merged.get(k) == k)
    for k in empty + broken:
        merged.pop(k, None)                                  # never ship an empty or placeholder-broken entry
    json.dump(dict(sorted(merged.items())), open(path, 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print(f'{lang}: {len(merged)} phrases, missing {len(missing)}, empty {len(empty)}, placeholder-broken {len(broken)}, unchanged {same}')
