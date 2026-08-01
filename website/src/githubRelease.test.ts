import { describe, expect, it } from "vitest";
import { selectPreferredWindowsAsset } from "./githubRelease";

describe("selectPreferredWindowsAsset", () => {
  it("selects the canonical executable regardless of API ordering", () => {
    const result = selectPreferredWindowsAsset([
      { name: "OTP-LOL-Setup-v2.0.0.exe", browser_download_url: "https://example.test/setup.exe" },
      { name: "OTP LOL.exe", browser_download_url: "https://example.test/canonical.exe" },
    ]);
    expect(result?.browser_download_url).toBe("https://example.test/canonical.exe");
  });

  it("prefers a versioned installer over a portable executable", () => {
    const result = selectPreferredWindowsAsset([
      { name: "OTP-LOL-v2.0.0.exe", browser_download_url: "https://example.test/portable.exe" },
      { name: "OTP-LOL-Setup-v2.0.0.exe", browser_download_url: "https://example.test/setup.exe" },
    ]);
    expect(result?.browser_download_url).toBe("https://example.test/setup.exe");
  });

  it("recognizes the installer naming used by existing releases", () => {
    const result = selectPreferredWindowsAsset([
      { name: "OTP-LOL-v2.0.0.exe", browser_download_url: "https://example.test/portable.exe" },
      { name: "Setup OTP LOL.exe", browser_download_url: "https://example.test/setup.exe" },
    ]);
    expect(result?.browser_download_url).toBe("https://example.test/setup.exe");
  });

  it("does not guess when an executable does not match the product name", () => {
    expect(selectPreferredWindowsAsset([{ name: "unrelated-tool.exe", browser_download_url: "https://example.test/unrelated.exe" }])).toBeUndefined();
  });
});
