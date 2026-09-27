import { Head, usePage } from '@inertiajs/react';

type StructuredData = Record<string, unknown> | Array<Record<string, unknown>>;

type PublicSeoProps = {
    title: string;
    description: string;
    path: string;
    type?: 'website' | 'article';
    image?: string;
    imageAlt?: string;
    structuredData?: StructuredData;
};

export default function PublicSeo({
    title,
    description,
    path,
    type = 'website',
    image = '/assets/brand/kmj-social-card.webp',
    imageAlt = 'KMJ TECHNO',
    structuredData,
}: PublicSeoProps) {
    const { publicSite } = usePage().props;
    const origin = publicSite.base_url.replace(/\/$/, '');
    const normalizedPath = path === '/' ? '/' : '/' + path.replace(/^\/+/, '');
    const canonical = origin + normalizedPath;
    const socialImage = image.startsWith('http')
        ? image
        : origin + '/' + image.replace(/^\/+/, '');
    const structuredDataWithUrl = Array.isArray(structuredData)
        ? structuredData.map((item) => ({
              ...item,
              url: item.url ?? canonical,
          }))
        : structuredData
          ? {
                ...structuredData,
                url: structuredData.url ?? canonical,
            }
          : null;

    return (
        <Head title={title}>
            <meta name="description" content={description} />
            <link rel="canonical" href={canonical} />
            <meta property="og:title" content={title} />
            <meta property="og:description" content={description} />
            <meta property="og:type" content={type} />
            <meta property="og:url" content={canonical} />
            <meta property="og:image" content={socialImage} />
            <meta property="og:image:alt" content={imageAlt} />
            <meta name="twitter:card" content="summary_large_image" />
            <meta name="twitter:title" content={title} />
            <meta name="twitter:description" content={description} />
            <meta name="twitter:image" content={socialImage} />
            <meta name="twitter:image:alt" content={imageAlt} />
            {structuredDataWithUrl && (
                <script type="application/ld+json">
                    {JSON.stringify(structuredDataWithUrl)}
                </script>
            )}
        </Head>
    );
}
