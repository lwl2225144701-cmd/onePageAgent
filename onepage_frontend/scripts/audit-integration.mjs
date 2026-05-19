import { promises as fs } from "node:fs";
import path from "node:path";

const frontendRoot = process.cwd();
const backendRoot = path.resolve(frontendRoot, "../onepage_backend");

const backendApiDir = path.join(backendRoot, "app/api/v1");
const frontendApiDir = path.join(frontendRoot, "src/api");
const frontendUsageDirs = [path.join(frontendRoot, "src/modules"), path.join(frontendRoot, "src/app")];
const reportPath = path.join(frontendRoot, "docs/integration-audit-report.md");

function normalizeRoute(routeFile, method, suffix) {
  const prefixMap = {
    ai_tasks: "/ai/tasks",
    uploads: "/uploads",
    journals: "/journals",
    pages: "/pages",
    materials: "/materials",
    weather: "/weather",
    preferences: "/preferences",
    export: "/export"
  };
  const name = path.basename(routeFile, ".py");
  const prefix = prefixMap[name];
  if (!prefix) return null;
  const joined = `${prefix}${suffix === "" ? "" : suffix}`;
  return `${method.toUpperCase()} ${joined}`;
}

function normalizeFrontendRoute(url) {
  return (
    url
      .replace(/^['"`]|['"`]$/g, "")
      .replace(/\$\{[^}]+\}/g, "{id}")
      .replace(/\{journalId\}/g, "{id}")
      .replace(/\{pageId\}/g, "{id}")
      .replace(/\{taskId\}/g, "{id}")
      .replace(/\/[a-zA-Z_]+Id/g, "/{id}")
      .replace(/\/\{id\}\/events/g, "/{id}/events")
  );
}

async function readFilesRecursive(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const out = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await readFilesRecursive(full)));
    } else {
      out.push(full);
    }
  }
  return out;
}

async function parseBackendRoutes() {
  const files = (await fs.readdir(backendApiDir)).filter((f) => f.endsWith(".py"));
  const routes = [];
  const routeRegex = /@router\.(get|post|put|delete)\("([^"]*)"/g;
  for (const file of files) {
    const fullPath = path.join(backendApiDir, file);
    const content = await fs.readFile(fullPath, "utf8");
    let match;
    while ((match = routeRegex.exec(content)) !== null) {
      const norm = normalizeRoute(fullPath, match[1], match[2]);
      if (norm) routes.push(norm);
    }
  }
  return Array.from(new Set(routes)).sort();
}

async function parseFrontendApiCoverage() {
  const files = (await fs.readdir(frontendApiDir)).filter((f) => f.endsWith(".ts"));
  const callRegex = /apiClient\.(get|post|put|delete)\((`[^`]+`|"[^"]+")/g;
  const eventRegex = /createEventSource\((`[^`]+`|"[^"]+")\)/g;
  const routes = [];
  const funcs = [];
  for (const file of files) {
    const fullPath = path.join(frontendApiDir, file);
    const content = await fs.readFile(fullPath, "utf8");
    const fnRegex = /export function ([a-zA-Z0-9_]+)/g;
    let fnMatch;
    while ((fnMatch = fnRegex.exec(content)) !== null) {
      funcs.push({ fn: fnMatch[1], file: path.relative(frontendRoot, fullPath) });
    }
    let match;
    while ((match = callRegex.exec(content)) !== null) {
      const method = match[1].toUpperCase();
      const route = normalizeFrontendRoute(match[2]);
      routes.push(`${method} ${route}`);
    }
    while ((match = eventRegex.exec(content)) !== null) {
      const route = normalizeFrontendRoute(match[1]);
      routes.push(`GET ${route}`);
    }
  }
  return { routes: Array.from(new Set(routes)).sort(), funcs };
}

async function parseFrontendFunctionUsage(functions) {
  const usageFiles = [];
  for (const dir of frontendUsageDirs) {
    usageFiles.push(...(await readFilesRecursive(dir)));
  }
  const tsxFiles = usageFiles.filter((f) => f.endsWith(".ts") || f.endsWith(".tsx"));
  const usageMap = new Map(functions.map((f) => [f.fn, []]));
  for (const file of tsxFiles) {
    const content = await fs.readFile(file, "utf8");
    for (const fn of usageMap.keys()) {
      const re = new RegExp(`\\b${fn}\\b`, "g");
      if (re.test(content)) {
        usageMap.get(fn).push(path.relative(frontendRoot, file));
      }
    }
  }
  return usageMap;
}

function backendRouteToComparable(route) {
  return route
    .replace(/\/\{[a-zA-Z_]+\}/g, "/{id}")
    .replace(/\/\{id\}\/events/g, "/{id}/events");
}

function frontendRouteToComparable(route) {
  return route
    .replace(/`/g, "")
    .replace(/\/\{id\}/g, "/{id}")
    .replace(/\/\{id\}\/events/g, "/{id}/events");
}

async function main() {
  const backendRoutesRaw = await parseBackendRoutes();
  const backendRoutes = backendRoutesRaw.map(backendRouteToComparable);
  const { routes: frontendRoutesRaw, funcs } = await parseFrontendApiCoverage();
  const frontendRoutes = frontendRoutesRaw.map(frontendRouteToComparable);
  const usageMap = await parseFrontendFunctionUsage(funcs);

  const missingInFrontend = backendRoutes.filter((route) => !frontendRoutes.includes(route));
  const extraFrontend = frontendRoutes.filter((route) => !backendRoutes.includes(route));

  const unusedFunctions = funcs
    .filter((f) => (usageMap.get(f.fn) ?? []).length === 0)
    .map((f) => `${f.fn} (${f.file})`);

  const lines = [];
  lines.push("# Frontend-Backend Integration Audit");
  lines.push("");
  lines.push(`Generated at: ${new Date().toISOString()}`);
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(`- Backend routes: ${backendRoutes.length}`);
  lines.push(`- Frontend API routes: ${frontendRoutes.length}`);
  lines.push(`- Missing frontend route coverage: ${missingInFrontend.length}`);
  lines.push(`- Extra frontend routes (not found in backend): ${extraFrontend.length}`);
  lines.push(`- Potentially unused API functions: ${unusedFunctions.length}`);
  lines.push("");
  lines.push("## Missing Frontend Route Coverage");
  lines.push("");
  if (missingInFrontend.length === 0) {
    lines.push("- None");
  } else {
    for (const item of missingInFrontend) lines.push(`- ${item}`);
  }
  lines.push("");
  lines.push("## Extra Frontend Routes");
  lines.push("");
  if (extraFrontend.length === 0) {
    lines.push("- None");
  } else {
    for (const item of extraFrontend) lines.push(`- ${item}`);
  }
  lines.push("");
  lines.push("## Potentially Unused API Functions");
  lines.push("");
  if (unusedFunctions.length === 0) {
    lines.push("- None");
  } else {
    for (const item of unusedFunctions) lines.push(`- ${item}`);
  }
  lines.push("");
  lines.push("## Route Matrix");
  lines.push("");
  for (const route of backendRoutes) {
    const covered = frontendRoutes.includes(route) ? "yes" : "no";
    lines.push(`- ${route} -> covered: ${covered}`);
  }
  lines.push("");

  await fs.writeFile(reportPath, `${lines.join("\n")}\n`, "utf8");
  console.log(`Integration audit report written to ${reportPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
