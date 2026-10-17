"""Build the eugeo map data from Natural Earth 1:10m shapefiles (public domain)."""
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import shapefile
import shapely
from pyproj import Transformer
from shapely.geometry import (GeometryCollection, LineString, MultiLineString,
                              MultiPolygon, Polygon, shape)
from shapely.geometry.base import BaseGeometry

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

CACHE = Path(__file__).resolve().parent / 'cache'

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


def main() -> None:
    for name in DATASETS:
        fetch(name, CACHE)
        print(f'{name}: {read_version(CACHE, name)}')


if __name__ == '__main__':
    main()
