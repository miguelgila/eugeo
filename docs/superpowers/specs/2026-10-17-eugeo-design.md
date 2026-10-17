# eugeo — Geografia europea: design

Date: 2026-10-17. Status: draft for owner approval.

## Intent

A static geography quiz for Europe, built the same way as
[chgeo](https://github.com/miguelgila/chgeo) (Swiss geography quiz by the same
owner), hosted on GitHub Pages at **eugeo.giar.dev** from the public repo
`miguelgila/eugeo`. The audience is schoolchildren (Italian-speaking); the
game is: pick a card from the tray, tap the matching place on the map, press
**Verifica**, see what matched.

Three decks at launch, with names exactly as the owner listed them (Italian):

- **Fiumi**: Tago, Ebro, Loira, Tamigi, Rodano, Po, Reno, Elba, Danubio,
  Vistola, Dnepr, Don, Volga.
- **Mari e oceani**: Mar Mediterraneo, Mar Ligure, Mar Tirreno, Mar Adriatico,
  Mar Ionio, Mar Egeo, Mare del Nord, Mar Baltico, Mar Nero, Mar Caspio,
  Oceano Atlantico.
- **Catene montuose**: Cordigliera Cantabrica, Sierra Nevada, Pirenei,
  Massiccio Centrale, Alpi, Appennino, Alpi Dinariche, Balcani, Carpazi,
  Monti Scandinavi, Caucaso, Monti Urali.

## Goals

- Same look, feel and interaction model as chgeo, so the owner's existing users
  (and the owner) find nothing surprising.
- Italian only at launch, but through the same `i18n.js` mechanism as chgeo so
  languages can be added later without touching `index.html`.
- Data structured so that **countries**, **capitals** and **other cities** can
  be added as decks later by extending the pipeline and adding a mode entry,
  with no change to the game engine.
- **Reproducible geometry.** chgeo's `data.js` cannot be regenerated; eugeo's
  must be produced by a committed script from public-domain sources.
- Only public-domain / open data, with the licence stated in the repo and in
  the page footer, because the site is public.

## Non-goals

- No backend, build step, package manager, bundler, tests or linter for the
  site itself (same as chgeo). The data pipeline is the one exception and is a
  developer tool, not part of the served site.
- No analytics, cookies, third-party scripts or widgets (audience is children;
  avoids consent banners). The Ko-fi link stays a plain link.
- No other languages, flags deck, or regional sub-maps at launch.
- Cartographic precision. Mountain ranges in particular are approximate blobs
  good enough to be unambiguous in a quiz.

## Anti-goals (what would make it a failure)

- Shipping geometry whose provenance or licence is unclear.
- A map where two targets of the same deck are hard to tell apart at the
  default zoom (e.g. Ligurian vs Tyrrhenian) without the zoom working well.
- Forking the engine so far from chgeo that fixes can't be ported between the
  two projects.

## Constraints

- Hosting: GitHub Pages from `main` / root, `.nojekyll`, `CNAME` containing
  `eugeo.giar.dev`. The owner adds the DNS record `CNAME eugeo →
  miguelgila.github.io` at the `giar.dev` provider.
