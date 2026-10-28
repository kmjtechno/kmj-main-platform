// A rejected share permission or clipboard write is not a successful share.
export async function deliverProductLink({
    mode,
    title,
    url,
    nativeShare,
    copyText,
}) {
    if (mode === 'share' && typeof nativeShare === 'function') {
        try {
            await nativeShare({ title, text: title, url });
            return 'shared';
        } catch (error) {
            // Cancellation must never trigger an unwanted clipboard write.
            if (error?.name === 'AbortError') return 'cancelled';
        }
    }

    if (typeof copyText !== 'function') return 'unavailable';
    try {
        await copyText(url);
        return 'copied';
    } catch {
        return 'unavailable';
    }
}
