# tools/test_i18n.py
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import build_data as b
from build_data import CACHE

if shutil.which('node') is None:
    pytest.skip('node not installed', allow_module_level=True)

ROOT = Path(__file__).resolve().parent.parent
LANGS = ['it', 'en', 'fr', 'de', 'es']
PLACEHOLDER = re.compile(r'\{\d+\}')


@pytest.fixture(scope='module')
def site():
    """window.I18N and window.GEO, loaded by node exactly as the browser sees them."""
    js = ('global.window = {};'
          f'require({json.dumps(str(ROOT / "i18n.js"))});'
          f'require({json.dumps(str(ROOT / "data.js"))});'
          'process.stdout.write(JSON.stringify({I: window.I18N, G: window.GEO}));')
    out = subprocess.run(['node', '-e', js], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.fixture(scope='module')
def i18n(site):
    return site['I']


@pytest.fixture(scope='module')
def target_ids(site):
    eu = site['G']['eu']
    return [f['id'] for layer in ('rivers', 'seas', 'ranges', 'cities', 'countries') for f in eu[layer]]


def test_i18n_langs_match_ui(i18n):
    codes = [code for code, _ in i18n['langs']]
    assert len(codes) == len(set(codes))
    assert codes[0] == 'it'
    assert set(codes) == set(i18n['ui'])


@pytest.mark.parametrize('lang', LANGS)
def test_i18n_ui_keys_complete(i18n, lang):
    ui = i18n['ui']
    assert lang in ui, f'no ui.{lang}'
    assert sorted(set(ui['it']) - set(ui[lang])) == [], 'missing keys'
    assert sorted(set(ui[lang]) - set(ui['it'])) == [], 'extra keys'
    assert [k for k, v in ui[lang].items() if not v.strip()] == [], 'empty strings'


def test_i18n_placeholders_match(i18n):
    ui = i18n['ui']
    for lang, strings in ui.items():
        for key, text in strings.items():
            if key in ui['it']:
                assert sorted(PLACEHOLDER.findall(text)) == sorted(PLACEHOLDER.findall(ui['it'][key])), (lang, key)


@pytest.mark.parametrize('lang', LANGS)
def test_i18n_places_complete(i18n, target_ids, lang):
    places = i18n['places']
    missing = [i for i in target_ids if not places.get(i, {}).get(lang, '').strip()]
    assert missing == []


needs_countries = pytest.mark.skipif(not (CACHE/'ne_10m_admin_0_countries').exists(), reason='no cache')

@needs_countries
def test_country_names_script_keys(i18n):
    import country_names
    names = country_names.country_names(b.read_shp(b.fetch('countries', CACHE)))
    assert sorted(names) == sorted(k for k in i18n['places'] if k.startswith('c:'))
    assert all(set(v) == set(LANGS) and all(s.strip() for s in v.values()) for v in names.values())
