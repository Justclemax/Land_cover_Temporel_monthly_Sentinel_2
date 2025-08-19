import argparse
from pathlib import Path
import ee
import os
from io import BytesIO
import geopandas as gpd
from dotenv import load_dotenv
from loguru import logger


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



if __name__ == "__main__":
    # Charger les variables d'environnement
    load_dotenv()

    # Parser CLI
    parser = argparse.ArgumentParser(description='Load a GeoJSON or Shapefile and display info')
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to the GeoJSON or Shapefile'
    )

    args = parser.parse_args()
    input_path = Path(args.input)

    # Charger le fichier
    gdf = loading_data(input_path)

    # Afficher un aperçu
    print(gdf.head())