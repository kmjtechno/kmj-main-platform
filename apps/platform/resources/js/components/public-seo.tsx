import { Head, usePage } from '@inertiajs/react';

type StructuredData = Record<string, unknown> | Array<Record<string, unknown>>;

type PublicSeoProps = {
    title: string;
    description: string;
    path: string;
    type?: 'website' | 'article';
    structuredData?: StructuredData;
};

export default function PublicSeo({
    title,
    description,
    path,
    type = 'website',
    structuredData,
}: PublicSeoProps) {
    const { publicSite } = usePage().props;
    const origin = publicSite.base_url.replace(/\/$/, '');
    const normalizedPath = path === '/' ? '/' : '/' + path.replace(/^\/+/, '');
    const canonical = origin + normalizedPath;

    return (
        <Head title={title}>
            <meta name="description" content={description} />
            <link rel="canonical" href={canonical} />
            <meta property="og:title" content={title} />
            <meta property="og:description" content={description} />
            <meta property="og:type" content={type} />
            <meta property="og:url" content={canonical} />
            <meta name="twitter:card" content="summary" />
            <meta name="twitter:title" content={title} />
            <meta name="twitter:description" content={description} />
            {structuredData && (
                <script type="application/ld+json">
                    {JSON.stringify(structuredData)}
                </script>
            )}
        </Head>
    );
}
