# eugeo: English, French, German and Spanish — design

Date: 2026-10-17. Owner: "add english, french, german and spanish, italian as default".

## Intent
Make the quiz usable by non-Italian players through the existing i18n mechanism, without changing the game or the default.

## Goals
- `I18N.langs` becomes `it, en, fr, de, es` (Italian first and default; the browser language stays ignored; `?lang=xx` and the saved choice work as today; the language `<select>` appears automatically).
- Every UI key in `ui.it` exists in the four new languages with the same `{0}`/`{1}` placeholders; the sentences read naturally to a native speaker and keep the school-friendly tone. Language names in `langs` are endonyms: Italiano, English, Français, Deutsch, Español.
- Every target id in `data.js` (13 rivers, 11 seas, 12 ranges, 46 capitals, 46 roster countries) and every background country has a `places[id][lang]` entry in all five languages.
- Country names in all five languages come from Natural Earth's `NAME_IT/EN/FR/DE/ES` columns through a small committed script (`tools/country_names.py`) that prints the `c:` places block; the i18n file stays the single source the site loads. Known Italian overrides in `i18n.js` (Monaco) are preserved; in the other languages Monaco is simply "Monaco".
- A pipeline test (`tools/test_i18n.py`, run by node through subprocess, skipped if node is missing) enforces completeness: same UI keys per language, same placeholder sets per key, a places entry per id and language, no empty strings, and `langs` codes matching `ui` keys.

## Non-goals
- Translating `manifest.webmanifest`, the README or the hand-drawn data; auto-detecting the browser language; flags.

## Naming conventions (builder follows these)
- English: Tagus, Ebro, Loire, Thames, Rhône, Po, Rhine, Elbe, Danube, Vistula, Dnieper, Don, Volga; Mediterranean Sea, Ligurian/Tyrrhenian/Adriatic/Ionian/Aegean Sea, North Sea, Baltic Sea, Black Sea, Caspian Sea, Atlantic Ocean; Cantabrian Mountains, Sierra Nevada, Pyrenees, Massif Central, Alps, Apennines, Dinaric Alps, Balkan Mountains, Carpathians, Scandinavian Mountains, Caucasus, Ural Mountains. Capitals in their usual English exonyms (Lisbon, Vienna, Prague, Warsaw, Kyiv, Moscow, Copenhagen, Brussels, Rome, Athens, Bucharest, Belgrade, Ljubljana, Zagreb, Vatican City, Valletta, Chișinău, Nicosia, Pristina, Reykjavík…).
- French, German, Spanish: the standard exonym of each language (e.g. fr "Tamise", "la Vistule"→"Vistule" without article; de "Themse", "Weichsel", "Rhône", "Kaukasus"; es "Támesis", "Vístula", "Ródano", "Cárpatos", "Cáucaso"). No articles in place names (cards are nouns). Sea names use the language's usual form ("mer Méditerranée" with the French lowercase generic; "Mittelmeer"; "mar Mediterráneo").
- UI: keep the same information density; the `wrong` sentence must read grammatically with both names substituted; "Verifica" → en "Check", fr "Vérifier", de "Prüfen", es "Comprobar".

## Builder's call
Anything else (exact wording, script CLI shape, test names).
