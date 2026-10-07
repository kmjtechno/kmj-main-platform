import { Head, usePage } from '@inertiajs/react';

type StructuredData = Record<string, unknown> | Array<Record<string, unknown>>;

type PublicSeoProps = {
    title: string;
    description: string;
    path: string;
    type?: 'website' | 'article';
    image?: string;
    structuredData?: StructuredData;
    localized?: boolean;
};

export default function PublicSeo({
    title,
    description,
    path,
    type = 'website',
    image = '/assets/brand/kmj-social-card.webp',
    structuredData,
    localized = false,
}: PublicSeoProps) {
    const { publicSite } = usePage().props;
    const origin = publicSite.base_url.replace(/\/$/, '');
    const normalizedPath = path === '/' ? '/' : '/' + path.replace(/^\/+/, '');
    const canonical = origin + normalizedPath;
    const socialImage = image.startsWith('http') ? image : origin + image;
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
            <meta
                name="robots"
                content={
                    publicSite.indexable ? 'index,follow' : 'noindex,nofollow'
                }
            />
            <link rel="canonical" href={canonical} />
            {localized && (
                <>
                    <link
                        rel="alternate"
                        hrefLang="en"
                        href={canonical + '?lang=en'}
                    />
                    <link
                        rel="alternate"
                        hrefLang="hi"
                        href={canonical + '?lang=hi'}
                    />
                    <link
                        rel="alternate"
                        hrefLang="x-default"
                        href={canonical}
                    />
                </>
            )}
            <link
                rel="alternate"
                type="text/plain"
                href={origin + '/llms.txt'}
                title="KMJ TECHNO AI-readable product authority"
            />
            <meta property="og:title" content={title} />
            <meta property="og:description" content={description} />
            <meta property="og:type" content={type} />
            <meta property="og:url" content={canonical} />
            <meta property="og:image" content={socialImage} />
            <meta
                property="og:image:alt"
                content="KMJ TECHNO — INNOVATE | BUILD | SCALE"
            />
            <meta name="twitter:card" content="summary_large_image" />
            <meta name="twitter:title" content={title} />
            <meta name="twitter:description" content={description} />
            <meta name="twitter:image" content={socialImage} />
            {structuredDataWithUrl && (
                <script type="application/ld+json">
                    {JSON.stringify(structuredDataWithUrl)}
                </script>
            )}
        </Head>
    );
}
