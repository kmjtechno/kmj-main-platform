export type ProductShareOutcome =
    | 'shared'
    | 'copied'
    | 'cancelled'
    | 'unavailable';

export declare function deliverProductLink(options: {
    mode: 'share' | 'copy';
    title: string;
    url: string;
    nativeShare?: (data: {
        title: string;
        text: string;
        url: string;
    }) => Promise<void>;
    copyText?: (text: string) => Promise<void>;
}): Promise<ProductShareOutcome>;
