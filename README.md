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
