#!/usr/bin/env node
/**
 * Start the FastAPI API and the Vite dev server together.
 *
 * This is intentionally dependency-free: it is the one command a new checkout
 * needs after Python is synced. If web/node_modules is missing it installs the
 * web dependencies once, then starts both processes.
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const webDir = resolve(root, "web");
const apiPort = process.env.OMNIRUN_API_PORT || "8000";
const webPort = process.env.OMNIRUN_WEB_PORT || "5173";

const useColor = process.stdout.isTTY;
const c = (code, text) => (useColor ? `\u001b[${code}m${text}\u001b[0m` : text);
const dim = (text) => c("2", text);
const bold = (text) => c("1", text);
const copper = (text) => c("38;5;179", text);

function fail(message) {
  console.error(`\n${c("31", "OmniRun dev:")} ${message}\n`);
  process.exit(1);
}

if (!existsSync(resolve(webDir, "package.json"))) {
  fail(`web/package.json is missing at ${webDir}.`);
}

if (!existsSync(resolve(webDir, "node_modules"))) {
  console.log(dim("Installing web dependencies (first run only)..."));
  const install = spawnSync("npm", ["install", "--no-audit", "--no-fund"], {
    cwd: webDir,
    stdio: "inherit",
    env: process.env,
  });
  if (install.status !== 0) {
    fail("web dependency install failed. Run `npm install` in web/ and retry.");
  }
}

const uvCheck = spawnSync("uv", ["--version"], { stdio: "ignore" });
if (uvCheck.status !== 0) {
  fail("`uv` was not found. Install it from https://docs.astral.sh/uv/ and retry.");
}

const children = [];
let stopping = false;

function start(label, command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: options.cwd || root,
    stdio: "inherit",
    env: { ...process.env, ...options.env },
  });
  child.on("error", (error) => {
    console.error(`${label} failed to start: ${error.message}`);
    shutdown(1);
  });
  child.on("exit", (code, signal) => {
    if (stopping) return;
    if (code !== 0 && code !== null) {
      console.error(`${label} exited with code ${code}.`);
      shutdown(code || 1);
    } else if (signal) {
      shutdown(0);
    }
  });
  children.push(child);
  return child;
}

function shutdown(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill("SIGTERM");
  }
  setTimeout(() => {
    for (const child of children) {
      if (!child.killed) child.kill("SIGKILL");
    }
    process.exit(code);
  }, 900);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

console.log(`
${bold("OmniRun dev")} ${dim("· API + web")}

  ${copper("Web")}   http://localhost:${webPort}
  ${copper("API")}   http://127.0.0.1:${apiPort}
  ${copper("Docs")}  http://127.0.0.1:${apiPort}/docs

  ${dim("Ctrl+C stops both. The web dev server proxies /api to FastAPI.")}
`);

start(
  "API",
  "uv",
  [
    "run",
    "uvicorn",
    "api.main:app",
    "--reload",
    "--reload-dir",
    "api",
    "--reload-dir",
    "core",
    "--host",
    "127.0.0.1",
    "--port",
    apiPort,
  ],
  { cwd: root },
);

start(
  "web",
  "npm",
  [
    "run",
    "dev",
    "--",
    "--host",
    "127.0.0.1",
    "--port",
    webPort,
    "--strictPort",
  ],
  { cwd: webDir },
);
