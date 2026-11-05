# US federal data review, batch 2 (November 2026)

**Status: proposals only. Nothing here is reviewed until the steward for US federal sources signs off.**
An agent researched the 27 unreviewed data entries whose coverage is the United States on
2026-11-05, tested what it could reach and drafted overrides (`seed/overrides/<id>.yaml`, marked
PROPOSED). `review.state` stays `seeded` on every entry. Fetches were limited to addresses that a
web search returned, so some endpoints are listed as "not yet tested".

| Entry | Proposed decision | Machine-readable access found | To check before approving |
| --- | --- | --- | --- |
| bts-ntad | Keep | BTS geodata hub (named in the Fall 2026 release note); catalog CSV (not yet fetched) | Test the catalog |
| cropscape-cropland-data-layer | Keep; publisher is USDA NASS (entry says "Unknown") | CropScape services (base URL only) | Find and test the service endpoint |
| fcc-national-broadband-map | Keep as a lead | None tested | Whether the data API needs registration |
| fema-nfhl | Keep (additions to the existing override) | REST (existing), WMS, WFS from FEMA's service page | Layer 28 (existing note); WFS limit recorded |
| gnis | Keep; publisher fixed | Staged downloads on The National Map S3 (page read) | none beyond a download test |
| gssurgo-gnatsgo | Keep; publisher fixed | Soil Data Access REST, WFS, WMS (help page read) | Add the gSSURGO/gNATSGO download page |
| landfire | Keep | LANDFIRE Product Service (GP service) | Whether anonymous use is allowed; publisher |
| layercake-osm-us | Keep; publisher fixed; **coverage is global, not US** | Nine GeoParquet files (page read) | none |
| lightbox | Keep as a commercial lead (licence proprietary) | Not researched | Access terms (account or API key) |
| naip | Keep; publisher fixed | TNM NAIP ImageServer (tested) | none |
| national-address-database | Keep; publisher fixed | DOT file geodatabase download (data.gov record) | none |
| national-address-database-nad | **Merge** into national-address-database (same product) | (none) | Agree; then retire with replaced_by |
| national-geologic-map-database | Keep as a lead | None found | Find an NGMDB service (MapView, GeMS downloads) |
| neon-aop-lidar | Keep; publisher fixed | NEON data API (tutorial read) | Whether a token is needed for volume |
| nhd-nhdplus-hr | Keep for now; 3DHP added as the successor | NHDPlus HR and 3DHP map services (3DHP read) | Add a 3DHP entry, and retire NHD when USGS does |
| nlcd-annual-nlcd | Keep; publisher fixed | MRLC downloads; S3 requester-pays bucket (page read) | Requester-pays costs recorded |
| noaa-ncei | Keep as a lead (very broad) | None tested | Split into products (normals, storm events, bathymetry)? |
| nps-data-and-api | Keep | Not tested | API key requirement |
| pad-us | Keep; publisher fixed | PAD-US 4 downloads and feature layer views (page read) | none |
| prism | Keep; publisher fixed; terms recorded | Web service document (not read) | Licence value (custom: free with attribution, PRISM keeps copyright) |
| regrid | Keep as a commercial lead | Not researched | Access terms |
| reportall | Keep as a commercial lead | Not researched | Access terms |
| the-national-map-tnm | Keep; publisher fixed | TNM Access API (documented examples) | none |
| tiger-line-road-features | **Merge** into census-tiger-line (roads are a TIGER/Line layer) | (none) | Agree; add roads as a collection of census-tiger-line |
| usfws-national-wetlands-inventory | Keep | REST and WMS (FWS page read) | none |
| usgs-3dep | Keep | 3DEP ImageServer (tested) and project index | Add the EPT/COPC lidar access on AWS |
| usgs-national-map-basemaps | Keep | USGS Topo tile service (tested) | none |

