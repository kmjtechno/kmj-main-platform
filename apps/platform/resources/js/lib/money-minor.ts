const ZERO_DECIMAL = new Set(['JPY', 'KRW', 'VND']);
const THREE_DECIMAL = new Set(['BHD', 'JOD', 'KWD', 'OMR']);

/** Number of minor-unit digits for a currency (INR/USD/EUR… use 2). */
export function minorDigits(currency: string): number {
    const code = currency.trim().toUpperCase();
    if (ZERO_DECIMAL.has(code)) return 0;
    if (THREE_DECIMAL.has(code)) return 3;

    return 2;
}

/**
 * Convert what a person types ("1499", "1,499.50") into integer minor units
 * using string arithmetic only, so no floating point rounding can change money.
 * Returns null for anything ambiguous, negative, zero or too precise.
 */
export function toMinorUnits(input: string, currency: string): number | null {
    const digits = minorDigits(currency);
    const cleaned = input.trim().replace(/,/g, '');
    const match = /^(\d{1,12})(?:\.(\d+))?$/.exec(cleaned);
    if (!match) return null;
    const fraction = match[2] ?? '';
    if (fraction.length > digits) return null;
    const minor = Number(match[1] + fraction.padEnd(digits, '0'));

    return Number.isSafeInteger(minor) && minor > 0 ? minor : null;
}
