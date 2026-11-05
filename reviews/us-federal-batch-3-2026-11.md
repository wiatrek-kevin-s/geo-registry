# US federal data review, batch 3 (November 2026)

**Status: proposals only. Nothing here is reviewed until the steward for US federal sources signs off.**
These are the 19 US federal entries that had no coverage region, flagged in
`reviews/coverage-unspecified-2026-11.md` (pull request #21). An agent researched them on 2026-11-05,
read the publishers' own pages where a web search returned them, and drafted overrides
(`seed/overrides/<id>.yaml`, marked PROPOSED) for 18. `review.state` stays `seeded` on every entry.
Endpoints were read through their service pages, not downloaded from; "read" below means the page or
service description was fetched.

| Entry | Proposed decision | Machine-readable access found | To check before approving |
| --- | --- | --- | --- |
| blm-navigator-plss-cadnsdi | Keep; coverage: PLSS states | National PLSS MapServer at the **new** `natlplss` path (read) | **BLM moved the service on 2026-10-14; the old `/arcgis/` path stops on 2027-02-01** |
| data-gov | Keep as a catalog; publisher fixed (GSA) | CKAN API at api.gsa.gov (documented) | Needs an api.data.gov key (`auth: api-key`) |
| epa-echo-frs | Keep | FRS map service, monthly geospatial download, FRS API (EPA's list read) | Whether ECHO itself needs its own access item |
| epa-enviroatlas | Keep | ArcGIS Server root (EPA page, updated 2026-09-30) | The entry's note asks whether EnviroAtlas survived 2025 cuts: the page is maintained, the services were not opened |
| faa-aeronautical-data | Keep; coverage only | None added | The entry's hub address is `adds-faa`; an API directory lists `ais-faa.opendata.arcgis.com`. Check which one FAA uses |
| fhwa-hpms | Keep | HPMS 2024 spatial (data.transportation.gov, GeoJSON); 2018 per-state FeatureServers (read) | The 2024 Socrata dataset is the current one; drop the 2018 services? |
| geoplatform-gov | Keep as a catalog; publisher fixed (FGDC) | STAC address from FGDC's status page (operational, 2026-10-22) | The STAC address is published as http only |
| noaa-atlas-14-pfds | Keep | ASCII grid directory and metadata pattern (read) | NOAA is preparing Atlas 15 as the successor; add it when published |
| noaa-digital-coast | **Merge** the Data Access Viewer entry into it? | (see below) | Agree on merge direction |
| noaa-digital-coast-data-access-viewer | Keep, or merge into noaa-digital-coast | Coastal lidar S3 bucket with tile indexes, STAC and COPC item collections (read) | Merge question above |
| noaa-ngs-cors-datums | Keep | CORS S3 bucket (read) | **From 2026-11-01 CORS data moved to NODD; legacy `geodesy.noaa.gov/corsdata/` paths stop working** |
| noaa-open-data-dissemination-nodd | Keep as a catalog; coverage Global | None added (a list of hundreds of datasets on AWS, Google and Azure) | Split into the datasets people ask for (GFS, NEXRAD, GHCN)? |
| usfs-fsgeodata-clearinghouse | Keep | EDW MapServer root and downloads page (read) | none |
| usfws-ecos-critical-habitat | Keep | ECOS Critical Habitat MapServer (read) | none |
| usgs-3d-hydrography-program-3dhp | Keep | 3DHP_all MapServer; 2025 download on ScienceBase (USGS page read) | none |
| usgs-3dep-lidar-on-aws-ept | Keep | Public EPT bucket and its STAC catalog (AWS registry page read) | The raw LAZ bucket is requester-pays; leave it out? |
| usgs-earthquake-hazards-api | Keep; coverage Global | FDSN event service (from the entry) | The service page could not be fetched here; test it |
| usgs-water-data-apis-nwis | Keep | OGC API at api.waterdata.usgs.gov/ogcapi (USGS blog read) | **waterservices.usgs.gov is decommissioned in Q1 2027**; Columbus should use only the new API |
| watershed-boundary-dataset-wbd | Keep as reference; publisher fixed (USGS) | WBD MapServer and staged downloads (read) | No longer updated since 2024 (3DHP replaces it); mark as superseded? |

Questions for the steward:
1. **Moved and retiring endpoints:** BLM PLSS (new path now, old one until 2027-02-01), NGS CORS (moved to NODD on
   2026-11-01), USGS WaterServices (gone in Q1 2027). The health check will catch the old ones failing; record the
   dates now?
2. **Legacy hydrography:** WBD, like NHD, is no longer maintained; keep both as reference with a pointer to 3DHP, or
   retire them with `replaced_by: usgs-3d-hydrography-program-3dhp`?
3. **Catalogs:** data.gov, GeoPlatform and NODD are catalogs of many sources rather than sources. Keep them as
   catalogs, or record their most-used datasets as their own entries?
4. **Merge:** the Digital Coast Data Access Viewer into Digital Coast (or the reverse).

## Evidence

## blm-navigator-plss-cadnsdi
- BLM announcement "BLM Changes Links to National Public Land Survey System GIS Dataset"
  (https://www.blm.gov/announcement/blm-changes-links-national-public-land-survey-system-gis-dataset, read): new URL
  https://gis.blm.gov/natlplss/rest/services/Cadastral/BLM_Natl_PLSS_CadNSDI/MapServer from 2026-10-14; the old
  https://gis.blm.gov/arcgis/rest/services/Cadastral/BLM_Natl_PLSS_CadNSDI/MapServer stays active until 2027-02-01.
- Old service's item info (read): PLSS grid in NAD 83 (townships, ranges, sections, intersected lands), public,
  "as is", not a legal survey; cite BLM.

## data-gov
- https://open.gsa.gov/api/datadotgov/ (read): base https://api.gsa.gov/technology/datagov/v3/, CKAN actions such as
  action/package_search, key from api.data.gov in the x-api-key header; DEMO_KEY for samples.

## epa-echo-frs
- https://epa.gov/frs/frs-data-resources (read): FRS Facilities Map Service (public)
  https://geodata.epa.gov/arcgis/rest/services/OEI/FRS_INTERESTS/MapServer; FRS API https://www.epa.gov/frs/frs-api;
  geospatial download (KMZ, CSV, monthly) https://www.epa.gov/frs/geospatial-data-download-service.

## epa-enviroatlas
- https://www.epa.gov/enviroatlas/enviroatlas-web-services (read): ArcGIS REST root
  https://enviroatlas.epa.gov/arcgis/rest/services; WMS and WFS links on each service page; "Last updated on
  September 30, 2026". National layers at sub-watershed scale, community layers at higher resolution.

## faa-aeronautical-data
- FAA ADDS notice 25-01 (June 2025, read): airport diagram GIS data on FAA's Open Data site from the August 2025
  cycle; the notice gives no site address.
- API directory entry for "FAA Aeronautical Information Services Open Data" (https://apis.io/apis/faa/faa-ais-open-data/,
  read; not an FAA page): hub https://ais-faa.opendata.arcgis.com/, FeatureServers under
  https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services, 73 datasets (airspace, runways, navaids,
  obstacles). Not added to the override until FAA's own address is confirmed.

## fhwa-hpms
- data.gov record "HPMS Spatial All Sections - 2024" (read): FHWA; on the ARNOLD network; GeoJSON, CSV, KML exports
  from https://data.transportation.gov/d/42um-tgh5; modified 2026-09-21.
- https://www.fhwa.dot.gov/Policyinformation/hpms/shapefiles.cfm (read): 2018 public release, one FeatureServer per
  state under https://geo.dot.gov/server/rest/services/Hosted/ (for example Texas_2018_PR).

## geoplatform-gov
- FGDC "Geospatial Platform status" (https://www.fgdc.gov/initiatives/geospatial-platform/geospatial_platform_status,
  read; modified 2026-10-22): all services operational, including search and http://stac.geoplatform.gov.

## noaa-atlas-14-pfds
- https://hdsc.nws.noaa.gov/pfds/pfds_gis.html (read): zipped ASCII grids with confidence limits for 12 volumes
  (Texas is volume 11, code tx); metadata at https://hdsc.nws.noaa.gov/pfds/meta/na14_vol{N}_{code}_grid_metadata.xml;
  directory https://hdsc.nws.noaa.gov/pub/hdsc/data/.

## noaa-digital-coast-data-access-viewer
- https://coast.noaa.gov/digitalcoast/tools/dav.html (read): lidar, imagery and land cover for US coasts, Alaska,
  Hawaii and territories; checkout in a web tool; no API named.
- https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/laz/geoid18/10423/index.html (read): a project folder with LAZ
  tiles, a tile index (shapefile and GeoPackage), a STAC collection and a COPC item collection.

## noaa-ngs-cors-datums
- https://geodesy.noaa.gov/CORS/data.shtml (read): "Effective November 1, 2026, public CORS data distribution moves
  primarily to the NOAA Open Data Dissemination (NODD) platform. Legacy paths, including geodesy.noaa.gov/corsdata/,
  will stop working." RINEX, station logs, coordinates (ITRF2020, NAD83(2011), (PA11), (MA11)) and orbits at
  https://noaa-cors-pds.s3.amazonaws.com/.

## noaa-open-data-dissemination-nodd
- https://www.noaa.gov/nodd/datasets (read): hundreds of datasets on AWS, Google Cloud and Azure, for example GFS,
  GHCN-Daily, ISD, NEXRAD Level 2; updated quarterly.

## usfs-fsgeodata-clearinghouse
- https://data.fs.usda.gov/geodata/edw/mapServices.php (read): nationwide datasets as map services at
  https://apps.fs.usda.gov/arcx/rest/services/EDW; downloads at https://data.fs.usda.gov/geodata/edw/datasets.php.

## usfws-ecos-critical-habitat
- https://mapsd.ecosphere.fws.gov/server/rest/services/Datawarehouse/Critical_Habitat/MapServer (read): final
  critical habitat designations, Web Mercator, JSON/GeoJSON/PBF queries, 2,000 records per request.

## usgs-3d-hydrography-program-3dhp
- https://www.usgs.gov/3d-hydrography-program/access-3dhp-data-products (read): 3DHP web services (last updated
  July 2026, new elevation-derived hydrography added quarterly); 2025 downloadable product on ScienceBase. In 2024
  USGS moved from maintaining NHD, WBD and NHDPlus HR to 3DHP; the legacy products "are no longer updated and
  maintained" and stay available for reference.
- Service: https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/MapServer (search result).

## usgs-3dep-lidar-on-aws-ept
- https://registry.opendata.aws/usgs-lidar/ (read): public EPT bucket usgs-lidar-public (us-west-2, no account) with
  STAC catalog https://usgs-lidar-stac.s3-us-west-2.amazonaws.com/ept/catalog.json; raw LAZ 1.4 in the
  requester-pays bucket usgs-lidar; public domain.

## usgs-earthquake-hazards-api
- https://earthquake.usgs.gov/fdsnws/event/1/ was returned by a search but could not be fetched from here; the
  entry's own access URL is kept.

## usgs-water-data-apis-nwis
- https://waterdata.usgs.gov/blog/api-waterservices-decom/ (read): "WaterServices will be decommissioned in the first
  quarter of 2027"; replacement https://api.waterdata.usgs.gov/ogcapi/ with a migration guide; in R
  `read_waterdata()`, in Python dataretrieval's `waterdata` module.

## watershed-boundary-dataset-wbd
- https://hydro.nationalmap.gov/arcgis/rest/services/wbd/FeatureServer/0 (read): WBDLine, hydrologic unit boundaries
  to 12 digits; credit USDA-NRCS, USGS and EPA.
- Legacy WBD map service and staged downloads listed on the 3DHP access page (above).
