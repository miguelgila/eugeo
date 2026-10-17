# Data pipeline

`build_data.py` turns Natural Earth 1:10m shapefiles into `../data.js` (`window.GEO.eu`). The output is deterministic for a given set of dataset versions, apart from the `version.built` date. Never edit `data.js` by hand: change the script and rebuild.

## Setup

From the repo root, once:

```sh
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-dev.txt   # pyshp, shapely, pyproj + pytest
```

`requirements.txt` holds the runtime dependencies only; `requirements-dev.txt` adds `pytest`.

## Build

```sh
.venv/bin/python tools/build_data.py
```

The first run downloads every dataset in `DATASETS` from `naciscdn.org` into `tools/cache/<ne_name>/` (git-ignored); later runs reuse the cache. To pick up a new Natural Earth release, delete the dataset's folder and zip under `tools/cache/` and rebuild.

The script prints `unmapped sea: …` for every marine polygon inside the window that no sea target uses. That is expected for Sea of Marmara, Barents Sea, White Sea and similar: they stay plain background water. Check the list after a Natural Earth upgrade.

It stops with `SystemExit` and a message, instead of writing a partial `data.js`, when:

- a river name in `RIVERS` matches no record;
- a sea name in `SEAS` has no marine polygon (the message lists similar names), or a sea's `points` entry falls in no polygon;
- a range name in `RANGES` has no region polygon, or a hand-drawn range is missing from `handdrawn.geojson`;
- `S. Nevada` matches a polygon outside Spain (the US Sierra Nevada is in the same dataset);
- two countries end up with the same `c:` ID, or a `COUNTRIES` code is missing from the canvas or has an empty path;
- the country coverage is invalid before or after simplification;
- a `CAPITALS` entry matches no `adm0cap == 1` record, or several, or has no country.

## Tests

```sh
cd tools && ../.venv/bin/pytest
```

`test_build_data.py` covers the path writer, the projection fit, each target list, the pre-clip, the country IDs, the roster and its `target`/`small` flags, the country coverage, the capitals (one per roster country, each inside its country), the anchor overrides, a parse of the written `data.js` and a size budget (under 600 kB). Tests that need the downloaded datasets are skipped when `tools/cache/` is missing; run a build first.

## Preview

```sh
.venv/bin/python tools/preview.py [rivers|seas|ranges|countries|capitals ...]
sips -s format png tools/preview.svg --out tools/preview.png   # macOS
```

`preview.py` reads `data.js` and writes `tools/preview.svg`: every layer, plus a name chip at each target's anchor for the decks given (default: all five). For `countries` it draws a cross and the name at each roster country's anchor, and for `capitals` a dot at each capital. The chips are sized like the game's "Mostra nomi" labels, so it is the quickest way to check by eye that labels sit on their feature and don't cover each other. Preview outputs are git-ignored.

## How it works

`build()` loads every dataset, builds each layer and returns `{'eu': {...}}`; `write_data_js()` writes it as `window.GEO = …` with a `// GENERATED … do not edit.` header listing every Natural Earth dataset's version (e.g. `land 5.1.1, countries 5.1.1, …`). The same versions are in `version.ne`, keyed by the short names in `DATASETS`, read from each dataset's `*.VERSION.txt` in the cache.

### Projection and canvas

- **Projection:** ETRS89-LAEA Europe, EPSG:3035 (equal-area, so Scandinavia is not inflated).
- **Window:** `WINDOW` is lon −25..70, lat 33..72 (Iceland to the Urals, Cyprus to North Cape). `window_bbox()` projects its edges, sampled every 0.5°, and takes the bounding box in metres.
- **Canvas:** width `W` = 1000. Height `H` is computed from the projected window's aspect (629 today), so the map fills the canvas with `MARGIN` = 0. `Fit` holds the scale and offsets that map metres to canvas pixels, y down.
- **Pre-clip:** every geometry is first clipped in lon/lat to `PRECLIP` (lon −70..100, lat 15..82). Geometry that crosses the antimeridian or lies near the projection's antipode otherwise projects to garbage that can land on the canvas. `PRECLIP` is wider than `WINDOW` so the canvas corners, which reach outside the lon/lat window, are still covered by land and sea.

`feature_to_canvas()` is the one path every feature takes: pre-clip, project to metres, simplify, clip to the projected window, scale to pixels. `to_path()` then writes SVG path data with one decimal. Simplification tolerances are 2 km for rivers, 5 km for seas and ranges, and `BG_TOL_KM` (4 km) for land, countries and lakes. Countries are the exception to the one-path rule: `country_geoms()` sends them through `feature_to_canvas()` unsimplified, then simplifies the whole layer at once with `shapely.coverage_simplify` (hence `shapely>=2.1`), so neighbours keep one shared border line. It checks `shapely.coverage_is_valid` before and after, and stops with `SystemExit` if either fails.

### Layers and tables

