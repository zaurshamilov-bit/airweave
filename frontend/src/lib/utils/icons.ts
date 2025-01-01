export function getAppIconUrl(shortName: string): string {
  try {
    return new URL(`/src/components/icons/apps/${shortName}.svg`, import.meta.url).href;
  } catch {
    return new URL(`/src/components/icons/apps/default-icon.svg`, import.meta.url).href;
  }
}

export function getDestinationIconUrl(shortName: string): string {
  return new URL(`/src/components/icons/destinations/${shortName}.png`, import.meta.url).href;
}
