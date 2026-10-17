# tools/country_names.py
"""Print the `c:` block of `places` in ../i18n.js: country names in five languages from Natural Earth.

Usage: .venv/bin/python tools/country_names.py   (then paste the output over the `c:` lines)
"""
import json

import build_data as b
from build_data import CACHE

LANGS = ['it', 'en', 'fr', 'de', 'es']

# Applied last, over the Natural Earth names.
OVERRIDES: dict[str, dict[str, str]] = {
    'c:PrincipatodiMonaco': {'it': 'Monaco', 'en': 'Monaco', 'fr': 'Monaco', 'de': 'Monaco', 'es': 'Mónaco'},
}


def country_names(records: list[tuple[dict, object]]) -> dict[str, dict[str, str]]:
    """`c:` ID -> {lang: name} for the countries build_countries() keeps."""
    out = {}
    for rec, _ in b.country_geoms(records, b.Fit.from_window(b.WINDOW)):
        out[b._country_id(rec['name_it'])] = {lang: rec[f'name_{lang}'].strip() for lang in LANGS}
    for fid, names in OVERRIDES.items():
        if fid not in out:
            raise SystemExit(f'country_names: override for unknown id {fid}')
        out[fid] = {**out[fid], **names}
    if empty := sorted(f'{fid}.{lang}' for fid, v in out.items() for lang, s in v.items() if not s):
        raise SystemExit(f'country_names: empty names {empty}')
    return out


def block(names: dict[str, dict[str, str]]) -> str:
    """The places lines, sorted by ID, in the i18n.js style."""
    def entry(v: dict[str, str]) -> str:
        return ', '.join(f'{json.dumps(lang)}: {json.dumps(v[lang], ensure_ascii=False)}' for lang in LANGS)
    return '\n'.join(f'    {json.dumps(fid)}: {{ {entry(names[fid])} }},' for fid in sorted(names))


def main() -> None:
    print(block(country_names(b.read_shp(b.fetch('countries', CACHE)))))


if __name__ == '__main__':
    main()
