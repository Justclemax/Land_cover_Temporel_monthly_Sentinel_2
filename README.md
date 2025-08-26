# Land_cover_Temporel_monthly_Sentinel_2

## 🎯 Objectif du projet

Ce projet vise à analyser l’évolution de la couverture du sol à l’aide des images Sentinel-2, en créant des composites mensuels pour capturer la dynamique temporelle.

## 🚀 Description
- Charger des points depuis un fichier GeoJSON.  
- Télécharger automatiquement les données Sentinel-2 SR pour chaque point, filtrées selon le pourcentage de nuages.  
- Créer des composites mensuels (médiane) et normaliser les bandes spectrales.
- Exporter un CSV final regroupant toutes les observations temporelles pour chaque point.
- Calculer des indices spectraux (NDVI, NDWI, NBR, EVI…) pour enrichir les données.  
- Préparer un jeu de données complet pour entraîner un modèle de Machine Learning de classification de la couverture du sol.  

## 🛠️ Installation et préparation du projet (Bash)

```bash
# 1. Cloner le projet depuis GitHub
git clone https://github.com/Justclemax/Land_cover_Temporel_monthly_Sentinel_2.git

# 2. Entrer dans le dossier du projet
cd Land_cover_Temporel_monthly_Sentinel_2

# 3. Créer un dossier pour les données
mkdir data

# 4. Placer le fichier GeoJSON de vos points dans le dossier data
# Exemple: data/landcover.geojson

# 5. Créer un environnement Python >= 3.11
python3.11 -m venv .venv

# 6. Activer l'environnement
# Sur Linux/Mac
source .venv/bin/activate
# Sur Windows
.venv\Scripts\activate

# 7. Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# 8. Authentification Google Earth Engine (une seule fois)
earthengine authenticate

# 9. Créer un fichier .env à la racine du projet
touch .env

# Ajouter la ligne suivante dans .env
EE_PROJECT=Votre_nom_de_projet_EE
  

# 10. Télécharger les données Sentinel-2 pour vos points GeoJSON
cd src 
python gee_data_download.py \
  --input data/landcover.geojson \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --cloud 60 \
  --output data/all_points_s2.csv

# 11. Lancer Jupyter Notebook pour entraîner le modèle
jupyter notebook