export const REPOSITORY = "qurnt1/otp_lol";
export const REPOSITORY_URL = `https://github.com/${REPOSITORY}`;
export const RELEASES_URL = `${REPOSITORY_URL}/releases`;
export const LATEST_RELEASE_URL = `${RELEASES_URL}/latest`;
export const LATEST_RELEASE_API = `https://api.github.com/repos/${REPOSITORY}/releases/latest`;

export type GitHubReleaseAsset = { name?: string; browser_download_url?: string };

const canonicalExecutable = /^otp lol\.exe$/i;
const namedInstaller = /^(?:(?:setup|installer)[ _-]+otp[ _-]+lol|otp[ _-]+lol[ _-]+(?:setup|installer))(?:[ _-]+v?\d+(?:\.\d+){1,3})?\.exe$/i;
const namedPortable = /^otp[ _-]+lol(?:[ _-]+(?:portable|v?\d+(?:\.\d+){1,3}))?\.exe$/i;

function priorityFor(name: string) {
  if (canonicalExecutable.test(name)) return 0;
  if (namedInstaller.test(name)) return 1;
  if (namedPortable.test(name)) return 2;
  return Number.POSITIVE_INFINITY;
}

export function selectPreferredWindowsAsset(assets: GitHubReleaseAsset[]) {
  return assets
    .filter((asset): asset is Required<GitHubReleaseAsset> => Boolean(asset.name && asset.browser_download_url))
    .map((asset) => ({ asset, priority: priorityFor(asset.name) }))
    .filter(({ priority }) => Number.isFinite(priority))
    .sort((left, right) => {
      if (left.priority !== right.priority) return left.priority - right.priority;
      return left.asset.name.toLowerCase().localeCompare(right.asset.name.toLowerCase());
    })[0]?.asset;
}
