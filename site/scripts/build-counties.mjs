// Builds public/places/us-counties.json, the county-to-state list the search page
// uses when a query names a US county (change request CR-1).
// Source: U.S. Census Bureau Gazetteer Files, counties (public domain).
//   https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip
// Usage: unzip that file, then: node scripts/build-counties.mjs path/to/2025_Gaz_counties_national.txt
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const STATES = {
  AL: "Alabama",
  AK: "Alaska",
  AZ: "Arizona",
  AR: "Arkansas",
  CA: "California",
  CO: "Colorado",
  CT: "Connecticut",
  DE: "Delaware",
  DC: "District of Columbia",
  FL: "Florida",
  GA: "Georgia",
  HI: "Hawaii",
  ID: "Idaho",
  IL: "Illinois",
  IN: "Indiana",
  IA: "Iowa",
  KS: "Kansas",
  KY: "Kentucky",
  LA: "Louisiana",
  ME: "Maine",
  MD: "Maryland",
  MA: "Massachusetts",
  MI: "Michigan",
  MN: "Minnesota",
  MS: "Mississippi",
  MO: "Missouri",
  MT: "Montana",
  NE: "Nebraska",
  NV: "Nevada",
  NH: "New Hampshire",
  NJ: "New Jersey",
  NM: "New Mexico",
  NY: "New York",
  NC: "North Carolina",
  ND: "North Dakota",
  OH: "Ohio",
  OK: "Oklahoma",
  OR: "Oregon",
  PA: "Pennsylvania",
  PR: "Puerto Rico",
  RI: "Rhode Island",
  SC: "South Carolina",
  SD: "South Dakota",
  TN: "Tennessee",
  TX: "Texas",
  UT: "Utah",
  VT: "Vermont",
  VA: "Virginia",
  WA: "Washington",
  WV: "West Virginia",
  WI: "Wisconsin",
  WY: "Wyoming",
};

const file = process.argv[2];
if (!file) throw new Error("Usage: node scripts/build-counties.mjs <Gazetteer counties .txt>");
const lines = readFileSync(file, "utf8").trim().split(/\r?\n/);
const header = lines
  .shift()
  .split("|")
  .map((h) => h.trim());
const iState = header.indexOf("USPS");
const iName = header.indexOf("NAME");
const counties = {};
for (const line of lines) {
  const cols = line.split("|");
  const state = STATES[cols[iState]];
  if (!state) throw new Error(`Unknown state code ${cols[iState]}`);
  const name = cols[iName].trim().toLowerCase();
  const list = (counties[name] ??= []);
  if (!list.includes(state)) list.push(state);
}
mkdirSync("public/places", { recursive: true });
writeFileSync(
  "public/places/us-counties.json",
  JSON.stringify({
    source: "U.S. Census Bureau, 2025 Gazetteer Files, counties (public domain)",
    states: Object.values(STATES),
    counties,
  }) + "\n",
);
console.log(`${lines.length} counties, ${Object.keys(counties).length} distinct names`);
