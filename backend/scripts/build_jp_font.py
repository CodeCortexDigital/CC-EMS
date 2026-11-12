"""Builds the two small Japanese fonts used by server-made PDFs (backend/assets/fonts/NotoSansJP-Regular.ttf and -Bold.ttf).

Source: Noto Sans JP, variable font, SIL Open Font License 1.1 (https://github.com/google/fonts/tree/main/ofl/notosansjp).
Run once when the font changes (needs `pip install fonttools`):

    python scripts/build_jp_font.py path/to/NotoSansJP[wght].ttf

It keeps the characters a school needs: Basic Latin, Latin-1, general punctuation, kana, CJK symbols, full-width forms, and every
kanji and symbol in JIS X 0208 (level 1 and 2, about 6,350 characters). Anything else prints as a blank box, which is the known limit.
"""
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'


def jis_x_0208() -> set[str]:
    chars: set[str] = set()
    for lead in range(0x81, 0xFD):
        for trail in range(0x40, 0xFD):
            try:
                ch = bytes([lead, trail]).decode('shift_jis')
            except UnicodeDecodeError:
                continue
            if len(ch) == 1:
                chars.add(ch)
    return chars


def wanted() -> list[int]:
    cps = set(range(0x20, 0x7F)) | set(range(0xA0, 0x100)) | set(range(0x2000, 0x2070))
    cps |= set(range(0x3000, 0x3100)) | set(range(0xFF00, 0xFFF0)) | {0x00A5, 0x20AC, 0x2022, 0x25CF}
    cps |= {ord(c) for c in jis_x_0208()}
    return sorted(cps)


def build(src: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, weight in (('Regular', 400), ('Bold', 700)):
        font = TTFont(src)
        font = instancer.instantiateVariableFont(font, {'wght': weight})
        opts = subset.Options()
        opts.layout_features = ['kern', 'palt', 'vert']
        opts.notdef_outline = True
        opts.name_IDs = ['*']
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=wanted())
        sub.subset(font)
        path = OUT / f'NotoSansJP-{name}.ttf'
        font.save(path)
        print(path, round(path.stat().st_size / 1024), 'KB')


if __name__ == '__main__':
    build(sys.argv[1])
