"""
Sentinel-2 Monthly Data Downloader for GeoJSON Points & Polygons

This script downloads Sentinel-2 Surface Reflectance (SR) values for points or polygons
provided in a GeoJSON file. It creates monthly median composites between a given start
and end date, normalizes the bands, and exports all sampled values into a single CSV file.

Features:
- Supports Point and Polygon geometries in GeoJSON.
- Handles files with missing labels (for inference).
- Splits large polygons to avoid GEE memory errors.
- Filters images based on maximum cloud cover.
- Normalizes each band to 0-1 range using unitScale.
- Exports a single CSV with all points/polygons and months.
"""

import argparse
from pathlib import Path
import ee
import os
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.geometry import box
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from loguru import logger
import geemap
from tqdm import tqdm
from shapely.geometry import Polygon, MultiPolygon

def loading_data(path_data: Path) -> gpd.GeoDataFrame:
    """Load a GeoJSON or shapefile into a GeoDataFrame."""
    try:
        data = gpd.read_file(path_data, driver="GeoJSON")
    except Exception as e:
        raise RuntimeError(f"⚠️ Failed to read {path_data}: {e}")
    if data.empty:
        raise ValueError(f"⚠️ The file {path_data} is empty or invalid.")
    logger.success(f"✅ Loaded {len(data)} records from {path_data}")
    logger.info(f"Columns: {list(data.columns)} | CRS: {data.crs}")
    return data


def split_polygon_grid(polygon, max_cells=4):
    """
    Split a large polygon into a grid of smaller polygons.
    max_cells: max number of subdivisions along x and y axis.
    """
    minx, miny, maxx, maxy = polygon.bounds
    x_steps = np.linspace(minx, maxx, max_cells + 1)
    y_steps = np.linspace(miny, maxy, max_cells + 1)

    small_polys = []
    for i in range(max_cells):
        for j in range(max_cells):
            b = box(x_steps[i], y_steps[j], x_steps[i + 1], y_steps[j + 1])
            inter = polygon.intersection(b)
            if not inter.is_empty:
                if inter.geom_type == "Polygon":
                    small_polys.append(inter)
                elif inter.geom_type == "MultiPolygon":
                    small_polys.extend(list(inter.geoms))
    return small_polys

def get_sentinel2_monthly(path_data, start_date, end_date, cloud_thresh=30,
                          label_col="landcover", output_file="all_points_s2.csv"):
    """
    Download Sentinel-2 monthly composites for GeoJSON Points & Polygons.
    Handles missing labels (inference) and large polygons.
    """
    try:
        gdf = loading_data(path_data)

        # Determine inference mode (no labels at all)
        if label_col not in gdf.columns or gdf[label_col].isnull().all():
            logger.info("⚠️ No labels found, download for inference only.")
            gdf_points = gdf.copy()
        else:
            # Drop only rows without labels
            gdf_points = gdf.dropna(subset=[label_col])

        if gdf_points.empty:
            logger.warning("⚠️ No valid points/polygons to process. Exiting.")
            return

        all_samples = []
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        for idx, row in tqdm(gdf_points.iterrows(), total=len(gdf_points), desc="Geometries"):

            geom_type = row.geometry.geom_type
            ee_geoms = []

            if geom_type == "Point":
                ee_geoms = [ee.Geometry.Point(row.geometry.coords[0])]
            elif geom_type == "Polygon":
                polys = split_polygon_grid(row.geometry, max_cells=4)
                ee_geoms = [ee.Geometry.Polygon(list(p.exterior.coords)) for p in polys]
            else:
                logger.warning(f"Geometry type {geom_type} not supported. Skipping geometry {idx}.")
                continue

            properties = {label_col: row[label_col]} if label_col in row and not pd.isna(row[label_col]) else {}

            for geom in ee_geoms:
                fc_geom = ee.FeatureCollection([ee.Feature(geom, properties)])
                current = start

                while current < end:
                    month_start = current
                    month_end = month_start + relativedelta(months=1) - pd.Timedelta(days=1)
                    if month_end > end:
                        month_end = end

                    tqdm.write(f"Processing geometry {idx}, Month {month_start.strftime('%Y-%m')}")

                    s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                          .filterBounds(fc_geom)
                          .filterDate(month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d'))
                          .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', cloud_thresh))
                          .select(['B1','B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12','B9'])
                          )

                    if s2.size().getInfo() == 0:
                        tqdm.write(f"  → No images found for geometry {idx}, Month {month_start.strftime('%Y-%m')}")
                        current += relativedelta(months=1)
                        continue

                    s2_median = s2.median()
                    band_names = s2_median.bandNames().getInfo()
                    s2_normalized = ee.Image.cat([s2_median.select(b).unitScale(0, 3000) for b in band_names])

                    sample = s2_normalized.sampleRegions(collection=fc_geom, properties=list(properties.keys()), scale=10)
                    df = geemap.ee_to_df(sample)
                    df['geometry_idx'] = idx
                    df['month'] = month_start.strftime('%Y-%m')
                    all_samples.append(df)

                    current += relativedelta(months=1)

        if all_samples:
            final_df = pd.concat(all_samples, ignore_index=True)
            final_df.to_csv(output_file, index=False)
            logger.success(f"✅ Export completed: {output_file}")
        else:
            logger.warning("⚠️ No data sampled. CSV not created.")

    except Exception as e:
        logger.error(e)

if __name__ == "__main__":
    load_dotenv()
    ee.Authenticate()
    ee.Initialize(project=os.getenv("EE_PROJECT"))

    parser = argparse.ArgumentParser(description='Download Sentinel-2 monthly composites for GeoJSON Points & Polygons')
    parser.add_argument('--input', type=str, required=True, help='Path to the GeoJSON with points/polygons')
    parser.add_argument('--start', type=str, required=True, help='Start date YYYY-MM-DD')
    parser.add_argument('--end', type=str, required=True, help='End date YYYY-MM-DD')
    parser.add_argument('--cloud', type=float, default=30, help='Max cloud percentage')
    parser.add_argument('--output', type=str, default='all_points_s2.csv', help='Output CSV file')

    args = parser.parse_args()
    input_path = Path(args.input)

    get_sentinel2_monthly(input_path, args.start, args.end, cloud_thresh=args.cloud, output_file=args.output)