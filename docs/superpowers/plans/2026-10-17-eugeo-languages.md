# eugeo languages (en, fr, de, es) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add English, French, German and Spanish to the quiz, Italian staying the default, with a completeness test.

**Architecture:** `i18n.js` stays the single runtime source. Country names are generated from Natural Earth by `tools/country_names.py`; the other names and the UI strings are translated by hand in four scratch JSON files and merged into `i18n.js` by one merge task. `tools/test_i18n.py` checks completeness with node.

**Tech Stack:** static JS, Python 3.14 venv (pyshp, pytest), node (present at /opt/homebrew/bin/node) for the test only.

**Spec:** `docs/superpowers/specs/2026-10-17-eugeo-languages-design.md`

## Global Constraints
- Languages and order: `[['it','Italiano'],['en','English'],['fr','Français'],['de','Deutsch'],['es','Español']]`; Italian default; browser language ignored (existing behaviour).
- Every `ui.it` key exists in every language with identical placeholder sets; every id in `data.js` (`r:`, `s:`, `m:`, `t:`, roster and background `c:`) has `places[id][lang]` for all five languages.
- `i18n.js` keeps its current structure and formatting (ui blocks per language, places as JSON-style objects with one id per line).
- Natural Earth only for the country names; no new external resources; no hard-coded text in `index.html`; commits without AI/co-author attribution lines; work on `main`, push only when the controller does.

## Review Focus
1. A placeholder dropped or swapped in a translated `wrong`/`helpSelected`/`progress` string shows "{0}" literally or the wrong name: pinned by `test_i18n_placeholders_match` (Task 1).
2. A missing places entry silently falls back to the Italian name from `data.js`: pinned by `test_i18n_places_complete` (Task 1).
3. `setLang()` must re-translate the mode nav, tray, help and chips without reshuffling: engine check in Task 3.
4. The `langs` code list and the `ui` keys must agree, else the select offers a language with no strings: pinned by `test_i18n_langs_match_ui` (Task 1).
5. Country names must stay keyed by the existing `c:` ids (derived from `name_it`), never regenerated from another language: pinned by `test_country_names_script_keys` (Task 1).

---

### Task 1: Country-name generator, completeness test, generated `c:` block

**Files:**
- Create: `tools/country_names.py`, `tools/test_i18n.py`
- Modify: `i18n.js` (the `c:` places block only), `tools/README.md` (short section)

**Interfaces:**
- Produces: `tools/country_names.py` with `country_names(records) -> dict[str, dict[str, str]]` mapping `c:<id>` (via `build_data._country_id(rec['name_it'])`) to `{'it','en','fr','de','es'}` names from `name_it/name_en/name_fr/name_de/name_es`, for the same records `build_countries` keeps (reuse `build_data.country_geoms` filtering or the same PRECLIP test), and a `main()` that prints the block as the lines `    "c:Id": { "it": "…", "en": "…", "fr": "…", "de": "…", "es": "…" },` sorted as the current block is. Overrides table `OVERRIDES = {'c:PrincipatodiMonaco': {'it': 'Monaco', 'en': 'Monaco', 'fr': 'Monaco', 'de': 'Monaco', 'es': 'Mónaco'}}` applied last.
- Produces: `tools/test_i18n.py` that loads `../i18n.js` and `../data.js` through `node -e` with `global.window={}` and prints JSON; tests: `test_i18n_langs_match_ui`, `test_i18n_ui_keys_complete`, `test_i18n_placeholders_match`, `test_i18n_places_complete` (every id in rivers/seas/ranges/cities/countries has every lang, non-empty), `test_country_names_script_keys` (the script's keys equal the `c:` keys already in `i18n.js`). Skip the module with `pytest.skip` if `shutil.which('node')` is None.

- [ ] Write the tests first; run `cd tools && ../.venv/bin/python -m pytest test_i18n.py -q -W error` and see them fail (langs has one entry; script missing).
- [ ] Implement `tools/country_names.py`; run it and replace the `c:` block in `i18n.js` with its output (Italian values must remain identical to the current ones except Monaco, which already is "Monaco"). Languages `en/fr/de/es` now exist for `c:` entries only, so `test_i18n_ui_keys_complete` and `test_i18n_places_complete` still fail for the other ids: that is expected; make the two tests parametrised per language so the failure is readable, and keep them failing (Tasks 2–3 turn them green).
- [ ] `test_country_names_script_keys` and `test_i18n_langs_match_ui` pass (langs is still `it` only, which matches `ui`).
- [ ] Document the script in `tools/README.md` (how to regenerate the block after a Natural Earth update).
- [ ] Commit `feat(tools): country names in five languages and an i18n completeness test`.

### Task 2: Translations (four parallel translators, one file each)

**Files:**
- Create (scratch, not committed): `<workspace>/i18n-en.json`, `i18n-fr.json`, `i18n-de.json`, `i18n-es.json`

**Interfaces:**
- Consumes: `<workspace>/source-strings.md` (the 60 `ui.it` strings and the 82 non-country target ids with Italian names).
- Produces: a JSON file `{"lang": "en", "name": "English", "ui": {key: string ×60}, "places": {id: string ×82}}`, UTF-8, valid JSON, no trailing commas.

- [ ] Each translator writes its file following the spec's Naming conventions, checks `python3 -I -c "import json,sys; json.load(open(sys.argv[1]))" <file>`, and reports.

### Task 3: Merge into `i18n.js` and engine check

**Files:**
- Modify: `i18n.js` (`langs`, four `ui.<lang>` blocks after `ui.it`, four extra values per non-country places entry)
- Create: `tools/merge_i18n.py`? No: the merge is one-off; do it with a throwaway script in the scratch directory, not committed.

- [ ] Merge: `langs` per Global Constraints; `ui.en/fr/de/es` blocks with the same key order and formatting as `ui.it`; for each non-country places entry add `"en": …, "fr": …, "de": …, "es": …` after `"it"`.
- [ ] `cd tools && ../.venv/bin/python -m pytest test_i18n.py test_build_data.py -q -W error` all green.
- [ ] Browser check on `python3 -m http.server 8765`: the select shows five languages; switching to each re-translates title, subtitle, mode nav, tray, buttons, help, and the cards without reshuffling; `?lang=de` loads German; `Verifica` flow in French shows the `wrong` sentence correctly with two names; "Mostra nomi" chips use the chosen language; reload keeps the choice; console clean.
- [ ] Commit `feat: English, French, German and Spanish`.

### Task 4: Docs

- [ ] `CLAUDE.md` (langs list, i18n section, "Adding a language" uses the script), `README.md` (languages line, `?lang=` hint). Commit `docs: five languages`.
