# Data review decisions, 2026-11-05

The project lead (wiatrek-kevin-s) approved every proposal in the four review batches (Texas, US federal batches 2 and 3,
global batch 1) on 2026-11-05. This file records how that approval was applied. Evidence for each entry is in the batch
files beside this one; endpoint tests are from two runs of the Health workflow on this branch the same day (GitHub
Actions runs 42021111623 and 42022242303), from GitHub's network.

## Rule

An approved **Keep** is recorded as `review.state: reviewed` only when at least one machine-readable access item
(anything but a plain web page) answered the Health check. Approved Keeps whose endpoints failed or that have only a
web page stay `seeded`, listed below with the reason, so Columbus never shows a source as verified without a working
endpoint. Merges and retirements are applied as approved.

## Reviewed (48)

| Entry | Endpoints that answered |
| --- | --- |
| capcog-data | api (no bbox yet: local coverage) |
| capmetro-gtfs | download (no bbox yet: local coverage) |
| city-of-austin-gis-arcgis | arcgis-rest (no bbox yet: local coverage) |
| city-of-austin-open-data | api (no bbox yet: local coverage) |
| h-gac-gis-data | api (no bbox yet: local coverage) |
| texas-orthoimagery-program-top | arcgis-rest |
| texas-water-development-board-gis | arcgis-rest |
| travis-county-gis | arcgis-rest (no bbox yet: local coverage) |
| txdot-open-data-portal | arcgis-rest |
| txdot-roadway-inventory-dfo-lrs | arcgis-rest, download |
| txgio-datahub | api |
| txgio-lidar | arcgis-rest |
| txgio-stratmap | arcgis-rest |
| bts-ntad | api |
| fema-nfhl | arcgis-rest, ogc-wfs, ogc-wms |
| gnis | download |
| gssurgo-gnatsgo | api, ogc-wfs |
| landfire | arcgis-rest |
| layercake-osm-us | download |
| naip | arcgis-rest |
| national-address-database | download |
| nhd-nhdplus-hr | arcgis-rest |
| the-national-map-tnm | api |
| usfws-national-wetlands-inventory | arcgis-rest, ogc-wms |
| usgs-3dep | arcgis-rest |
| usgs-national-map-basemaps | arcgis-rest |
| blm-navigator-plss-cadnsdi | arcgis-rest |
| epa-echo-frs | api, arcgis-rest |
| epa-enviroatlas | arcgis-rest |
| fhwa-hpms | api, arcgis-rest |
| noaa-digital-coast | s3 |
| noaa-ngs-cors-datums | s3 |
| usfs-fsgeodata-clearinghouse | arcgis-rest |
| usgs-3d-hydrography-program-3dhp | arcgis-rest, download |
| usgs-3dep-lidar-on-aws-ept | s3, stac |
| usgs-earthquake-hazards-api | api |
| watershed-boundary-dataset-wbd | arcgis-rest |
| copernicus-dem | s3, stac |
| esa-worldcover | s3 |
| esri-land-cover-10-m-annual-lulc | s3 |
| geoboundaries | api |
| global-building-footprints-models-microsoft | stac |
| jrc-global-surface-water | download, ogc-wmts |
| natural-earth | s3 |
| overture-maps-data | s3, stac |
| sentinel-1 | stac |
| sentinel-2 | stac |
| worldpop | api |

## Merged or retired (10)

| Entry | Decision |
| --- | --- |
| national-address-database-nad | Merged into national-address-database |
| tiger-line-road-features | Merged into census-tiger-line |
| noaa-digital-coast-data-access-viewer | Merged into noaa-digital-coast (its access moved there) |
| eoxhub-eox-sentinel-2-cloudless | Merged into eox-sentinel-2-cloudless |
| overture-buildings-theme, overture-places-theme, overture-transportation-theme, overture-divisions-theme, overture-maps-addresses | Merged into overture-maps-data (theme licences in its notes) |
| texas-dshs-gis | Retired: not a data source |

## Approved but still seeded (26): need a working endpoint

| Entry | Why |
| --- | --- |
| bureau-of-economic-geology-data | arcgis-rest failed |
| railroad-commission-of-texas-gis | download failed; download failed |
| texas-general-land-office-gis | no machine-readable access |
| texas-historical-commission-atlas | download failed |
| texas-parks-and-wildlife-gis | arcgis-rest failed |
| travis-central-appraisal-district | arcgis-rest failed |
| cropscape-cropland-data-layer | no machine-readable access |
| neon-aop-lidar | api failed |
| nlcd-annual-nlcd | s3 failed |
| nps-data-and-api | no machine-readable access |
| pad-us | no machine-readable access |
| prism | no machine-readable access |
| data-gov | needs a key, not probed |
| faa-aeronautical-data | no machine-readable access |
| geoplatform-gov | stac failed |
| noaa-atlas-14-pfds | no machine-readable access |
| noaa-open-data-dissemination-nodd | no machine-readable access |
| usfws-ecos-critical-habitat | arcgis-rest failed |
| usgs-water-data-apis-nwis | ogc-api-features failed |
| alos-world-3d-aw3d30 | no machine-readable access |
| chirps | no machine-readable access |
| eox-sentinel-2-cloudless | no machine-readable access |
| fabdem | no machine-readable access |
| gadm | no machine-readable access |
| gebco-grid | no machine-readable access |
| worldclim | no machine-readable access |

Also still seeded, as decided (leads without access to test): tceq-gis-data, fcc-national-broadband-map,
national-geologic-map-database, noaa-ncei, and the commercial leads lightbox, regrid and reportall.

## Other decisions recorded

- NHD and WBD stay as reference entries (no longer maintained by USGS); 3DHP is their successor.
- TxGIO's TOP, lidar and StratMap stay separate entries linked to txgio-datahub.
- Licences: each entry keeps its current value until the publisher states one; disclaimers go in notes.
- Non-commercial sources (GADM, WorldClim, FABDEM, EOX cloudless after 2016) stay, with licences recorded; Columbus
  recipes should prefer open alternatives (a Columbus-side change).
- Parcel data with owner names (TCAD, StratMap) is flagged for the design set's open question on field hiding.
- Six local entries (CAPCOG, CapMetro, the two City of Austin entries, H-GAC, Travis County) have no bbox yet; a
  statewide box would wrongly match every Texas county.
