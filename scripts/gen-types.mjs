#!/usr/bin/env node
/**
 * Generate TypeScript types from the FastAPI OpenAPI document.
 *
 * The source of truth is api/schemas.py. This script dumps app.openapi() to
 * web/openapi.json and runs openapi-typescript, so the frontend never
 * hand-writes response field names.
 */
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFileSync } from "node:fs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const webDir = resolve(root, "web");
const openapiPath = resolve(webDir, "openapi.json");

const dump = spawnSync(
  "uv",
  [
    "run",
    "python",
    "-c",
    [
      "import json",
      "from api.main import app",
      "print(json.dumps(app.openapi(), indent=2))",
    ].join("; "),
  ],
  { cwd: root, encoding: "utf8" },
);

if (dump.status !== 0) {
  console.error(dump.stderr || dump.stdout);
  process.exit(dump.status || 1);
}

writeFileSync(openapiPath, dump.stdout + "\n", "utf8");
console.log(`Wrote ${openapiPath}`);

const generate = spawnSync(
  "npm",
  [
    "exec",
    "--",
    "openapi-typescript",
    "openapi.json",
    "-o",
    "src/api/schema.gen.ts",
  ],
  { cwd: webDir, stdio: "inherit" },
);

if (generate.status !== 0) {
  process.exit(generate.status || 1);
}
