// CR-1: the county lookup adds a state-level query only when it is unambiguous.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expandCounty, type Gazetteer } from "../../src/scripts/places.ts";

const gaz: Gazetteer = JSON.parse(
  readFileSync(resolve(import.meta.dirname, "../../public/places/us-counties.json"), "utf8"),
);

test("a county query also searches its state", () => {
  assert.deepEqual(expandCounty("lidar Travis County", gaz), ["lidar Texas"]);
  assert.deepEqual(expandCounty("parcels for orleans parish", gaz), ["parcels for Louisiana"]);
});

test("no expansion when the state is already named, the name is ambiguous, or no county", () => {
  assert.deepEqual(expandCounty("lidar Travis County Texas", gaz), []);
  assert.deepEqual(expandCounty("roads Washington County", gaz), []); // 30 states
  assert.deepEqual(expandCounty("county boundaries", gaz), []);
  assert.deepEqual(expandCounty("buffer PostGIS", gaz), []);
});
