"""Build the eugeo map data from Natural Earth 1:10m shapefiles (public domain)."""
import json
import unicodedata
import urllib.request
from datetime import date
import zipfile
from pathlib import Path

import numpy as np
import shapefile
import shapely
from pyproj import Transformer
from shapely.geometry import (GeometryCollection, LineString, MultiLineString,
                              MultiPolygon, Point, Polygon, box, shape)
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

NE_BASE = 'https://naciscdn.org/naturalearth/10m/'
DATASETS: dict[str, str] = {
    'land': 'physical/ne_10m_land',
    'countries': 'cultural/ne_10m_admin_0_countries',
    'rivers': 'physical/ne_10m_rivers_lake_centerlines',
    'marine': 'physical/ne_10m_geography_marine_polys',
    'regions': 'physical/ne_10m_geography_regions_polys',
    'lakes': 'physical/ne_10m_lakes',
    'places': 'cultural/ne_10m_populated_places_simple',
}

W, H = 1000, 800
MARGIN = 16
WINDOW = (-25.0, 33.0, 70.0, 72.0)  # lon_min, lat_min, lon_max, lat_max
# Padded lon/lat box clipped before projecting: geometry spanning the antimeridian or near the
# EPSG:3035 antipode projects to garbage that can land on the canvas.
PRECLIP = (-70.0, 15.0, 100.0, 82.0)  # lon_min, lat_min, lon_max, lat_max

CACHE = Path(__file__).resolve().parent / 'cache'
HANDDRAWN = Path(__file__).resolve().parent / 'handdrawn.geojson'

_TO_LAEA = Transformer.from_crs('EPSG:4326', 'EPSG:3035', always_xy=True)


def _ne_name(name: str) -> str:
    return DATASETS[name].rsplit('/', 1)[1]


