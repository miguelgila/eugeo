# eugeo countries and capitals decks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the "Stati" (countries) and "Capitali" (capitals) decks to the eugeo quiz, with topology-safe borders and tappable microstates.

**Architecture:** The pipeline (`tools/build_data.py`) marks the 46 roster countries, simplifies the country layer as a coverage, and fills `cities` with the capitals. The engine (`index.html`) gains a `country` kind that makes roster countries tappable, draws markers for small ones, and two modes. Copy lives in `i18n.js`.

**Tech Stack:** Python 3.14 venv, pyshp, shapely ≥ 2.1 (`coverage_simplify`), pyproj, pytest; static HTML/JS.

**Spec:** `docs/superpowers/specs/2026-10-17-eugeo-countries-capitals-design.md` (the roster, capital names and copy are fixed there; read it).

## Global Constraints

- Data sources: Natural Earth only (already cached in `tools/cache/`), never hand-edit `data.js`.
- No UI text hard-coded in `index.html`; every string through `i18n.js`.
- Keep the chgeo-like structure and naming; follow existing code style (compact, commented where non-obvious).
- Tests: `cd tools && ../.venv/bin/python -m pytest test_build_data.py -q -W error` must pass; `data.js` under 600 KB.
- Commits: no AI or co-author attribution lines. Work on `main` (owner consent given for this repo).

## Review Focus

1. Tapping a microstate marker must register for that microstate, not for Italy/France/Spain under it (marker and hit circle drawn after the country paths). Pinned by the engine's manual check in Task 3.
2. A capital's point must lie in (or within 2 canvas units of) its own country polygon, otherwise the table is miswired. Pinned by `test_capitals_are_inside_their_country` (Task 2).
3. Non-roster countries must not take taps in the country decks. Pinned by `test_targets_are_exactly_the_roster` (Task 1) and the engine check (Task 3).
4. Coverage simplification must not create invalid geometry or drop a roster country. Pinned by `test_country_coverage_is_valid` and `test_roster_countries_all_present` (Task 1).
5. Duplicate or missing capital records (e.g. a country with two `adm0cap` rows). Pinned by `test_capitals_cover_roster` and the `SystemExit` guard (Task 2).

---

### Task 1: Roster, coverage simplification and small flag in the pipeline

**Files:**
- Modify: `tools/build_data.py` (`build_countries`, new constants `COUNTRIES`, `SMALL_AREA`, `COUNTRY_ANCHORS`)
- Modify: `tools/requirements.txt` (`shapely>=2.1`)
- Test: `tools/test_build_data.py`

**Interfaces:**
- Produces: `countries[]` entries `{id, name, iso, a3, d, cx, cy, target?: True, small?: True}`; module constants `COUNTRIES: frozenset[str]` (46 ADM0_A3 codes from the spec), `SMALL_AREA = 12`, `COUNTRY_ANCHORS: dict[str, tuple[float,float]]` keyed by country id.
- Consumes: existing `feature_to_canvas`, `Fit.scale`, `anchor`, `_country_id`, `BG_TOL_KM`.

- [ ] **Step 1: Write failing tests** in `tools/test_build_data.py`, using the existing `built`/fixtures pattern (`@needs_all` where the cache is required):

```python
def test_roster_countries_all_present(built):
    a3 = {c['a3'] for c in built['eu']['countries'] if c.get('target')}
    assert a3 == set(b.COUNTRIES) and len(a3) == 46

def test_targets_are_exactly_the_roster(built):
    for c in built['eu']['countries']:
        assert bool(c.get('target')) == (c['a3'] in b.COUNTRIES)

def test_small_flag_marks_the_microstates(built):
    small = {c['a3'] for c in built['eu']['countries'] if c.get('small')}
    assert small == {'VAT', 'MCO', 'SMR', 'LIE', 'MLT', 'AND'}

def test_country_coverage_is_valid(countries_records, fit):
    pairs = b.country_geoms(countries_records, fit)
    assert shapely.coverage_is_valid([g for _, g in pairs])
    assert all(not g.is_empty for rec, g in pairs if rec['adm0_a3'] in b.COUNTRIES)
```
  `country_geoms(records, fit) -> list[tuple[dict, BaseGeometry]]` is a new helper (Step 3) returning the clipped, coverage-simplified geometries with their records; `build_countries` is built on it.

