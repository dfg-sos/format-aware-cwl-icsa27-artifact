"""Generate the small geodata files used by the fixtures (committed; rerun only to change them).

    uv run scenarios/fixtures/make_data.py

numpy, rasterio and fiona are dependencies of this artifact (`uv sync`); fiona needs Python < 3.14.
"""

from pathlib import Path

import fiona
import numpy as np
import rasterio
import rasterio.shutil
from rasterio.transform import from_origin

DATA = Path(__file__).parent / "data"


def raster(path: Path, crs: str) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        dtype="uint8",
        crs=crs,
        transform=from_origin(9.9, 49.8, 0.01, 0.01),
    ) as dst:
        dst.write(np.arange(16, dtype="uint8").reshape(1, 4, 4))


def vector(path: Path, driver: str, geom_type: str, coords: list) -> None:
    schema = {"geometry": geom_type, "properties": {"name": "str"}}
    with fiona.open(path, "w", driver=driver, crs="EPSG:4326", schema=schema) as dst:
        for i, c in enumerate(coords):
            dst.write({"geometry": {"type": geom_type, "coordinates": c}, "properties": {"name": f"f{i}"}})


def netcdf() -> None:
    """The GeoTIFF raster as NetCDF: a valid raster that is not a GeoTIFF (F1.3)."""
    rasterio.shutil.copy(DATA / "raster_4326.tif", DATA / "raster_4326.nc", driver="netCDF")


def broken() -> None:
    """Faulty inputs derived from the files above: GeoJSON content behind a .tif name (F2.2)
    and a GeoTIFF cut off inside its header (F5.1)."""
    (DATA / "roads_as.tif").write_bytes((DATA / "roads.geojson").read_bytes())
    (DATA / "raster_truncated.tif").write_bytes((DATA / "raster_4326.tif").read_bytes()[:TRUNCATE_AT])


TRUNCATE_AT = 64  # bytes; the IFD of raster_4326.tif is cut off

if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    raster(DATA / "raster_4326.tif", "EPSG:4326")
    lines = [[(9.93, 49.79), (9.95, 49.80)], [(9.92, 49.78), (9.94, 49.77)]]
    vector(DATA / "roads.geojson", "GeoJSON", "LineString", lines)
    vector(DATA / "roads.shp", "ESRI Shapefile", "LineString", lines)
    vector(DATA / "points.geojson", "GeoJSON", "Point", [(9.93, 49.79), (9.95, 49.80)])
    broken()
    netcdf()
    for p in sorted(DATA.iterdir()):
        print(p.name, p.stat().st_size)