Questions for the steward:
1. **Merges:** the two National Address Database entries, and TIGER road features into TIGER/Line.
2. **NHD to 3DHP:** add a 3DHP entry now and mark NHD for retirement when USGS retires it?
3. **Commercial parcel data** (LightBox, Regrid, ReportAll): keep as commercial leads, or leave
   commercial products out of the public registry?
4. **Very broad entries** (NOAA NCEI, the NPS API): split into the products people ask for?

## Evidence

## usgs-3dep
- https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer fetched: public
  ImageServer, bare-earth DEM from multi-resolution 3DEP sources, WKID 102100, 1 band F32, raster
  functions (hillshade, slope, aspect, contours), WMS and WCS enabled; copyright "USGS National
  Map 3D Elevation Program (3DEP). October 27, 2026."
- Index of 3DEP projects: https://index.nationalmap.gov/arcgis/rest/services/3DEPElevationIndex/MapServer (search result).

## the-national-map-tnm
- TNM Access API https://tnmaccess.nationalmap.gov/api/v1/products (documented by the University of
  Alabama libraries' API cookbook, fetched): parameters bbox, datasets (e.g. "Digital Elevation Model
  (DEM) 1 meter", "National Boundary Dataset (NBD)"), prodFormats, offset, max; examples need no key.

## nhd-nhdplus-hr
- https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer (search result).
- SUCCESSOR: https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/MapServer fetched: "the first
  of several data services the USGS 3D Hydrography Program will deliver"; flowlines, hydrolocations,
  waterbodies, catchments; elevation-derived hydrography "will replace the NHD data" as it is
  collected; data refreshed September 4, 2026. Also a FeatureServer.

## usfws-national-wetlands-inventory
- https://www.fws.gov/wetlands/data/web-map-services.html fetched: REST
  https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest ; WMS Wetlands
  https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/services/Wetlands/MapServer/WMSServer ;
  also Data_Source, WetlandsRaster, Wetlands_Status, Riparian. "updated biannually"; no terms stated.

## pad-us
- https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-web-services fetched: PAD-US 4
  (DOI https://doi.org/10.5066/P96WBCHS) as ArcGIS Online feature layer views (usgs.maps.arcgis.com
  items: GAP status, public access, fee managers, manager name/type, designation...); database
  download https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-download ;
  no terms stated on the page.

## national-address-database / national-address-database-nad (DUPLICATES)
- data.gov "National Address Database (NAD) File Geodatabase" fetched: publisher US DOT, rights
  public, updated 2026-09-30, download
  https://data.transportation.gov/download/yw36-suxr/application/x-zip-compressed (zip of a file
  geodatabase). Also a text-file version on data.gov. Landing page https://www.transportation.gov/nad
- Two registry entries describe the same product: propose MERGE (keep one, retire the other with
  replaced_by).

## nlcd-annual-nlcd
- https://www.usgs.gov/centers/eros/science/annual-nlcd-data-access fetched: Annual NLCD Collection 1
  (CONUS from 1985; ver. 1.2 listed June 2026); channels EarthExplorer, MRLC viewer and
  https://www.mrlc.gov/data , ScienceBase item 655ceb8ad34ee4b6e05cc51a, a WMS (instructions at
  https://www.mrlc.gov/data-services-page), AWS S3 requester-pays
  s3://usgs-landcover/annual-nlcd/c1/v0/<region>/mosaic/ (us-west-2). No data licence stated
  (USGS products are generally public domain: to confirm).

## naip
- ScienceBase item 5310c63ae4b0b4dfebd5ee9e (fetched) is OUTDATED: points to
  http://gis.apfo.usda.gov/arcgis/services (FSA/APFO). Current distribution still to find.
- CURRENT: https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer fetched:
  TNM's NAIP mosaic, primarily 0.6 m 4-band, WKID 102100, raster functions natural color, CIR,
  NDVI; copyright "USGS, USDA, The National Map: Orthoimagery. January 09, 2025"; the page says
  NAIP is public domain and free to download through the National Map Downloader.
  Index: https://index.nationalmap.gov/arcgis/rest/services/USGSNAIPImageryIndex/MapServer