- Licences: code MIT (as chgeo). Map data: **Natural Earth**
  (https://www.naturalearthdata.com), public domain; recorded in
  `DATA_LICENSE` with the dataset names and version, and credited in the
  footer ("Dati: Natural Earth") even though attribution is not required.
  No other geodata source may be added without listing it in `DATA_LICENSE`
  and telling the owner.
- Commit messages: no AI co-author lines (owner rule).
- The owner uses `gh`; creating the repo, enabling Pages and pushing are
  actions the owner confirms before they happen.

## Decisions taken (owner's, or marked as builder's call)

### Repository layout

```
index.html            game: markup, CSS, inline script (from chgeo, adapted)
i18n.js               window.I18N: langs ['it'], ui.it, places[id].it
data.js               window.GEO.eu, GENERATED — do not hand-edit
tools/build_data.py   the generator
tools/requirements.txt pyshp, shapely, pyproj
tools/README.md       how to run it
tools/handdrawn.geojson  hand-drawn polygons for features missing upstream
CNAME, .nojekyll, manifest.webmanifest, icon.svg, icon-180.png, icon-512.png
LICENSE (MIT), DATA_LICENSE, README.md, CLAUDE.md
docs/superpowers/specs/…, docs/superpowers/plans/…
```

Natural Earth zips are **not** committed; the script downloads them into
`tools/cache/` (gitignored) from `https://naciscdn.org/naturalearth/10m/…`.
The script pins the dataset version by recording `VERSION.txt` contents of
each dataset into a header comment of `data.js`.

### Data pipeline (`tools/build_data.py`)

Builder's call on tooling: Python 3 + `pyshp` (read shapefiles), `shapely`
(union, simplify, clip, representative point), `pyproj` (projection). Run
with `python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt
&& .venv/bin/python tools/build_data.py`. Output is deterministic for a given
dataset version.

**Datasets (all Natural Earth 1:10m, public domain)**, verified on
2026-10-17 to contain every feature needed:

| Dataset | Used for | Notes |
|---|---|---|
| `physical/ne_10m_land` | land background | one grey landmass layer, not clickable |
| `cultural/ne_10m_admin_0_countries` | country outlines (background now; `countries` deck later) | has `NAME_IT` |
| `physical/ne_10m_rivers_lake_centerlines` | rivers | all 13 present; `featurecla` is `River` or `Lake Centerline`; take both parts per name. Name variants: Tagus is `Tajo`+`Tejo`, Rhine is `Rhein`+`Rhin`+`Rhine`, Dnieper is `Dnipro`; match on `name_en`. Has `name_it`. |
| `physical/ne_10m_geography_marine_polys` | seas | all 11 present; polygons are non-overlapping, so "Mediterranean Sea" is the remainder outside the named sub-seas. Has `name_it`. |
| `physical/ne_10m_geography_regions_polys` | mountain ranges | 10 of 12 present: `ALPS`, `PYRENEES`, `Massif Central`, `Dinaric Alps`, `Balkan Mts.`, `CARPATHIAN MOUNTAINS`, `URAL MOUNTAINS`, `CAUCASUS MTS.`, `S. Nevada` (bbox −4.7..−2.0, 36.8..37.9; not the US `SIERRA NEVADA`), `KJØLEN MOUNTAINS` (= Scandinavian Mountains). **Missing: Cantabrian Mountains, Apennines** → `tools/handdrawn.geojson`. |
| `physical/ne_10m_lakes` | (optional) big lakes for visual context | builder's call; include only lakes with `scalerank <= 3` inside the extent, non-clickable |
| `cultural/ne_10m_populated_places_simple` | capitals / cities later | has `adm0cap`, `pop_max`; not emitted at launch, but the script has the function stubbed and documented |

**Projection and extent.** ETRS89-LAEA Europe, EPSG:3035 (the standard
"Europe" projection; equal-area, Scandinavia not inflated). Clip to the
geographic window lon −25..70, lat 33..72 (Iceland to the Urals' east flank,
Cyprus to North Cape); then fit to an SVG canvas `w: 1000, h: 800` with a
uniform scale and a small margin. Note the Ural range extends to 68°N/67°E
and the Caspian to 54°E; the eastern edge must include them whole. Volga's
source and mouth both fit. (Builder may tune the window so that the map is
not dominated by the Russian plain; what must stay fully inside: all 36
targets, Iceland optional.)

**Simplification.** Douglas–Peucker in projected metres (`shapely.simplify`,
tolerance ≈ 3–5 km for land/countries, 2 km for rivers, 5 km for seas and
ranges), applied **after** union and **before** projection to SVG, and applied
to country polygons via a shared-border-preserving approach is *not* required
for launch because countries are background only; when the `countries` deck is
added, switch the country layer to topology-preserving simplification (e.g.
run through `mapshaper` or simplify the arcs of a topology). Record that
caveat in `tools/README.md`.

**Sea composition (builder's call, owner may override).** Natural Earth
splits seas into many non-overlapping polygons. The merge table in the
script is:

| Target | NE polygons merged into one shape |
|---|---|
| `s:Mediterraneo` (remainder path) | Mediterranean Sea, Balearic Sea, Alboran Sea |
| `s:Ligure`, `s:Tirreno`, `s:Adriatico`, `s:Ionio` | each its own polygon, `parent: 's:Mediterraneo'` |
| `s:Egeo` | Aegean Sea + Sea of Crete, `parent: 's:Mediterraneo'` |
| `s:MareDelNord` | North Sea + Skagerrak + Kattegat |
| `s:Baltico` | Baltic Sea + Gulf of Bothnia + Gulf of Finland + Gulf of Riga |
| `s:Nero` | Black Sea + Sea of Azov |
| `s:Caspio` | Caspian Sea |
| `s:Atlantico` | North Atlantic Ocean (clipped to extent) + Bay of Biscay + Celtic Sea + Irish Sea + English Channel + Bristol Channel + Inner Seas off Scotland + Norwegian Sea |

Only the Mediterranean has children, so `parent` is one group. Everything
else in the extent (Sea of Marmara, Barents Sea, White Sea, Strait of
Gibraltar polygon if any) renders as plain water with no target: tapping it
does nothing, same as tapping land in the seas deck. Any NE polygon that the
script finds inside the extent but not in the table must be logged by the
script so the omission is deliberate.

**Output `data.js` shape** (mirrors chgeo so the engine needs minimal change):

```js
window.GEO = { eu: {
  w: 1000, h: 800,
  version: { ne: '5.1.1', built: '2026-10-17' },
  land:      [{d}],                      // background
  countries: [{id:'c:Italia', name:'Italia', iso:'IT', d, cx, cy}], // bg now, deck later
  lakes:     [{name, d}],                // background, optional
  rivers:    [{id:'r:Tago',  name:'Tago',  d, cx, cy}],
  seas:      [{id:'s:Ligure', name:'Mar Ligure', d, cx, cy, parent:'s:Mediterraneo'}],
  ranges:    [{id:'m:Alpi',  name:'Alpi',  d, cx, cy}],
  cities:    []                           // {id:'t:Roma', name, cx, cy, capital:true, iso:'IT'} later
}};
```

IDs are stable keys derived from the Italian names (prefixes: `c:` country,
`t:` town/city, `r:` river, `s:` sea, `m:` mountain range); display names go
through `pn(id)` from `i18n.js`, exactly as chgeo. The Italian names in
`data.js` are set by a mapping table in the script (NE English name →
Italian), **not** by NE's `name_it`, so that the names match the owner's list
(e.g. "Dnepr", "Monti Scandinavi", "Cordigliera Cantabrica").

`(cx, cy)` label anchor: `shapely` `representative_point()` for polygons;
for rivers the point at 50% of the longest segment, nudged by a per-feature
override table in the script where needed (Danube, Volga, Rhine run through
busy areas).

### Game engine (`index.html`)

Start from chgeo's `index.html`; keep the structure (`MAPS`, modes, `S`,
`buildSvg`, `render`, `applyView`, zoom/pan, chips, "Mostra nomi", Verifica,
"Da ripassare"), the CSS and the i18n helpers. Changes:

- One map, `eu`. `MAPS.eu` normalises `GEO.eu` into layers: `land` and
  `countries` (non-interactive background), `lakes` (background), `rivers`,
  `seas` (water zones), `ranges` (zones), `pins` (empty for now).
- **Engine scope (builder's call): minimal diff, option "a".** Keep chgeo's
  hard-coded layer approach and add two layers, `seas` and `ranges`, plus the
  non-interactive `land`, `countries` and `lakes` backgrounds. Add a new kind
  `sea` (clickable: seas only) and reuse `river` (rivers only), `zone`
  (ranges only; chgeo's `water` kind, which lights rivers and lakes together,
  is dropped). Do **not** refactor chgeo into a shared generic layer table;
  portability between the two projects means "same structure and naming, diff
  is readable", not "identical code". Mountain ranges are `zone` targets drawn
  with a semi-transparent brown fill and dashed outline over the land so
  country borders stay visible beneath.
- **Seas deck.** All 11 cards. Sub-seas are drawn as their own paths on top
  of the Mediterranean remainder path. Click resolution: clicking a sub-sea
  path picks that sub-sea; clicking the remainder picks `s:Mediterraneo`.
  When the `s:Mediterraneo` card is placed/checked, the engine colours the
  remainder **and** every sea whose `parent` is `s:Mediterraneo` with the
  Mediterranean status colour, unless that sub-sea has its own placement,
  which wins. The chip for Mediterraneo sits in the western basin (its
  remainder's representative point). This is the only engine addition
  (`parent` handling in `status()`/`render()`), and it is generic.
- Rivers keep chgeo's wide invisible `riverHit` path. Builder's call: make
  the hit width scale with zoom exactly as chgeo does.
- Remove: Ticino map, flags deck, capitals-as-canton-abbr convention. Target
  IDs for future capitals are `t:<name>`, not reused country IDs.
- Persist `eugeo.map` / `eugeo.lang` in `localStorage` (renamed keys).
- Footer: "Dati: Natural Earth (pubblico dominio)" linked to
  naturalearthdata.com, plus the Ko-fi link, as plain links.
- Default and only language `it`; the language `<select>` is hidden when
  `I18N.langs.length === 1` (so adding `de` later just works).
- Title: "Geografia europea"; PWA name "eugeo"; icon: a new simple SVG (not
  the Swiss one). Builder's call on the icon design; keep it a single-colour
  glyph.

### i18n

`i18n.js` with `langs: ['it']`, every UI key chgeo has (dropping the flag/
Ticino ones; adding `mode.rivers.*`, `mode.seas.*`, `mode.ranges.*`,
`map.eu`, `map.eu.title`), and `places[id].it` for all 36 targets plus
country names (so a future countries deck only needs geometry wiring).

### Hosting / ops

- `gh repo create miguelgila/eugeo --public --description "Quiz di geografia europea"`,
  initial commit on `main`, push.
- `gh api -X POST repos/miguelgila/eugeo/pages -f build_type=legacy
  -f source[branch]=main -f source[path]=/` then set the custom domain and
  enforce HTTPS once the cert is issued.
- Owner: DNS `CNAME eugeo → miguelgila.github.io`.

## What's left to the builder

- Exact simplification tolerances and the margin/extent tuning, judged by
  eye: the 36 targets must be clickable without zoom on a phone, except the
  Ligurian Sea, which may need one zoom step (acceptable).
- Colours for the three kinds, consistent with chgeo's palette.
- The hand-drawn Apennines and Cantabrian polygons: simple 8–15 vertex
  outlines along the ridge lines (Apennines from Liguria to Calabria,
  ~60–100 km wide; Cantabrian from Galicia's east to the Basque Country).
  **Provenance (builder's call):** vertices are typed in by hand as
  lon/lat from general geographic knowledge, checked visually only against
  Natural Earth's own land/country layers; nothing is traced from any other
  map. The file is released CC0 / public domain and `DATA_LICENSE` says so
  in its own section ("Hand-drawn polygons in tools/handdrawn.geojson").
  The footer stays "Dati: Natural Earth (pubblico dominio)"; the
  hand-drawn outlines are documented in README/DATA_LICENSE, not the footer.
- Whether to render large lakes (Ladoga, Onega, Vänern, Geneva, Constance)
  as background; recommended yes for orientation.
- Where the Volga, Danube and Rhine chips go so they don't cover other targets.
- CLAUDE.md for the new repo, modelled on chgeo's, documenting the pipeline.

## Open questions resolved by default (owner may override)

- Mediterranean card highlights the whole basin (owner was asked, did not
  object; builder's default).
- Iceland in or out of the frame: builder's call, recommended **in** (keeps
  the Atlantic obviously large).
- Caspian is a "sea" target even though it's a lake; the owner listed it, so
  it is in the seas deck.
