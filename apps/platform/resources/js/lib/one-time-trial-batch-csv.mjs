/**
 * Browser-only one-time, trial-only key export. The parent Inertia page has
 * already received these secrets for a single authorized session flash.
 * This helper does no persistence, network calls, telemetry or background work.
 *
 * @typedef {{customer_id: string, product_code: string, license_id: string, key: string}} IssuedTrialKey
 */

/** @param {string} value */
function csvCell(value) {
    const cleaned = Array.from(value, (char) => {
        const code = char.charCodeAt(0);
        return code < 32 || code === 127 ? ' ' : char;
    }).join('');
    const normalized = /^\s*[=+\-@]/u.test(cleaned) ? "'" + cleaned : cleaned;
    return '"' + normalized.replace(/"/g, '""') + '"';
}

/**
 * @param {IssuedTrialKey[]} keys
 * @returns {string}
 */
export function buildOneTimeTrialBatchCsv(keys) {
    if (!Array.isArray(keys) || keys.length < 2 || keys.length > 10) {
        throw new Error('KSLP_ONE_TIME_TRIAL_BATCH_SIZE_REJECTED');
    }

    const customerIds = new Set();
    const licenseIds = new Set();
    const header = [
        'customer_id',
        'product_code',
        'license_id',
        'one_time_trial_bootstrap_key',
    ].join(',');

    const rows = keys.map((issued) => {
        if (
            !issued ||
            typeof issued.customer_id !== 'string' ||
            !/^[A-Za-z0-9._:@-]{3,128}$/.test(issued.customer_id) ||
            typeof issued.product_code !== 'string' ||
            !/^[A-Z0-9][A-Z0-9_.:-]{2,95}$/.test(issued.product_code) ||
            typeof issued.license_id !== 'string' ||
            !/^[0-9a-f-]{36}$/i.test(issued.license_id) ||
            typeof issued.key !== 'string' ||
            !/^KMJ1-[A-Za-z0-9_-]{43}$/.test(issued.key) ||
            customerIds.has(issued.customer_id) ||
            licenseIds.has(issued.license_id)
        ) {
            throw new Error('KSLP_ONE_TIME_TRIAL_BATCH_SHAPE_REJECTED');
        }
        customerIds.add(issued.customer_id);
        licenseIds.add(issued.license_id);

        return [
            issued.customer_id,
            issued.product_code,
            issued.license_id,
            issued.key,
        ]
            .map(csvCell)
            .join(',');
    });

    // No stream to a remote server. Caller may only turn this into a
    // user-confirmed, local browser download while one-time keys are visible.
    return [header, ...rows].join('\r\n') + '\r\n';
}
