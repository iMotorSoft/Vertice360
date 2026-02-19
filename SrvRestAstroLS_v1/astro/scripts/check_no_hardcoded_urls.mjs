import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const PROJECT_ROOT = process.cwd();
const SRC_ROOT = path.join(PROJECT_ROOT, "src");
const ALLOWED_FILE = path.normalize(path.join("src", "components", "global.js"));

const URL_PATTERNS = [
  /localhost:7062/g,
  /http:\/\/localhost/g,
  /https?:\/\/[^\s'"`]+/g,
];

const shouldIgnoreDir = (name) =>
  name === ".astro" || name === "node_modules" || name === "dist";

const collectFiles = async (dir) => {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (shouldIgnoreDir(entry.name)) continue;
      files.push(...(await collectFiles(fullPath)));
      continue;
    }
    if (!entry.isFile()) continue;
    files.push(fullPath);
  }
  return files;
};

const findViolations = (relPath, source) => {
  const violations = [];
  const lines = source.split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    for (const pattern of URL_PATTERNS) {
      pattern.lastIndex = 0;
      const matches = line.matchAll(pattern);
      for (const match of matches) {
        violations.push({
          file: relPath,
          line: i + 1,
          value: match[0],
        });
      }
    }
  }
  return violations;
};

const main = async () => {
  const files = await collectFiles(SRC_ROOT);
  const offenders = [];

  for (const filePath of files) {
    const relPath = path.normalize(path.relative(PROJECT_ROOT, filePath));
    if (relPath === ALLOWED_FILE) {
      continue;
    }
    const source = await readFile(filePath, "utf8");
    offenders.push(...findViolations(relPath, source));
  }

  if (offenders.length > 0) {
    console.error("Hardcoded URL(s) detected outside src/components/global.js:");
    for (const offender of offenders) {
      console.error(`- ${offender.file}:${offender.line} -> ${offender.value}`);
    }
    process.exit(1);
  }

  console.log("OK: no hardcoded URLs found outside src/components/global.js");
};

main().catch((error) => {
  console.error("Failed to run hardcoded URL check:", error);
  process.exit(1);
});
