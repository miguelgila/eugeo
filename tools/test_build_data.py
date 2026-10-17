# tools/test_build_data.py
from shapely.geometry import Polygon, LineString, MultiLineString
import build_data as b

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
