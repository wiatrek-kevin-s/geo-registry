// Read Turf.js's TypeScript declarations (dist/esm/index.d.ts of every @turf/* package)
// and print one JSON object per exported function: name, package, overloads with
// their parameters (name, type text, optional) and the fields of `options` objects.
// Uses TypeScript's parser only; nothing from Turf is executed.
//
//   node harvest/turf_declarations.mjs NODE_MODULES
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const root = process.argv[2];
const require = createRequire(path.join(root, "noop.js"));
const ts = require("typescript");

const out = [];
const turfDir = path.join(root, "@turf");
for (const pkg of fs.readdirSync(turfDir).sort()) {
  const file = path.join(turfDir, pkg, "dist", "esm", "index.d.ts");
  if (!fs.existsSync(file)) continue;
  const text = fs.readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const exported = new Set();
  const decls = new Map();
  const isExported = (n) => (ts.getModifiers(n) || []).some((m) => m.kind === ts.SyntaxKind.ExportKeyword);
  for (const st of sf.statements) {
    if (ts.isExportDeclaration(st) && st.exportClause && ts.isNamedExports(st.exportClause)) {
      for (const el of st.exportClause.elements) exported.add((el.propertyName || el.name).text);
    }
    if (ts.isFunctionDeclaration(st) && st.name) {
      const name = st.name.text;
      if (isExported(st)) exported.add(name);
      const params = st.parameters.map((p) => {
        // A destructured parameter ({ a, b }) is Turf's options object.
        const destructured = ts.isObjectBindingPattern(p.name);
        const param = {
          name: destructured ? "options" : p.name.getText(sf),
          type: p.type ? p.type.getText(sf).replace(/\s+/g, " ") : "any",
          optional: Boolean(p.questionToken || p.initializer),
        };
        if (destructured && !(p.type && ts.isTypeLiteralNode(p.type))) {
          param.fields = p.name.elements.map((el) => ({
            name: (el.propertyName || el.name).getText(sf), type: "any", optional: Boolean(el.initializer),
          }));
        } else if (p.type && ts.isTypeLiteralNode(p.type)) {
          param.fields = p.type.members.filter(ts.isPropertySignature).map((m) => ({
            name: m.name.getText(sf),
            type: m.type ? m.type.getText(sf).replace(/\s+/g, " ") : "any",
            optional: Boolean(m.questionToken),
          }));
        }
        return param;
      });
      if (!decls.has(name)) decls.set(name, []);
      decls.get(name).push({ params, returns: st.type ? st.type.getText(sf).replace(/\s+/g, " ") : "any" });
    }
  }
  const version = JSON.parse(fs.readFileSync(path.join(turfDir, pkg, "package.json"), "utf8")).version;
  for (const [name, overloads] of decls) {
    if (exported.has(name)) out.push({ package: `@turf/${pkg}`, version, name, overloads });
  }
}
process.stdout.write(JSON.stringify(out));