- [ ] **Step 2: Run the tests, expect failures** (`a3`/`target` keys missing, helper undefined).

- [ ] **Step 3: Implement** in `tools/build_data.py`:
  - `COUNTRIES` (46 codes), `SMALL_AREA = 12`, `COUNTRY_ANCHORS = {}` placeholder next to `RANGE_ANCHORS`.
  - `country_geoms(records, fit)`: filter on `_PRECLIP_BOX`, `feature_to_canvas(g, fit, 0)` (no per-feature simplify), drop empties, then `shapely.coverage_simplify(geoms, BG_TOL_KM * 1000 * fit.scale, simplify_boundary=True)`; `SystemExit('countries: invalid coverage')` if `coverage_is_valid` fails before or after.
  - `build_countries` uses it; adds `'a3': rec['adm0_a3']`, `'target': True` when in `COUNTRIES`, `'small': True` when target and `geom.area < SMALL_AREA`; applies `COUNTRY_ANCHORS` overrides as the other layers do (anchor override by id).
  - `tools/requirements.txt`: `shapely>=2.1`.

- [ ] **Step 4: Run the tests, expect pass.** Also run `.venv/bin/python tools/build_data.py` and `tools/preview.py`; confirm borders have no slivers in `tools/preview.svg` (open it or rasterise with `qlmanage -t -s 2000 -o <scratch dir> tools/preview.svg` and view the PNG).

- [ ] **Step 5: Commit** `feat(tools): roster flag, coverage-simplified borders and small flag for countries` (include the regenerated `data.js`).

### Task 2: Capitals in the pipeline and anchor tuning

**Files:**
- Modify: `tools/build_data.py` (`CAPITALS`, `build_cities`, `build`, `COUNTRY_ANCHORS` values)
- Test: `tools/test_build_data.py`

**Interfaces:**
- Produces: `cities[]` entries `{id:'t:<slug>', name, cx, cy, capital: True, iso, country:'c:<id>'}`, 46 of them, in `COUNTRIES` roster order of the `CAPITALS` table; `CAPITALS: list[tuple[str, str]]` of `(a3, Italian name)` from the spec.
- Consumes: Task 1's `build_countries` output (for `a3 → id` mapping), `Fit.to_canvas`, `_country_id` for the slug (`t:` + `_country_id(name)[2:]`).

- [ ] **Step 1: Write failing tests:**

```python
def test_capitals_cover_roster(built):
    cities = built['eu']['cities']
    assert len(cities) == 46 and all(c['capital'] for c in cities)
    assert {c['country'] for c in cities} == {c['id'] for c in built['eu']['countries'] if c.get('target')}
    assert len({c['id'] for c in cities}) == 46

def test_capitals_are_inside_their_country(built):
    # distance from the capital point to its country's geometry < 2 canvas units
    ...  # use country_geoms() from Task 1 and shapely.Point(c['cx'], c['cy'])

def test_capital_table_entry_without_match_exits(places_records, fit, monkeypatch):
    monkeypatch.setattr(b, 'CAPITALS', b.CAPITALS + [('ZZZ', 'Nowhere')])
    with pytest.raises(SystemExit): b.build_cities(places_records, <countries>, fit)
```

- [ ] **Step 2: Run, expect failures.**

- [ ] **Step 3: Implement** `build_cities(records, countries, fit) -> list[dict]`: for each `(a3, name)` in `CAPITALS` find the records with `adm0cap == 1 and adm0_a3 == a3`; exactly one, else `SystemExit` naming the code and count; point from `(longitude, latitude)` through `fit.to_canvas(Point)`; `iso` from `rec['iso_a2']`; `country` from the `a3 → id` map built from `countries`. Update `build()` to pass the countries list. Keep `data.js` `cities` key.

- [ ] **Step 4: Tune `COUNTRY_ANCHORS`** by regenerating and viewing `tools/preview.py` output (have the preview draw the country anchors as small crosses and the capitals as dots, following how it draws the other layers). Move anchors that land on islands, in the sea or off the mainland (expect Russia → European Russia west of the Urals, Norway, Greece, Croatia, Denmark, Italy, UK, France, Netherlands). Document each override with a short comment, as the existing tables do.

- [ ] **Step 5: Run all tests, expect pass**; `data.js` rebuilt, size under 600 KB.

