export type OrderProgress = {
    label: string;
    /** 1 = requested, 2 = payment confirmed. Access activation is step 3 and is shown on the dashboard. */
    step: 0 | 1 | 2;
    message: string;
};

/** Plain-language view of a commercial order status (requested | confirmed | cancelled). */
export function orderProgress(status: string): OrderProgress {
    switch (status) {
        case 'requested':
            return {
                label: 'Requested',
                step: 1,
                message:
                    'Request received. The KMJ team confirms your payment before access is activated.',
            };
        case 'confirmed':
            return {
                label: 'Payment confirmed',
                step: 2,
                message:
                    'Payment confirmed. The KMJ team activates your access next; it then appears on your dashboard.',
            };
        case 'cancelled':
            return {
                label: 'Cancelled',
                step: 0,
                message:
                    'This request was cancelled. You can send a new request any time.',
            };
        default:
            return {
                label: status,
                step: 0,
                message: 'Contact support if you need help with this request.',
            };
    }
}
