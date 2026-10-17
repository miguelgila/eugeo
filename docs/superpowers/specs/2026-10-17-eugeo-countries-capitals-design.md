# eugeo: countries and capitals decks — design

Date: 2026-10-17. Extends `2026-10-17-eugeo-design.md`. Owner asked for countries and capitals and chose "the standard list of 44 to 50 European states", leaving the rest to the builder.

## Intent

Two more decks in the same game: **Stati** (tap the country) and **Capitali** (tap the country whose capital is on the card). Same engine, same data pipeline, same open data (Natural Earth only).

## Goals

- A **countries deck** with 46 targets: the 44 states of the UN "Europe" list plus Cyprus and Kosovo, as Italian schoolbooks list them. Turkey, Kazakhstan, Georgia, Armenia and Azerbaijan stay drawn as background and are never targets.
- A **capitals deck** with the same 46 targets, where the card shows the capital's Italian name and the player taps the country. This is the chgeo approach (canton ↔ capital) and avoids 46 overlapping pins (Rome and Vatican City are 2.5 km apart). After a check, the capital's dot and its name chip are shown so the player learns where it is.
- Microstates (Vatican City, Monaco, San Marino, Liechtenstein, Malta, Andorra) must be tappable at zoom 1 on a phone, so they get a round marker drawn on top of the map with a finger-sized hit circle, like pins.
- Country borders must be topology-shared (no slivers between neighbours) since they are now coloured.

## Non-goals

- Tapping the capital's dot itself; other cities; flags; a map of a single country; English or other languages (keep the i18n mechanism).

## Roster (ISO alpha-3 as in Natural Earth `ADM0_A3`)

ALB AND AUT BLR BEL BIH BGR HRV CYP CZE DNK EST FIN FRA DEU GRC HUN ISL IRL ITA KOS LVA LIE LTU LUX MLT MDA MCO MNE NLD MKD NOR POL PRT ROU RUS SMR SRB SVK SVN ESP SWE CHE UKR GBR VAT (46).

Capitals (Italian): Tirana, Andorra la Vella, Vienna, Minsk, Bruxelles, Sarajevo, Sofia, Zagabria, Nicosia, Praga, Copenaghen, Tallinn, Helsinki, Parigi, Berlino, Atene, Budapest, Reykjavík, Dublino, Roma, Pristina, Riga, Vaduz, Vilnius, Lussemburgo, La Valletta, Chișinău, Monaco, Podgorica, Amsterdam, Skopje, Oslo, Varsavia, Lisbona, Bucarest, Mosca, San Marino, Belgrado, Bratislava, Lubiana, Madrid, Stoccolma, Berna, Kiev, Londra, Città del Vaticano.

Display-name overrides in `i18n.js` only (IDs stay as derived from Natural Earth `name_it`): `c:PrincipatoDiMonaco` → "Monaco". "Repubblica Ceca" stays (still the common school name).

## Data (`data.js`, produced by `tools/build_data.py`)

- `countries[]` entries gain `a3` (Natural Earth `ADM0_A3`), `target: true` for the 46 roster entries (absent otherwise), and `small: true` for roster entries whose canvas area is below `SMALL_AREA = 12` square canvas units (exactly the six microstates with current data).
- Country geometry goes through `shapely.coverage_simplify` on the whole clipped layer (tolerance `BG_TOL_KM` converted to canvas units through `fit.scale`) instead of per-feature `simplify`. `shapely.coverage_is_valid` must hold before and after, else `SystemExit`. This bumps the requirement to `shapely>=2.1`.
- `cities[]` is filled by `build_cities()` from `ne_10m_populated_places_simple`: one record per roster country, matched on `adm0cap == 1` and `adm0_a3` from a `CAPITALS` table `(a3, Italian name)` in the script. Shape: `{id:'t:<ItalianNameNoSpaces>', name, cx, cy, capital: true, iso, country:'c:<CountryId>'}`. Zero or multiple matches for a table entry is `SystemExit`.
- A `COUNTRY_ANCHORS` override table, tuned with `tools/preview.py`, for countries whose representative point lands badly (expected: Russia, Norway, Greece, Croatia, Denmark, Italy, United Kingdom, France).

## Engine (`index.html`)

- New `kind: 'country'`. When active, roster countries (`target`) take taps and are coloured through `status()`; non-roster countries keep `fill: none` and no pointer events. When inactive, the layer stays the background it is today.
- Small countries get a `.mark` circle (visible, coloured like the country) and a `.markHit` circle sized in screen pixels by `applyView()` like `pinHits`; both exist only for `small` countries and are shown only when the kind is `country`.
- Modes: `countries` (`kind:'country'`, targets = roster countries, chip at the country anchor) and `capitals` (`kind:'country'`, `dots: true`, targets = `cities` with `capital`, `id` = the city's `country`, `name` = `pn(city.id)`, chip at the city's `(cx, cy)` with the `.up` offset). With `dots`, the pins layer (`EU.cities`) is drawn as non-interactive dots; the `pinHits` stay hidden since the kind is not `pin`.
- Mode order in the nav: Fiumi, Mari e oceani, Catene montuose, Stati, Capitali.
- No change to scoring, the parent rule, zoom or i18n plumbing.

## Copy (`i18n.js`, Italian)

- `mode.countries`: label "Stati", tray "Stati", subtitle "Metti ogni Stato al suo posto", what "uno Stato", help "Tocca lo Stato giusto sulla mappa. I più piccoli hanno un pallino."
- `mode.capitals`: label "Capitali", tray "Capitali", subtitle "Trova lo Stato di ogni capitale", what "lo Stato della capitale", help "Tocca lo Stato di cui la carta è la capitale. I più piccoli hanno un pallino."
- `description` becomes "Quiz di geografia: fiumi, mari, catene montuose, Stati e capitali d'Europa."
- `places['t:…']` for the 46 capitals.

## Builder's call

Anything not fixed above (exact colours within the existing palette, marker radius, test names) is the builder's.