- [ ] **Step 6: Commit** `feat(tools): capitals layer and country label anchors` (with `data.js`).

### Task 3: Engine kinds, markers, modes and copy

**Files:**
- Modify: `index.html` (`MAPS.eu`, CSS, `buildSvg`, `applyView`, `render`, `renderChips`)
- Modify: `i18n.js` (`description`, `mode.countries.*`, `mode.capitals.*`, `places['t:…']` ×46, `c:PrincipatoDiMonaco` → "Monaco")

**Interfaces:**
- Consumes: `countries[].target/small/a3`, `cities[]` from Tasks 1–2.
- Produces: `kind:'country'`; modes `countries` and `capitals` (`dots:true`); `nodes.marks`, `nodes.markHits`.

- [ ] **Step 1: `MAPS.eu`**: `pins: EU.cities`; add modes after `ranges`:
  - `{id:'countries',kind:'country',targets:()=>EU.countries.filter(c=>c.target).map(c=>({id:c.id,name:pn(c.id,c.name),cx:c.cx,cy:c.cy}))}`
  - `{id:'capitals',kind:'country',dots:true,targets:()=>EU.cities.filter(c=>c.capital).map(c=>({id:c.country,name:pn(c.id,c.name),cx:c.cx,cy:c.cy}))}`

- [ ] **Step 2: `buildSvg`**: country paths get `n.onclick=()=>pickTarget(c.id)` for `target` countries; after rivers and before pins, for each `small` country create a `.mark` circle (r 5) and a `.markHit` circle (r 11) at `(cx, cy)`, `onclick` → `pickTarget(c.id)`, stored in `nodes.marks`/`nodes.markHits` (keep the index aligned with `m.countries.filter(c=>c.small)`). CSS: `.country.target{cursor:pointer;transition:fill .15s}`, `.mark{stroke:#fff;stroke-width:2;pointer-events:none}`, `.markHit{fill:transparent;cursor:pointer}`.

- [ ] **Step 3: `applyView`**: size `nodes.markHits` like `pinHits` (`r = max(11, 18*u)`), and `nodes.marks` `r = max(5, 7*u)` so they stay visible when zoomed out and shrink when zoomed in.

- [ ] **Step 4: `render`**: `const active=k==='country'`; for each country `i`: if `c.target`, `fill = active ? status(c.id, '#E7E3D6', tint(i,55,55), '#D7D7D1', cnt) : 'none'`, `stroke = active ? '#8B8B84' : '#C9C9C2'`, `pointerEvents = active ? '' : 'none'`, `cursor`; non-target countries always `fill:none`, pointer-events none. Marks: visible only when active, fill = the same status colour as their country (compute once per country, don't call `status()` twice since it counts). Pins: visible when `M.dots`, fill `#1C1C1A`, `pinHits` hidden unless `k==='pin'`. `renderChips`: use `.up` when `mode().kind==='pin' || mode().dots`.

- [ ] **Step 5: `i18n.js`**: strings from the spec's Copy section; 46 `places['t:…']` entries (ids as emitted in `data.js`); `"c:PrincipatoDiMonaco": { "it": "Monaco" }`.

- [ ] **Step 6: Manual check** on `python3 -m http.server 8765` with the Chrome tools, or by reading the DOM through a headless check if no browser: in Stati, tap Italy → the Italy path colours; tap the Vatican marker → Vatican is placed, Italy unaffected; Turkey takes no tap; Verifica scores; Mostra nomi shows 46 chips. In Capitali, dots appear, chips for wrong answers sit above the capital dot. Rivers/Mari/Catene unchanged.

- [ ] **Step 7: Commit** `feat: Stati and Capitali decks`.

### Task 4: Docs

**Files:**
- Modify: `CLAUDE.md` (data shape, kinds, modes, parent rule unchanged, "Adding a deck" rewrite: countries deck now exists), `README.md` (decks list), `tools/README.md` (remove the "not topology-shared" caveat, describe `COUNTRIES`, `CAPITALS`, `country_geoms`, `COUNTRY_ANCHORS`, `SMALL_AREA`), `DATA_LICENSE` (no new source; confirm unchanged).

- [ ] **Step 1: Update the four files** so every statement matches the code (grep for "stub", "background", "topology", "future" and fix each).
- [ ] **Step 2: Commit** `docs: countries and capitals decks`.
