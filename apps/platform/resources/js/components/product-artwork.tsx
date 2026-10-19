import { useState } from 'react';

type Props = {
    src?: string | null;
    name: string;
    fallbackClassName: string;
    fallbackText: string;
};

/**
 * Keeps the locked image geometry for valid assets. A failed product image
 * must never leave a broken icon or silently substitute another product's art.
 */
export default function ProductArtwork({
    src,
    name,
    fallbackClassName,
    fallbackText,
}: Props) {
    const source = src?.trim() ?? '';
    const [failedSource, setFailedSource] = useState<string | null>(null);

    if (source && failedSource !== source) {
        return (
            <img
                src={source}
                alt={name + ' product artwork'}
                loading="lazy"
                width="480"
                height="270"
                onError={() => setFailedSource(source)}
            />
        );
    }

    return (
        <span
            className={fallbackClassName}
            role="img"
            aria-label={name + ' artwork not available'}
        >
            {fallbackText}
        </span>
    );
}