def fetch(name: str, cache: Path) -> Path:
    """Download and unzip a Natural Earth dataset into cache/<ne_name>/; return the .shp path."""
    ne_name = _ne_name(name)
    folder = cache / ne_name
    shp = folder / f'{ne_name}.shp'
    if shp.exists():
        return shp
    cache.mkdir(parents=True, exist_ok=True)
    zpath = cache / f'{ne_name}.zip'
    if not zpath.exists():
        urllib.request.urlretrieve(f'{NE_BASE}{DATASETS[name]}.zip', zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(folder)
    return shp


def read_version(cache: Path, name: str) -> str:
    folder = cache / _ne_name(name)
    return next(folder.glob('*.VERSION.txt')).read_text().strip()


def read_shp(shp: Path) -> list[tuple[dict, BaseGeometry]]:
    with shapefile.Reader(str(shp)) as r:
        return [({k.lower(): v for k, v in sr.record.as_dict().items()},
                 shape(sr.shape.__geo_interface__))
                for sr in r.iterShapeRecords()]


class Fit:
    """Maps lon/lat to canvas pixels via EPSG:3035, fitting the window into the canvas."""

    def __init__(self, bbox: tuple[float, float, float, float], scale: float, ox: float, oy: float):
        self.bbox = bbox  # projected window bbox in EPSG:3035 metres
        self.scale = scale
        self.ox = ox
        self.oy = oy

    @classmethod
    def from_window(cls, window: tuple[float, float, float, float]) -> 'Fit':
        lon0, lat0, lon1, lat1 = window
        n_lon = round((lon1 - lon0) / 0.5)
        n_lat = round((lat1 - lat0) / 0.5)
        lons = [lon0 + i * (lon1 - lon0) / n_lon for i in range(n_lon + 1)]
        lats = [lat0 + i * (lat1 - lat0) / n_lat for i in range(n_lat + 1)]
        edge = ([(lon, lat0) for lon in lons] + [(lon1, lat) for lat in lats]
                + [(lon, lat1) for lon in reversed(lons)] + [(lon0, lat) for lat in reversed(lats)])
        xs, ys = _TO_LAEA.transform(*zip(*edge))
        minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
        bw, bh = maxx - minx, maxy - miny
        scale = min((W - 2 * MARGIN) / bw, (H - 2 * MARGIN) / bh)
        ox = (W - bw * scale) / 2 - minx * scale
        oy = (H - bh * scale) / 2 + maxy * scale
        return cls((minx, miny, maxx, maxy), scale, ox, oy)

    def to_metres(self, geom: BaseGeometry) -> BaseGeometry:
        """lon/lat -> EPSG:3035 metres."""
        return shapely.transform(geom, lambda c: np.column_stack(_TO_LAEA.transform(c[:, 0], c[:, 1])))

    def scale_geom(self, geom: BaseGeometry) -> BaseGeometry:
        """EPSG:3035 metres -> canvas px (y down)."""
        return shapely.transform(geom, lambda c: c * [self.scale, -self.scale] + [self.ox, self.oy])

    def project(self, geom: BaseGeometry) -> BaseGeometry:
        return self.scale_geom(self.to_metres(geom))

    def clip(self, geom: BaseGeometry) -> BaseGeometry:
        """Clip a geometry in EPSG:3035 metres to the projected window bbox."""
        return shapely.clip_by_rect(geom, *self.bbox)

    def to_canvas(self, geom: BaseGeometry) -> BaseGeometry:
        return self.scale_geom(self.clip(self.to_metres(geom)))


def _fmt(v: float, nd: int) -> str:
    s = f'{v:.{nd}f}'
    return s[1:] if s.startswith('-') and float(s) == 0 else s


def _pts(coords, nd: int) -> str:
    return 'L'.join(f'{_fmt(x, nd)} {_fmt(y, nd)}' for x, y, *_ in coords)


def to_path(geom: BaseGeometry, nd: int = 1) -> str:
    """SVG path data: closed ring per polygon ring (exterior and holes), open run per line."""
    if isinstance(geom, Polygon):
        if geom.is_empty:
            return ''
        return ''.join(f'M{_pts(ring.coords[:-1], nd)}Z' for ring in (geom.exterior, *geom.interiors))
    if isinstance(geom, LineString):
        return '' if geom.is_empty else f'M{_pts(geom.coords, nd)}'
    if isinstance(geom, (MultiPolygon, MultiLineString, GeometryCollection)):
        return ''.join(to_path(g, nd) for g in geom.geoms)
    return ''


def _lines(geom: BaseGeometry) -> list[LineString]:
    if isinstance(geom, LineString):
        return [geom]
    if hasattr(geom, 'geoms'):
        return [l for g in geom.geoms for l in _lines(g)]
    return []


def anchor(geom: BaseGeometry) -> tuple[float, float]:
    """Label anchor: representative point for polygons, midpoint of the longest line part for lines."""
    lines = _lines(geom)
    if lines:
        p = max(lines, key=lambda l: l.length).interpolate(0.5, normalized=True)
    else:
        p = geom.representative_point()
    return round(p.x, 1), round(p.y, 1)


def simplify(geom: BaseGeometry, tol_km: float) -> BaseGeometry:
    """Simplify a geometry in EPSG:3035 metres."""
    return geom.simplify(tol_km * 1000, preserve_topology=True)


def preclip(geom: BaseGeometry) -> BaseGeometry:
    """Clip a lon/lat geometry to the padded PRECLIP box."""
    return shapely.clip_by_rect(geom, *PRECLIP)


def feature_to_canvas(geom: BaseGeometry, fit: Fit, tol_km: float) -> BaseGeometry:
    """lon/lat geometry -> pre-clipped -> metres -> simplified -> clipped -> canvas px."""
    return fit.scale_geom(fit.clip(simplify(fit.to_metres(preclip(geom)), tol_km)))


def _feature(fid: str, name: str, geom: BaseGeometry, fit: Fit, tol_km: float,
             anchors: dict[str, tuple[float, float]] | None = None) -> dict:
    g = feature_to_canvas(geom, fit, tol_km)
    cx, cy = (anchors or {}).get(fid) or anchor(g)
    return {'id': fid, 'name': name, 'd': to_path(g), 'cx': cx, 'cy': cy}


RIVERS: list[tuple[str, str, list[str]]] = [
    ('r:Tago', 'Tago', ['Tagus']),
    ('r:Ebro', 'Ebro', ['Ebro']),
    ('r:Loira', 'Loira', ['Loire']),
    ('r:Tamigi', 'Tamigi', ['Thames']),
    ('r:Rodano', 'Rodano', ['Rhône']),
    ('r:Po', 'Po', ['Po']),
    ('r:Reno', 'Reno', ['Rhine']),
    ('r:Elba', 'Elba', ['Elbe']),
    ('r:Danubio', 'Danubio', ['Danube']),
    ('r:Vistola', 'Vistola', ['Vistula']),
    ('r:Dnepr', 'Dnepr', ['Dnieper']),
    ('r:Don', 'Don', ['Don']),
    ('r:Volga', 'Volga', ['Volga']),
]

RIVER_ANCHORS: dict[str, tuple[float, float]] = {}


def build_rivers(records: list[tuple[dict, BaseGeometry]], fit: Fit) -> list[dict]:
    out = []
    for fid, name, ne in RIVERS:
        parts = [g for rec, g in records if rec['name_en'] in ne]
        if not parts:
            raise SystemExit(f'river {fid}: no records with name_en in {ne}')
        out.append(_feature(fid, name, unary_union(parts), fit, 2, RIVER_ANCHORS))
    return out


_MED = 's:Mediterraneo'
# `ne`: NE `name` values to merge; optional `points`: lon/lat points, each merging
# every (possibly unnamed) polygon that contains it.
SEAS: list[dict] = [
    {'id': 's:Mediterraneo', 'name': 'Mar Mediterraneo', 'parent': None,
     'ne': ['Mediterranean Sea', 'Balearic Sea', 'Alboran Sea', 'Golfe du Lion', 'Strait of Gibraltar']},
    {'id': 's:Ligure', 'name': 'Mar Ligure', 'parent': _MED, 'ne': ['Ligurian Sea']},
    {'id': 's:Tirreno', 'name': 'Mar Tirreno', 'parent': _MED, 'ne': ['Tyrrhenian Sea']},
    {'id': 's:Adriatico', 'name': 'Mar Adriatico', 'parent': _MED, 'ne': ['Adriatic Sea']},
    {'id': 's:Ionio', 'name': 'Mar Ionio', 'parent': _MED, 'ne': ['Ionian Sea']},
    {'id': 's:Egeo', 'name': 'Mar Egeo', 'parent': _MED, 'ne': ['Aegean Sea', 'Sea of Crete']},
    {'id': 's:MareDelNord', 'name': 'Mare del Nord', 'parent': None,
     'ne': ['North Sea', 'Skagerrak', 'Kattegat', 'Waddenzee']},
    {'id': 's:Baltico', 'name': 'Mar Baltico', 'parent': None,
     'ne': ['Baltic Sea', 'Gulf of Bothnia', 'Gulf of Finland', 'Gulf of Riga',
            'Øresund', 'Mecklenburger Bucht', 'Stettiner Haff'],
     'points': [(10.9, 55.3)]},  # Great Belt: the Danish Belts polygon has no NE name
    {'id': 's:Nero', 'name': 'Mar Nero', 'parent': None, 'ne': ['Black Sea', 'Sea of Azov']},
    {'id': 's:Caspio', 'name': 'Mar Caspio', 'parent': None, 'ne': ['Caspian Sea']},
    {'id': 's:Atlantico', 'name': 'Oceano Atlantico', 'parent': None,
     # NE 5.x has no 'Celtic Sea' polygon (that water is part of 'North Atlantic Ocean'),
     # and the Sea of the Hebrides is named 'Inner Seas' (name_en 'Sea of the Hebrides').
     'ne': ['North Atlantic Ocean', 'Bay of Biscay', 'Irish Sea', 'English Channel',
            'Bristol Channel', 'Inner Seas', 'Norwegian Sea', 'Greenland Sea']},
]


def build_seas(records: list[tuple[dict, BaseGeometry]], fit: Fit, log=print) -> list[dict]:
    by_name: dict[str, list[BaseGeometry]] = {}
    for rec, g in records:
        if rec['name']:
            by_name.setdefault(rec['name'], []).append(g)
    used: set[int] = set()  # ids of unnamed records merged via `points`
    out = []
    for sea in SEAS:
        for n in sea['ne']:
            if n not in by_name:
                word = n.split()[0]
                raise SystemExit(f'sea {sea["id"]}: no marine polygon named {n!r}; '
                                 f'candidates: {sorted(k for k in by_name if word in k)}')
        parts = [g for n in sea['ne'] for g in by_name[n]]
        for lon, lat in sea.get('points', []):
            hits = [(i, g) for i, (_, g) in enumerate(records) if g.contains(Point(lon, lat))]
            if not hits:
                raise SystemExit(f'sea {sea["id"]}: no marine polygon contains {(lon, lat)}')
            used.update(i for i, _ in hits)
            parts += [g for _, g in hits]
        geom = unary_union(parts)
        out.append({**_feature(sea['id'], sea['name'], geom, fit, 5), 'parent': sea['parent']})
    mapped = {n for sea in SEAS for n in sea['ne']}
    in_window = lambda g: not fit.clip(fit.to_metres(preclip(g))).is_empty
    for name, geoms in by_name.items():
        if name not in mapped and in_window(unary_union(geoms)):
            log(f'unmapped sea: {name}')
    for i, (rec, g) in enumerate(records):
        if not rec['name'] and i not in used and in_window(g):
            p = g.representative_point()
            log(f'unmapped sea: <unnamed> at ({p.x:.2f}, {p.y:.2f})')
    return out


RANGES: list[tuple[str, str, str | None]] = [
    ('m:CordiglieraCantabrica', 'Cordigliera Cantabrica', None),
    ('m:SierraNevada', 'Sierra Nevada', 'S. Nevada'),
    ('m:Pirenei', 'Pirenei', 'PYRENEES'),
    ('m:MassiccioCentrale', 'Massiccio Centrale', 'Massif Central'),
    ('m:Alpi', 'Alpi', 'ALPS'),
    ('m:Appennino', 'Appennino', None),
    ('m:AlpiDinariche', 'Alpi Dinariche', 'Dinaric Alps'),
    ('m:Balcani', 'Balcani', 'Balkan Mts.'),
    ('m:Carpazi', 'Carpazi', 'CARPATHIAN MOUNTAINS'),
    ('m:MontiScandinavi', 'Monti Scandinavi', 'KJØLEN MOUNTAINS'),
    ('m:Caucaso', 'Caucaso', 'CAUCASUS MTS.'),
    ('m:MontiUrali', 'Monti Urali', 'URAL MOUNTAINS'),
]


def build_ranges(records: list[tuple[dict, BaseGeometry]], handdrawn: Path, fit: Fit) -> list[dict]:
    """Ranges from NE geography regions (`name`), or from the CC0 hand-drawn file when ne is None."""
    drawn = {f['properties']['id']: shape(f['geometry'])
             for f in json.loads(handdrawn.read_text())['features']}
    out = []
    for fid, name, ne in RANGES:
        if ne is None:
            if fid not in drawn:
                raise SystemExit(f'range {fid}: missing from {handdrawn.name}')
            geom = drawn[fid]
        else:
            parts = [g for rec, g in records if rec['name'] == ne]
            if not parts:
                raise SystemExit(f'range {fid}: no region polygon named {ne!r}')
            geom = unary_union(parts)
        if fid == 'm:SierraNevada' and geom.bounds[2] >= 0:
            raise SystemExit('range m:SierraNevada: matched a polygon outside Spain')
        out.append(_feature(fid, name, geom, fit, 5))
    return out


BG_TOL_KM = 4  # land, countries, lakes
_WINDOW_BOX = box(*WINDOW)
_PRECLIP_BOX = box(*PRECLIP)  # land and countries: everything drawn on the canvas


def build_land(records: list[tuple[dict, BaseGeometry]], fit: Fit) -> list[dict]:
    """One land feature: the union of NE land polygons near the window."""
    geom = unary_union([g for _, g in records if g.intersects(_PRECLIP_BOX)])
    return [{'d': to_path(feature_to_canvas(geom, fit, BG_TOL_KM))}]


# Letters NFKD does not decompose into an ASCII base.
_TRANSLIT = str.maketrans({'æ': 'ae', 'Æ': 'Ae', 'ø': 'o', 'Ø': 'O', 'ß': 'ss', 'ð': 'd', 'Ð': 'D',
                           'þ': 'th', 'Þ': 'Th', 'ł': 'l', 'Ł': 'L', 'œ': 'oe', 'Œ': 'Oe'})


def _country_id(name: str) -> str:
    plain = ''.join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c))
    return 'c:' + ''.join(c for c in plain.translate(_TRANSLIT) if c.isascii() and c.isalnum())


