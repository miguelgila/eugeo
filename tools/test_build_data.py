# tools/test_build_data.py
import json
import re

import pytest
from shapely.geometry import Polygon, LineString, MultiLineString
import build_data as b
from build_data import CACHE


@pytest.fixture(scope='module')
def fit():
    return b.Fit.from_window(b.WINDOW)


@pytest.fixture(scope='module')
def rivers_records():
    return b.read_shp(b.fetch('rivers', CACHE))


@pytest.fixture(scope='module')
def marine_records():
    return b.read_shp(b.fetch('marine', CACHE))


@pytest.fixture(scope='module')
def regions_records():
    return b.read_shp(b.fetch('regions', CACHE))


@pytest.fixture(scope='module')
def built():
    return b.build(CACHE)


def test_to_path_polygon_with_hole():
    p = Polygon([(0,0),(10,0),(10,10),(0,10)], [[(2,2),(4,2),(4,4),(2,4)]])
    assert b.to_path(p) == "M0.0 0.0L10.0 0.0L10.0 10.0L0.0 10.0ZM2.0 2.0L4.0 2.0L4.0 4.0L2.0 4.0Z"

def test_to_path_multiline():
    assert b.to_path(MultiLineString([[(0,0),(1,1)],[(2,2),(3,3)]])) == "M0.0 0.0L1.0 1.0M2.0 2.0L3.0 3.0"

def test_anchor_line_is_midpoint_of_longest_part():
    assert b.anchor(MultiLineString([[(0,0),(10,0)],[(0,5),(2,5)]])) == (5.0, 0.0)

def test_fit_maps_window_inside_canvas():
    f = b.Fit.from_window(b.WINDOW)
    for lon, lat in [(-25,33),(70,33),(70,72),(-25,72),(20,55)]:
        x, y = f.project(LineString([(lon,lat),(lon,lat)])).coords[0]
        assert b.MARGIN - 1 <= x <= b.W - b.MARGIN + 1 and b.MARGIN - 1 <= y <= b.H - b.MARGIN + 1

def test_fit_north_is_up():
    f = b.Fit.from_window(b.WINDOW)
    y_north = f.project(LineString([(10,70),(10,70)])).coords[0][1]
    y_south = f.project(LineString([(10,40),(10,40)])).coords[0][1]
    assert y_north < y_south

needs_rivers = pytest.mark.skipif(not (CACHE/'ne_10m_rivers_lake_centerlines').exists(), reason='no cache')

@needs_rivers
def test_each_river_has_all_parts(rivers_records, fit):
    out = b.build_rivers(rivers_records, fit)
    assert [r['id'] for r in out] == [r[0] for r in b.RIVERS]
    counts = {r[0]: sum(1 for rec,_ in rivers_records if rec['name_en'] in r[2]) for r in b.RIVERS}
    assert counts['r:Tago'] == 3 and counts['r:Reno'] == 4 and counts['r:Volga'] == 2  # River + Lake Centerline parts

@needs_rivers
def test_river_paths_nonempty_and_inside(rivers_records, fit):
    for r in b.build_rivers(rivers_records, fit):
        assert r['d'].startswith('M') and 0 <= r['cx'] <= b.W and 0 <= r['cy'] <= b.H

needs_marine = pytest.mark.skipif(not (CACHE/'ne_10m_geography_marine_polys').exists(), reason='no cache')

@needs_marine
def test_seas_cover_spec_list(marine_records, fit):
    out = b.build_seas(marine_records, fit, log=lambda *_: None)
    assert [s['id'] for s in out] == ['s:Mediterraneo','s:Ligure','s:Tirreno','s:Adriatico','s:Ionio','s:Egeo','s:MareDelNord','s:Baltico','s:Nero','s:Caspio','s:Atlantico']
    assert {s['id'] for s in out if s['parent']=='s:Mediterraneo'} == {'s:Ligure','s:Tirreno','s:Adriatico','s:Ionio','s:Egeo'}

@needs_marine
def test_unmapped_seas_are_logged(marine_records, fit):
    seen = []
    b.build_seas(marine_records, fit, log=seen.append)
    assert any('Sea of Marmara' in m for m in seen)
    assert not any('Gulf of Bothnia' in m for m in seen)
    for merged in ('Golfe du Lion', 'Waddenzee', 'Mecklenburger Bucht'):
        assert not any(merged in m for m in seen)

@needs_marine
def test_no_unnamed_baltic_polygon_left(marine_records, fit):
    seen = []
    b.build_seas(marine_records, fit, log=seen.append)
    pts = [tuple(map(float, m.split('(')[1].rstrip(')').split(','))) for m in seen if '<unnamed>' in m]
    assert not [(x, y) for x, y in pts if 9 <= x <= 30 and 53 <= y <= 66]

