import assert from "node:assert/strict";
import { access } from "node:fs/promises";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import content from "../src/content.json" with { type: "json" };

const screenshotSources = {
  settings: "../../docs/images/settings-web.png",
  statistics: "../../docs/images/statistics-web.png",
};

test("download actions point to the project release page", () => {
  const releases = new URL(content.releasesUrl);
  assert.equal(releases.hostname, "github.com");
  assert.equal(releases.pathname, "/qurnt1/otp_lol/releases/latest");
});

test("the screenshot selector has distinct, described captures", async () => {
  const ids = content.screenshots.map((shot) => shot.id);
  assert.deepEqual(ids, ["settings", "statistics"]);

  for (const shot of content.screenshots) {
    assert.ok(shot.label.trim());
    assert.ok(shot.title.trim());
    assert.ok(shot.alt.trim());
    assert.ok(shot.note.trim());
    await access(fileURLToPath(new URL(screenshotSources[shot.id], import.meta.url)));
  }
});