All the content decisions live in tables near the top of `build_data.py`. For rivers, seas and ranges, IDs are hand-written stable keys in the `RIVERS`/`SEAS`/`RANGES` tables, based on the Italian name (`r:Tago`, `s:MareDelNord`), and the Italian `name` comes from these tables, not from Natural Earth's `name_it`. Countries use NE `name_it` (see below). Country and capital IDs come from `_country_id()`, which folds the name to ASCII and drops spaces and punctuation but keeps the casing (`c:PrincipatodiMonaco`, `t:AndorralaVella`).

- **`RIVERS`**: `(id, Italian name, [NE name_en values])`. Every record whose `name_en` is in the list is merged, river and lake-centreline parts alike.
- **`SEAS`**: the sea merge table. Natural Earth splits the seas into many non-overlapping polygons, so each target lists the NE `name` values to union (e.g. *Mar Baltico* is Baltic Sea plus its gulfs, Øresund and two bays). `points` adds polygons by location, for the unnamed Great Belt polygon. `parent` marks the five inner seas of the Mediterranean (`s:Ligure`, `s:Tirreno`, `s:Adriatico`, `s:Ionio`, `s:Egeo`); `s:Mediterraneo` itself is only the remainder outside them, and the game colours its children with it. Comments in the table record Natural Earth naming quirks (no Celtic Sea polygon, Sea of the Hebrides named `Inner Seas`).
- **`RANGES`**: `(id, Italian name, NE region name)`; `None` means the outline comes from `handdrawn.geojson`.
- **Countries**: every country intersecting `PRECLIP` and visible on the canvas, with `id` `c:` plus the ASCII-folded Italian name (`_country_id()`), `name` from NE `name_it`, `iso` (falling back to `iso_a2_eh` where `iso_a2` is `-99`, e.g. France and Norway) and `a3`, NE's `ADM0_A3`.
- **`COUNTRIES`**: the roster of the Stati deck, 46 `ADM0_A3` codes. Those countries get `target: true`; all others stay background. A roster country whose simplified area is under `SMALL_AREA` (12 canvas units²) also gets `small: true`, and the game draws a tap marker on it: today the six microstates. The build stops if a roster code is missing from the canvas. To change the roster, edit the codes, add a `CAPITALS` entry for each new country, and add its `c:` and `t:` names to `places` in `../i18n.js`.
- **`CAPITALS`**: `(ADM0_A3, Italian name)` for each roster country, in roster order. `build_cities()` picks the one `ne_10m_populated_places_simple` record with `adm0cap == 1` and that `adm0_a3`, projects its point with `fit.to_canvas()`, and emits `{id: 't:…', name, cx, cy, capital: True, iso, country}`. `iso` comes from the country record, since Kosovo's place record says `-99`, and `country` is the country's `c:` ID, which is what the Capitali deck targets.
- **Lakes**: NE lakes with `scalerank <= 3` inside the window, background only.
- **Land**: one path, the union of all land polygons near the window.

### Label anchors

Each target has a label anchor `(cx, cy)` in canvas pixels, where the game puts its name chip. `anchor()` takes the midpoint of the longest part for rivers and a representative point for polygons. Where that looks wrong, `RIVER_ANCHORS`, `SEA_ANCHORS`, `RANGE_ANCHORS` and `COUNTRY_ANCHORS` override it (the last one keeps Norway off Svalbard, Croatia inland and the United Kingdom on the English Midlands); they were tuned by eye with `preview.py`. A test checks that every override names an existing target and stays inside the canvas. If the window or canvas changes, re-tune them.

### `handdrawn.geojson`

Natural Earth has no polygon for the Apennines or the Cantabrian Mountains, so they are drawn by hand: simple lon/lat outlines typed in from general geographic knowledge and checked only against Natural Earth's own land and country layers. Nothing may be traced from any other map. Each feature has `properties.id` (the target ID), `name` and `license: "CC0-1.0"`; the file is CC0 (see `../DATA_LICENSE`, section 2). Edit the coordinates by hand and rebuild.

## Adding other cities

`cities` holds only the 46 capitals today, all with `capital: True`. To add a deck of other cities, e.g. the largest cities:

1. Extend `build_cities()` to also select those records from `ne_10m_populated_places_simple` (e.g. by `pop_max` inside the window), with Italian names from a new table and `t:` IDs. Emit them without `capital: True`, and keep the capitals unchanged.
2. Add the Italian names to `places` in `../i18n.js`.
3. In `../index.html`, add a mode with `kind: 'pin'` whose `targets()` returns those cities by their `t:` IDs (the engine already draws pins and their tap areas). Every `cities` entry becomes a pin, and the Capitali deck shows all pins as dots after Verifica, so give that deck a way to hide the non-capital pins.
4. Add the `mode.<id>.*` UI strings to every language in `i18n.js`, add tests, rebuild and check with `preview.py`.
