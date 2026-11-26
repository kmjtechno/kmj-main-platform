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

const indiaDate = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
});

const indiaClock = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
});

/**
 * Lenient instant parser for display-only fields. The platform stores UTC, so a
 * zone-less "YYYY-MM-DD HH:MM[:SS]" string is read as UTC, never browser-local.
 */
function toInstant(
    value: string | number | Date | null | undefined,
): Date | null {
    if (value == null || value === '') return null;
    let input: string | number | Date = value;
    if (
        typeof input === 'string' &&
        /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(
            input.trim(),
        )
    ) {
        input = input.trim().replace(' ', 'T') + 'Z';
    }
    const instant = input instanceof Date ? input : new Date(input);

    return Number.isFinite(instant.getTime()) ? instant : null;
}

/** dd/mm/yyyy in India time. */
export function formatIstDate(
    value: string | number | Date | null | undefined,
    fallback = '\u2014',
): string {
    const instant = toInstant(value);

    return instant ? indiaDate.format(instant) : fallback;
}

/** HH:mm:ss (24h) in India time. */
export function formatIstClock(
    value: string | number | Date | null | undefined,
    fallback = '',
): string {
    const instant = toInstant(value);

    return instant ? indiaClock.format(instant) : fallback;
}

/** dd/mm/yyyy HH:mm:ss IST for display-only timestamps. */
export function formatIstStamp(
    value: string | number | Date | null | undefined,
    fallback = '\u2014',
): string {
    const instant = toInstant(value);

    return instant
        ? `${indiaDate.format(instant)} ${indiaClock.format(instant)} IST`
        : fallback;
}
