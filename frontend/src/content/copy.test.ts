import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx)$/.test(entry.name) && !entry.name.endsWith("copy.test.ts") ? [path] : [];
  });
}

describe("French UI copy", () => {
  const files = sourceFiles(resolve(process.cwd(), "src"));
  const content = files.map((path) => readFileSync(path, "utf8")).join("\n");

  it("contains no common mojibake sequences", () => {
    expect(content).not.toMatch(/[ÃÂ�]|â€™|â€œ/);
  });

  it("keeps user-facing French words accented", () => {
    expect(content).not.toMatch(/(?<!\p{L})(?:trouvee|detecte|reglages|selection|parametres|desactive|connecte|execute)(?!\p{L})/iu);
  });
});
