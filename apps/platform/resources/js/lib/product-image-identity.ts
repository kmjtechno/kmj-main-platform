/**
 * Reject a database-configured image whose product identity is ambiguous.
 * Static KMJ-owned locked artwork is selected separately by its explicit
 * slug mapping; arbitrary public images never inherit another product's art.
 *
 * Owner uploads should use /assets/products/<canonical-slug>[-variant].webp.
 */
const legacyAliases: Record<string, readonly string[]> = {
    'kmj-calibration-pro': ['/assets/products/kmj-calibration.webp'],
};

export function productImageForSlug(
    slug: string,
    configuredImage: string | null | undefined,
): string | null {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
        return null;
    }
    const image = configuredImage?.trim();
    if (!image || !/^\/assets\/products\/[a-z0-9-]+\.webp$/.test(image)) {
        return null;
    }
    if (legacyAliases[slug]?.includes(image)) {
        return image;
    }
    const stem = image.slice('/assets/products/'.length, -'.webp'.length);
    return stem === slug || stem.startsWith(slug + '-') ? image : null;
}