needs_regions = pytest.mark.skipif(not (CACHE/'ne_10m_geography_regions_polys').exists(), reason='no cache')

@needs_regions
def test_ranges_cover_spec_list(regions_records, fit):
    out = b.build_ranges(regions_records, b.HANDDRAWN, fit)
    assert [r['id'] for r in out] == [r[0] for r in b.RANGES]

def test_handdrawn_is_sane():
    gj = json.loads(b.HANDDRAWN.read_text())
    ids = {f['properties']['id'] for f in gj['features']}
    assert ids == {'m:Appennino','m:CordiglieraCantabrica'}
    for f in gj['features']:
        assert f['properties']['license'] == 'CC0-1.0' and 8 <= len(f['geometry']['coordinates'][0]) - 1 <= 15

@needs_regions
def test_sierra_nevada_is_the_spanish_one(regions_records, fit):
    sn = next(r for r in b.build_ranges(regions_records, b.HANDDRAWN, fit) if r['id']=='m:SierraNevada')
    assert sn['cx'] < b.W * 0.3

def test_preclip_tames_global_band(fit):
    band = Polygon([(-180,60),(180,60),(180,70),(-180,70)]).segmentize(1.0)
    g = b.feature_to_canvas(band, fit, 4)
    x0, y0, x1, y1 = g.bounds
    win_w = (fit.bbox[2] - fit.bbox[0]) * fit.scale
    assert not g.is_empty and x1 - x0 <= win_w + 0.5
    assert 0 <= x0 and x1 <= b.W and 0 <= y0 and y1 <= b.H

def test_preclip_drops_far_geometry(fit):
    asia = Polygon([(100,40),(120,40),(120,70),(100,70)]).segmentize(1.0)
    # contains the EPSG:3035 antipode (-170, -52): projects inside-out over the whole window
    antipode = Polygon([(-175,-60),(-165,-60),(-165,-45),(-175,-45)]).segmentize(1.0)
    for far in (asia, antipode):
        assert b.feature_to_canvas(far, fit, 4).is_empty

def test_country_id_strips_accents_and_spaces():
    assert b._country_id("Città del Vaticano") == 'c:CittadelVaticano'
    assert b._country_id("Costa d'Avorio") == 'c:CostadAvorio'
    assert b._country_id('Fær Øer') == 'c:FaerOer'

needs_all = pytest.mark.skipif(not all((CACHE/b._ne_name(n)).exists() for n in b.DATASETS), reason='no cache')

@needs_all
def test_all_targets_inside_canvas(built):
    for layer in ('rivers','seas','ranges'):
        for f in built['eu'][layer]:
            xs = [float(v) for v in re.findall(r'[ML](-?\d+\.\d)', f['d'])]
            ys = [float(v) for v in re.findall(r' (-?\d+\.\d)', f['d'])]
            assert min(xs) >= 0 and max(xs) <= b.W and min(ys) >= 0 and max(ys) <= b.H, f['id']
            # not clipped: the Urals and Caspian must not touch the right edge
    for fid in ('m:MontiUrali','s:Caspio'):
        f = next(x for layer in ('ranges','seas') for x in built['eu'][layer] if x['id']==fid)
        assert max(float(v) for v in re.findall(r'[ML](-?\d+\.\d)', f['d'])) < b.W - b.MARGIN + 0.5

@needs_all
def test_data_js_is_parseable(tmp_path, built):
    out = tmp_path/'data.js'; b.write_data_js(built, out)
    txt = out.read_text(); assert txt.startswith('// GENERATED')
    body = txt.split('window.GEO = ',1)[1].rstrip().rstrip(';')
    d = json.loads(body); assert set(d['eu']) == {'w','h','version','land','countries','lakes','rivers','seas','ranges','cities'}

@needs_all
def test_size_budget(tmp_path, built):
    out = tmp_path/'data.js'; b.write_data_js(built, out); assert out.stat().st_size < 600_000

@needs_all
def test_country_iso_falls_back_to_eh(built):
    iso = {c['id']: c['iso'] for c in built['eu']['countries']}
    assert iso['c:Francia'] == 'FR' and iso['c:Norvegia'] == 'NO'

@needs_all
def test_country_ids_unique_ascii(built):
    ids = [c['id'] for c in built['eu']['countries']]
    assert len(ids) == len(set(ids)) and all(i.isascii() for i in ids)

@needs_all
def test_greenland_sea_is_atlantic(built):
    atl = next(s for s in built['eu']['seas'] if s['id'] == 's:Atlantico')
    assert 'Greenland Sea' in next(s['ne'] for s in b.SEAS if s['id'] == 's:Atlantico') and atl['d']
