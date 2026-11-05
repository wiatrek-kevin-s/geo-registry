# Coverage for the 90 data entries with none (proposal, November 2026)

Proposed `coverage.region` for each seeded data entry that has none, so the full review can be
batched by area (Texas, US federal, global). Proposals from the entries' own names and summaries
and common knowledge; nothing is changed by this file. Flags: **federal** joins the next US
federal batch; **not data** proposes Retire (not a data source) or moving the entry to software;
**duplicate?** proposes a merge; **check status** needs a check that the source still exists.

| Entry | Proposed region | Flag | Note |
| --- | --- | --- | --- |
| advan | United States | commercial | Commercial foot-traffic data (formerly SafeGraph Patterns). |
| arcgis-living-atlas-of-the-world | Global | duplicate? | Same catalog as esri-living-atlas: merge. |
| arcgis-pretrained-geoai-models | Global | not data | Deep learning models, not data; overlaps arcgis-pretrained-models-living-atlas. |
| arcgis-pretrained-models-living-atlas | Global | not data | Deep learning models, not data. |
| arcgis-streetmap-premium-locators | Global | commercial | Licensed locators (software data); commercial. |
| awesome-gee-community-catalog | Global | catalog |  |
| aws-open-data-registry | Global | duplicate? | Same as aws-registry-of-open-data: merge. |
| aws-registry-of-open-data | Global | catalog |  |
| bbbike-extracts | Global |  |  |
| blacksky | Global | commercial |  |
| blm-navigator-plss-cadnsdi | United States | federal | Federal batch. |
| capella-space | Global | commercial |  |
| clay-foundation-model | Global | not data | A model, not data. |
| copernicus-land-monitoring-service | Europe and global |  |  |
| data-gov | United States | federal catalog | Federal batch. |
| daylight-map-distribution | Global | check status | Meta's Daylight distribution: check it is still published. |
| ejscreen | United States | check status | EPA EJScreen: check it is still published by EPA. |
| epa-echo-frs | United States | federal | Federal batch. |
| epa-enviroatlas | United States | federal | Federal batch. |
| epsg-geodetic-parameter-dataset | Global | reference | Reference registry (CRS definitions) rather than map data: keep as reference or move. |
| esri-living-atlas | Global | catalog |  |
| faa-aeronautical-data | United States | federal | Federal batch. |
| fhwa-hpms | United States | federal | Federal batch. |
| gedi | Global |  | NASA; near-global (about 52 N to 52 S). |
| geo-mcp-servers-curated-list | Global | not data | A list of software, not data. |
| geoanalystbench | Global | not data | An LLM benchmark, not geospatial data. |
| geobenchx | Global | not data | An LLM benchmark, not geospatial data. |
| geofabrik-downloads | Global |  |  |
| geogpt | Global | not data | Language models, not data. |
| geoplatform-gov | United States | federal catalog | Federal batch. |
| google-earth-engine-data-catalog | Global | catalog |  |
| google-open-buildings | Africa, Asia, Latin America |  |  |
| harmonized-landsat-sentinel-2-hls | Global |  |  |
| hdx-humanitarian-data-exchange | Global | catalog |  |
| hifld-open | United States | check status | The summary itself says 'former' portal: likely retire, with successors. |
| icesat-2-atl03-atl08 | Global | duplicate? | Overlaps icesat-2: merge as collections. |
| icesat-2 | Global |  |  |
| iceye | Global | commercial |  |
| landsat-collection-2 | Global |  |  |
| lp-daac | Global | archive |  |
| maxar-open-data-program | Global | check status | Maxar is now Vantor (see vantor-formerly-maxar): check the program's current name and host. |
| microsoft-building-footprints | Global |  |  |
| microsoft-planetary-computer-catalog | Global | catalog |  |
| mobility-database | Global | catalog |  |
| modis | Global |  |  |
| nasa-earthdata | Global | portal |  |
| nasadem | Global (60 N to 56 S) |  |  |
| nearmap | US, Australia, Canada, NZ | commercial |  |
| nhgis-ipums | United States |  | Historical US census tables and boundaries (University of Minnesota). |
| noaa-atlas-14-pfds | United States | federal | Federal batch. |
| noaa-digital-coast-data-access-viewer | United States | duplicate? | Part of noaa-digital-coast: merge. |
| noaa-digital-coast | United States | federal | Federal batch. |
| noaa-ngs-cors-datums | United States | federal | Federal batch. |
| noaa-open-data-dissemination-nodd | Global | federal | Federal batch (global datasets). |
| npmrds | United States | restricted | FHWA probe speeds; access is limited to agencies: check. |
| olmoearth | Global | not data | Models and platform, not data. |
| openstreetmap-standard-tile-layer | Global | service | Tile service with a strict usage policy. |
| opentopomap | Global | service |  |
| opera-products-dswx-dist-rtc | North America and global |  |  |
| osm-carto | Global | not data | A stylesheet, not data. |
| osm-on-aws-open-data | Global |  |  |
| planet-basemaps | Global | commercial |  |
| planet-osm | Global |  |  |
| precisely | Global | commercial |  |
| prithvi-eo-2-0 | Global | not data | A model, not data; overlaps prithvi-ibm-nasa. |
| prithvi-ibm-nasa | Global | not data | Models, not data. |
| proj-data | Global | reference | Datum grids used by PROJ: reference data for software; keep as reference. |
| protomaps-basemaps | Global |  |  |
| radiant-mlhub-source-cooperative-ml-data | Global | duplicate? | Now hosted on Source Cooperative: merge with source-cooperative? |
| safegraph | Global | commercial |  |
| satellogic | Global | commercial |  |
| satlaspretrain-models | Global | not data | Models, not data. |
| satlaspretrain | Global | training data | A training dataset (keep) or merge with its models entry. |
| source-cooperative | Global | catalog |  |
| ssl4eo-s12 | Global | training data |  |
| ssurgo | United States | duplicate? | Same survey as gssurgo-gnatsgo (Soil Data Access serves both): merge, or keep SSURGO as the vector product. |
| stac-index | Global | catalog |  |
| terramind | Global | not data | A model, not data. |
| umbra | Global | commercial | Has an open data program too. |
| usfs-fsgeodata-clearinghouse | United States | federal | Federal batch. |
| usfws-ecos-critical-habitat | United States | federal | Federal batch. |
| usgs-3d-hydrography-program-3dhp | United States | federal | Federal batch; the successor to nhd-nhdplus-hr. |
| usgs-3dep-lidar-on-aws-ept | United States | federal | Federal batch; link from usgs-3dep. |
| usgs-earthexplorer | Global | portal |  |
| usgs-earthquake-hazards-api | Global | federal | Federal batch (global catalog). |
| usgs-sciencebase | United States | catalog |  |
| usgs-water-data-apis-nwis | United States | federal | Federal batch. |
| vantor-formerly-maxar | Global | commercial |  |
| viirs | Global |  |  |
| watershed-boundary-dataset-wbd | United States | federal | Federal batch. |

Counts: 90 entries; no flag 17, federal 16, not data 13, commercial 12, catalog 10, duplicate? 6, check status 4, federal catalog 2, reference 2, portal 2, service 2, training data 2, archive 1, restricted 1.