## landfire
- https://lfps.usgs.gov/arcgis/rest/services/LandfireProductService/GPServer fetched: LANDFIRE Product
  Service (layers + area of interest -> multi-band GeoTIFF), asynchronous geoprocessing service; the
  page shows Login/Get Token links and a helpdesk note: whether anonymous use is allowed needs a test.

## gssurgo-gnatsgo
- https://sdmdataaccess.sc.egov.usda.gov/webservicehelp.aspx fetched: Soil Data Access REST
  https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest (query, aoi, interpretation, report; up to
  100,000 rows), WFS https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDMWGS84Geographic.wfs (also
  NAD83 and Web Mercator), WMS https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDM.wms; no key
  mentioned; no terms on the page. (SDA serves SSURGO; gSSURGO/gNATSGO are gridded downloads.)

## gnis
- https://www.usgs.gov/us-board-on-geographic-names/download-gnis-data fetched: staged products at
  https://prd-tnm.s3.amazonaws.com/index.html?prefix=StagedProducts%2FGeographicNames%2F (DomesticNames
  TXT, FullModel GDB/GPKG, Topical national zips such as
  https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/Topical/PopulatedPlaces_National_Text.zip);
  refreshed every other month; public domain.

## prism
- https://prism.oregonstate.edu/terms/ fetched: data "freely reproduced and distributed" with
  attribution (PRISM Group name, URL, access date; map copyright notice); PRISM Group, Oregon State
  University, retains ownership (copyright); silent on commercial use; "as is". Publisher fix:
  PRISM Group, Oregon State University (entry says "Unknown"). Web service document:
  https://www.prism.oregonstate.edu/documents/PRISM_downloads_web_service.pdf (search result).

## bts-ntad
- https://www.bts.gov/newsroom/bts-updates-datasets-national-transportation-atlas-database-fall-2026
  fetched: 26 layers updated 2026-10-23; downloads at https://geodata.bts.gov/ (FGDB, SHP, GeoJSON,
  CSV, KML); catalog CSV with each dataset's service URL
  https://hub.arcgis.com/api/feed/all/csv?target=geodata.bts.gov ; WFS per dataset; now updated on a
  rolling basis.

## neon-aop-lidar
- NEON API (tutorial fetched): https://data.neonscience.org/api/v0/ with products/, sites/, data/
  endpoints; discrete return lidar point cloud product DP1.30003.001. Publisher fix: National
  Ecological Observatory Network (NEON), operated by Battelle for the NSF (entry says "Unknown").
  Token not mentioned in the tutorial.

## fema-nfhl
- https://hazards.fema.gov/femaportal/resources/flood_map_svc.htm fetched: REST
  https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer (effective data only; also
  Preliminary, Pending, Draft services), WMS
  https://hazards.fema.gov/arcgis/rest/services/public/NFHLWMS/MapServer/WMSServer , WFS
  https://hazards.fema.gov/arcgis/services/public/NFHL/MapServer/WFSServer (1,000-feature cap; use
  the Map Service Center state/county downloads for bulk); preliminary/pending data not for rating
  insurance; TLS 1.2 only.

## layercake-osm-us
- https://layercake.openstreetmap.us/layers/ fetched: nine layers, each one GeoParquet file covering
  the whole planet (https://data.openstreetmap.us/layercake/<layer>.parquet); (c) OpenStreetMap
  contributors, ODbL.

## usgs-national-map-basemaps
- https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer fetched: cached tile base
  map, 24 levels, WKID 102100, refreshed 2026-09-04 (v1.2).

## cropscape-cropland-data-layer
- CropScapeR documentation (fetched): the GetCDLData service at https://nassgeodata.gmu.edu/CropScape ,
  by county or state FIPS, box, polygon or point, per year. Exact endpoint not confirmed.