def build_countries(records: list[tuple[dict, BaseGeometry]], fit: Fit) -> list[dict]:
    """Countries intersecting the pre-clip box, simplified per country (borders not topology-shared)."""
    out = []
    for rec, g in records:
        if not g.intersects(_PRECLIP_BOX):
            continue
        c = feature_to_canvas(g, fit, BG_TOL_KM)
        if c.is_empty:  # inside PRECLIP but off the canvas
            continue
        cx, cy = anchor(c)
        iso = rec['iso_a2'] if rec['iso_a2'] != '-99' else rec['iso_a2_eh']  # e.g. France, Norway
        out.append({'id': _country_id(rec['name_it']), 'name': rec['name_it'], 'iso': iso,
                    'd': to_path(c), 'cx': cx, 'cy': cy})
    ids = [c['id'] for c in out]
    if len(ids) != len(set(ids)):
        raise SystemExit(f'countries: duplicate ids {sorted({i for i in ids if ids.count(i) > 1})}')
    return out


def build_lakes(records: list[tuple[dict, BaseGeometry]], fit: Fit) -> list[dict]:
    """Major lakes (scalerank <= 3) intersecting the window."""
    out = []
    for rec, g in records:
        if rec['scalerank'] <= 3 and g.intersects(_WINDOW_BOX):
            d = to_path(feature_to_canvas(g, fit, BG_TOL_KM))
            if d:
                out.append({'name': rec['name'], 'd': d})
    return out


