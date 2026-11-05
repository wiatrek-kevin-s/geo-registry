# Global data review, batch 1 (November 2026)

**Status: proposals only. Nothing here is reviewed until a steward for global sources signs off.**
The first global batch covers the 24 most-asked worldwide sources among the 41 entries whose coverage is
already Global: elevation, imagery, land cover, buildings, boundaries, water, population and climate. An
agent read the publishers' pages and cloud registries on 2026-11-05 and drafted overrides for 17 of them
(`seed/overrides/<id>.yaml`, marked PROPOSED). `review.state` stays `seeded` everywhere. S3 addresses
are the HTTPS form of buckets named on the AWS registry pages; they have not been listed from here.

| Entry | Proposed decision | Machine-readable access found | To check before approving |
| --- | --- | --- | --- |
| alos-world-3d-aw3d30 | Keep; publisher fixed (JAXA) | None added | JAXA's terms say free of charge; commercial use and redistribution are not stated there |
| chirps | Keep; publisher fixed | None added | CHIRPS3 announced 2026-06-10 with no download address or licence on the page; the entry says CC0 |
| copernicus-dem | Keep; publisher fixed | GLO-30 COGs on S3; Earth Search STAC | none |
| eox-sentinel-2-cloudless | Keep; publisher fixed | None added | 2016 is CC BY 4.0, 2018-2025 CC BY-NC-SA 4.0 (EOX page): one entry or one per licence? |
| eoxhub-eox-sentinel-2-cloudless | **Merge** into eox-sentinel-2-cloudless (same product) | (none) | Agree; retire with replaced_by |
| esa-worldcover | Keep | S3 (2020 v100, 2021 v200); Terrascope STAC | none |
| esri-land-cover-10-m-annual-lulc | Keep; publisher Impact Observatory and Esri | S3, 2017-2024 COGs | none |
| fabdem | Keep; publisher fixed | None added | CC BY-NC-SA 4.0 (non-commercial) already recorded; find the University of Bristol download |
| gadm | Keep as non-commercial | (unchanged) | GADM's licence: "Redistribution or commercial use is not allowed without prior permission" (matches the entry). Prefer geoBoundaries in recipes? |
| gebco-grid | Keep; publisher fixed | None added | Public domain with attribution required; not for navigation |
| geoboundaries | Keep; publisher fixed | API pattern (GitHub README) | Licence: the README says CC BY 4.0 / ODbL; the entry says CC BY 4.0 |
| global-building-footprints-models-microsoft | Keep; publisher fixed | Planetary Computer STAC (ms-buildings) | none |
| jrc-global-surface-water | Keep | V1.5 tiles (CloudFerro listing); WMTS for display | none |
| natural-earth | Keep; publisher fixed (NACIS) | S3 (zipped shapefiles) | none |
| overture-maps-data | Keep as the parent entry | S3 GeoParquet by release; STAC | Merge the five theme entries into it as collections? |
| overture-buildings-theme, -places-theme, -transportation-theme, -divisions-theme, overture-maps-addresses | **Merge** into overture-maps-data as collections? | (parent's) | Licences differ by theme (ODbL for OSM-derived themes, CDLA-Permissive-2.0 otherwise); Overture's FAQ points to its attribution page, not read |
| sentinel-1 | Keep; publisher fixed | Earth Search sentinel-1-grd | Some assets requester-pays |
| sentinel-2 | Keep; publisher fixed | Earth Search sentinel-2-l2a | none |
| worldclim | Keep as non-commercial; publisher fixed | None added | WorldClim: "Redistribution or commercial use is not allowed without prior permission" (matches the entry) |
| worldpop | Keep; publisher fixed | REST catalogue (WorldPop API page) | Rate limits page not read |

Not in this batch (17 more Global entries, for batch 2): alphaearth-foundations-satellite-embedding,
dynamic-world, era5-copernicus-climate-data-store, foursquare-open-source-places, geonames, ghsl,
global-forest-watch, kartaview, mapillary, nasa-gibs, openaddresses, openaerialmap, panoramax, sentinel-3,
sentinel-5p, srtm, who-s-on-first; plus the about 60 entries `reviews/coverage-unspecified-2026-11.md`
proposes to make Global.

Questions for the steward:
1. **Overture:** one entry with themes as collections (each with its own licence), or keep six entries?
2. **Non-commercial sources** (GADM, WorldClim, FABDEM, EOX cloudless after 2016): keep with their licence
   recorded, and have recipes prefer open alternatives (geoBoundaries, Copernicus DEM)?
3. **Earth Search** serves Sentinel-1, Sentinel-2, Landsat and Copernicus DEM: record it once as a catalogue entry
   as well as on each source?

## Evidence

## copernicus-dem
- https://registry.opendata.aws/copernicus-dem/ (read): buckets copernicus-dem-30m (GLO-30) and copernicus-dem-90m
  (GLO-90), eu-central-1, COGs, Copernicus licence terms, managed by Sinergise.
- Readme at https://copernicus-dem-30m.s3.amazonaws.com/readme.html (search result).

## esa-worldcover
- https://registry.opendata.aws/esa-worldcover-vito/index.html (read): bucket esa-worldcover, eu-central-1, public;
  2020 v100 and 2021 v200; CC BY 4.0; managed by VITO; STAC https://services.terrascope.be/stac/.

## esri-land-cover-10-m-annual-lulc
- https://registry.opendata.aws/io-lulc/ (read): bucket io-10m-annual-lulc, us-west-2, public; 2017-2024; CC BY 4.0;
  managed by Impact Observatory; STAC at api.impactobservatory.com.

## sentinel-1, sentinel-2 (and copernicus-dem)
- https://github.com/element84/earth-search (read): STAC API https://earth-search.aws.element84.com/v1, collections
  sentinel-2-l2a (about 21.7 million items), sentinel-1-grd, landsat-c2-l2, cop-dem-glo-30 and -90; free, no
  guaranteed service; requester-pays assets use s3:// addresses.

## eox-sentinel-2-cloudless
- https://cloudless.eox.at/license-non-commercial (read): 2016 CC BY 4.0; 2018-2025 CC BY-NC-SA 4.0.

## overture-maps-data
- https://docs.overturemaps.org/getting-data (read): s3://overturemaps-us-west-2/release/{release}/theme={theme}/type={type}/*,
  example release 2026-10-21.0; GeoParquet; STAC https://stac.overturemaps.org/catalog.json.
- https://overturemaps.org/about/faq/ (read): CDLA-Permissive-2.0 where possible; several themes carry ODbL because
  they use OpenStreetMap data; per-theme list on docs.overturemaps.org/attribution/ (not read).

## global-building-footprints-models-microsoft
- https://planetarycomputer.microsoft.com/api/stac/v1/collections/ms-buildings (read): ODbL-1.0; Microsoft; over 999
  million buildings from Bing imagery 2014-2021; GeoParquet on Azure account bingmlbuildings, container footprints.

## geoboundaries
- https://github.com/wmgeolab/geoBoundaries (read): API https://www.geoboundaries.org/api/current/gbOpen/[ISO3]/[ADM]/
  ("ALL" allowed; gbAuthoritative, gbHumanitarian); latest tagged release 6.0.0 (2023-09-14), API current is updated
  continuously; "CC BY 4.0 / ODbL".

## gadm
- https://gadm.org/license.html (read): "Redistribution or commercial use is not allowed without prior permission."

## natural-earth
- https://registry.opendata.aws/naturalearth (read): bucket naturalearth, us-west-2, zipped shapefiles, public
  domain, managed by NACIS.

## jrc-global-surface-water
- https://global-surface-water.appspot.com/download (read): V1.5 covers 1984-2024; file listing
  https://s3.waw4-1.cloudferro.com/swift/v1/global-surface-water/; WMTS for display; free of charge without
  restriction (Copernicus), cite Pekel et al. (2016); attribution "Source: EC JRC/Google".

## worldpop
- https://www.worldpop.org/sdi/introapi/ (read): https://www.worldpop.org/rest/data, JSON; e.g. rest/data/pop/wpgp?iso3=AUS.

## gebco-grid
- https://www.gebco.net/data-products/gridded-bathymetry/terms-of-use (read): public domain, attribution required,
  commercial use allowed, not for navigation.

## worldclim
- https://worldclim.org/about.html (read): free for academic and non-commercial use; "Redistribution or commercial
  use is not allowed without prior permission."

## fabdem
- Search results show FABDEM data at the University of Bristol data repository and derivatives on Zenodo under
  CC BY-NC-SA 4.0; the global record was not read.

## chirps
- https://chc.ucsb.edu/node/534 (read): "CHC's CHIRPS3 dataset now available for all", 2026-06-10; no download
  address or licence on the page.

## alos-world-3d-aw3d30
- https://www.eorc.jaxa.jp/ALOS/en/aw3d30/terms.htm (read): "available to use with no charge"; commercial use,
  registration and redistribution not stated on that page.
