"""
Sentinel-2 Monthly Data Downloader for GeoJSON Points

This script downloads Sentinel-2 Surface Reflectance (SR) values for points
provided in a GeoJSON file. It creates monthly median composites between
a given start and end date, normalizes the bands, and exports all sampled
values into a single CSV file.

Features:
- Supports Point geometries in GeoJSON.
- Filters images based on maximum cloud cover.
- Normalizes each band to the 0-1 range using unitScale.
- Exports a single CSV with all points and months.
"""

import argparse
from pathlib import Path
import ee
import os
import geopandas as gpd
import pandas as pd
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from loguru import logger
import geemap
from tqdm import tqdm


def loading_data(path_data: Path) -> gpd.GeoDataFrame:
    """Load a GeoJSON (or shapefile) into a GeoDataFrame."""
    try:
        data = gpd.read_file(path_data, driver="GeoJSON")
    except Exception as e:
        raise RuntimeError(f"⚠️ Failed to read {path_data}: {e}")
    if data.empty:
        raise ValueError(f"⚠️The file {path_data} is empty or invalid.")
    logger.success(f"✅ Loaded {len(data)} records from {path_data}")
    logger.info(f"Columns: {list(data.columns)} | CRS: {data.crs}")
    return data

def gdf_to_fc(gdf, label_col="label"):
    """Convert GeoDataFrame to EE FeatureCollection (supports Point only for sampling)."""
    features = []
    for idx, row in gdf.iterrows():
        if row.geometry.geom_type != 'Point':
            logger.warning(f"Feature {idx} is not a Point. Skipping.")
            continue
        geom = ee.Geometry.Point(row.geometry.coords[0])
        features.append(ee.Feature(geom, {label_col: row[label_col]}))
    return ee.FeatureCollection(features)

def get_sentinel2_monthly(path_data, start_date, end_date, cloud_thresh=30,
                          label_col="landcover", output_file="all_points_s2.csv"):
    """
    Download Sentinel-2 monthly composites and extract bands for each point.
    Exports a single CSV containing all points and months.
    """
    try:
        gdf = loading_data(path_data)
        all_samples = []

        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        for poly_idx, row in tqdm(gdf.iterrows(), total=len(gdf), desc="Polygons"):
            if row.geometry.geom_type != 'Point':
                logger.warning(f"Polygon {poly_idx} is not a Point. Skipping.")
                continue

            geom = ee.Geometry.Point(row.geometry.coords[0])
            fc_poly = ee.FeatureCollection([ee.Feature(geom, {label_col: row[label_col]})])

            current = start
            while current < end:
                month_start = current
                month_end = month_start + relativedelta(months=1) - pd.Timedelta(days=1)
                if month_end > end:
                    month_end = end

                tqdm.write(f"Processing Polygon {poly_idx}, Month {month_start.strftime('%Y-%m')}")

                s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                      .filterBounds(fc_poly)
                      .filterDate(month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d'))
                      .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', cloud_thresh))
                      .select(['B1','B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12','B9'])
                      )

                if s2.size().getInfo() == 0:
                    tqdm.write(f"  → No images found for Polygon {poly_idx}, Month {month_start.strftime('%Y-%m')}")
                    current += relativedelta(months=1)
                    continue

                s2_median = s2.median()
                band_names = s2_median.bandNames().getInfo()
                s2_normalized = ee.Image.cat([s2_median.select(b).unitScale(0, 3000) for b in band_names])

                sample = s2_normalized.sampleRegions(collection=fc_poly, properties=[label_col], scale=10)
                df = geemap.ee_to_df(sample)
                df['polygon_idx'] = poly_idx
                df['month'] = month_start.strftime('%Y-%m')
                all_samples.append(df)

                current += relativedelta(months=1)

        if all_samples:
            final_df = pd.concat(all_samples, ignore_index=True)
            final_df.to_csv(output_file, index=False)
            logger.success(f"✅ Export terminé : {output_file}")
        else:
            logger.warning("⚠️ No data sampled. CSV not created.")

    except Exception as e:
        logger.error(e)

if __name__ == "__main__":
    load_dotenv()
    ee.Authenticate()
    ee.Initialize(project=os.getenv("EE_PROJECT"))

    parser = argparse.ArgumentParser(description='Download Sentinel-2 monthly composites for GeoJSON points')
    parser.add_argument('--input', type=str, required=True, help='Path to the GeoJSON with points')
    parser.add_argument('--start', type=str, required=True, help='Start date YYYY-MM-DD')
    parser.add_argument('--end', type=str, required=True, help='End date YYYY-MM-DD')
    parser.add_argument('--cloud', type=float, default=30, help='Max cloud percentage')
    parser.add_argument('--output', type=str, default='all_points_s2.csv', help='Output CSV file')

    args = parser.parse_args()
    input_path = Path(args.input)

    get_sentinel2_monthly(input_path, args.start, args.end, cloud_thresh=args.cloud, output_file=args.output)