def build_cities(records: list[tuple[dict, BaseGeometry]], fit: Fit) -> list[dict]:
    """Stub: no cities yet.

    Future: capitals from ne_10m_populated_places_simple (`adm0cap == 1`, ranked by `pop_max`),
    each as {id: 't:<name>', name, cx, cy, capital, iso}.
    """
    return []


def build(cache: Path) -> dict:
    fit = Fit.from_window(WINDOW)
    rec = {name: read_shp(fetch(name, cache)) for name in DATASETS}
    return {'eu': {
        'w': W, 'h': H,
        'version': {'ne': read_version(cache, 'land'), 'built': date.today().isoformat()},
        'land': build_land(rec['land'], fit),
        'countries': build_countries(rec['countries'], fit),
        'lakes': build_lakes(rec['lakes'], fit),
        'rivers': build_rivers(rec['rivers'], fit),
        'seas': build_seas(rec['marine'], fit),
        'ranges': build_ranges(rec['regions'], HANDDRAWN, fit),
        'cities': build_cities(rec['places'], fit),
    }}


def write_data_js(data: dict, out: Path) -> None:
    body = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    out.write_text(f'// GENERATED by tools/build_data.py from Natural Earth {data["eu"]["version"]["ne"]}; '
                   f'do not edit.\nwindow.GEO = {body};\n', encoding='utf-8')


def main() -> None:
    write_data_js(build(CACHE), Path(__file__).resolve().parent.parent / 'data.js')


if __name__ == '__main__':
    main()
