/** UTC storage -> explicit IST operator display; never depends on browser timezone. */
const indiaDateTime = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
});

export function formatIstDateTime(
    value: string | number | Date | null | undefined,
): string {
    if (value == null || value === '') return 'Time unavailable';

    // A server datetime without a timezone is ambiguous and must not be
    // silently treated as the customer's browser-local clock.
    if (
        typeof value === 'string' &&
        !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value.trim())
    ) {
        return 'Time unavailable';
    }

    const instant = value instanceof Date ? value : new Date(value);
    if (!Number.isFinite(instant.getTime())) return 'Time unavailable';

    return indiaDateTime.format(instant).replace(',', '') + ' IST';
}
