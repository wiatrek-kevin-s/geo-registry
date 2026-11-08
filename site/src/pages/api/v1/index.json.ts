import { json } from "../../../lib/api";
import { indexBytes } from "../../../lib/registry";

export const GET = () => json(indexBytes());
