import argparse
from pathlib import Path
import ee
import os
import numpy as np
import geopandas as gpd
from dotenv import load_dotenv
from loguru import logger
import geemap
from tqdm import tqdm

def loading_data(path_data: Path) -> gpd.GeoDataFrame:
    """
    Load a GeoJSON (or shapefile) into a GeoDataFrame.
    """
    try:
        data = gpd.read_file(path_data, driver="GeoJSON")
    except Exception as e:
        raise RuntimeError(f"⚠️ Failed to read {path_data}: {e}")

    if data.empty:
        raise ValueError(f"⚠️The file {path_data} is empty or invalid.")

    logger.success(f"✅ Loaded {len(data)} records from {path_data}")
    logger.info(f"Columns: {list(data.columns)}")
    logger.info(f"CRS: {data.crs}")

    return data

def gdf_to_fc(gdf, label_col="label"):
    """Convert GeoDataFrame to EE FeatureCollection."""
    features = []

    for idx, row in gdf.iterrows():
        geom_type = row.geometry.geom_type

        # Vérifier si le type est supporté
        if geom_type not in ['Point', 'LineString', 'Polygon', 'MultiPolygon']:
            logger.warning(f"Feature {idx} is not a supported geometry. Skipping.")
            continue
        # Convertir en EE Geometry selon le type
        if geom_type == 'Point':
            geom = ee.Geometry.Point(row.geometry.coords[0])
        elif geom_type == 'LineString':
            geom = ee.Geometry.LineString(list(row.geometry.coords))
        else:  # Polygon ou MultiPolygon
            if geom_type == 'Polygon':
                geom_coords = [list(row.geometry.exterior.coords)]
            else:  # MultiPolygon
                geom_coords = [list(poly.exterior.coords) for poly in row.geometry.geoms]
            geom = ee.Geometry.Polygon(geom_coords)

        # Creating the  feature
        feature = ee.Feature(geom, { "label": row[label_col] })
        features.append(feature)

    return ee.FeatureCollection(features)





def normalize(array):
    """Normalize a numpy array to the range 0.0 - 1.0"""
    array_min, array_max = np.nanmin(array), np.nanmax(array)

    if array_max == array_min:
        return np.zeros_like(array)

    return (array - array_min) / (array_max - array_min)



def get_sentinel2(path_data, start_date, end_date, cloud_thresh=30,
        label_col="landcover", output_file="training_s2.geojson"):
    """Download Sentinel-2 composite and extract bands for each point, with tqdm progress bar."""
    try:
        gdf = loading_data(path_data)
        fc_list = []

        # Parcourir chaque feature avec tqdm
        for idx, row in tqdm(gdf.iterrows(), total=len(gdf), desc="Processing points"):
            geom_type = row.geometry.geom_type
            if geom_type != 'Point':
                logger.warning(f"Feature {idx} is not a Point. Skipping.")
                continue
            geom = ee.Geometry.Point(row.geometry.coords[0])
            feature = ee.Feature(geom, {label_col: row[label_col]})
            fc_list.append(feature)

        if not fc_list:
            raise ValueError("⚠️ No valid points to process!")

        fc = ee.FeatureCollection(fc_list)

        # Filtrer Sentinel-2 SR
        s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
              .filterBounds(fc)
              .filterDate(start_date, end_date)
              .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', cloud_thresh))
              .select([
                  'B1','B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12','B9'
              ])
        )

        # Composite médian
        s2_median = s2.median()

        # Normaliser chaque bande
        band_names = s2_median.bandNames().getInfo()
        normalized_bands = []

        for band in band_names:
            normalized = s2_median.select(band).unitScale(0, 3000)  # Sentinel-2 SR 0-3000 approx
            normalized_bands.append(normalized)

        s2_normalized = ee.Image.cat(normalized_bands)

        # Sample les valeurs pour chaque point
        sample = s2_normalized.sampleRegions(
            collection=fc,
            properties=[label_col],
            scale=10
        )

        # Export local GeoJSON
        geemap.ee_export_vector(sample, filename=output_file)
        logger.success(f"✅ Export terminé : {output_file}")

    except Exception as e:
        logger.error(e)

if __name__ == "__main__":
    # Charger les variables d'environnement
    load_dotenv()
    ee.Authenticate()
    ee.Initialize(project=os.getenv("EE_PROJECT"))

    # Parser CLI
    parser = argparse.ArgumentParser(description='Download Sentinel-2 values for each point in a GeoJSON')
    parser.add_argument('--input', type=str, required=True, help='Path to the GeoJSON with points')
    parser.add_argument('--start', type=str, required=True, help='Start date YYYY-MM-DD')
    parser.add_argument('--end', type=str, required=True, help='End date YYYY-MM-DD')
    parser.add_argument('--cloud', type=float, default=30, help='Max cloud percentage')
    parser.add_argument('--output', type=str, default='training_s2.geojson', help='Output GeoJSON file')

    args = parser.parse_args()
    input_path = Path(args.input)

    # Télécharger les valeurs Sentinel-2
    get_sentinel2(input_path, args.start, args.end, args.cloud, output_file=args.output)