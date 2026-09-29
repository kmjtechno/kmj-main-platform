import LegalDocument from '@/components/legal/legal-document';

export default function RefundPolicy() {
    return (
        <LegalDocument
            title="Refund & Cancellation Policy"
            description="KMJ TECHNO refund, cancellation and digital-product remedy policy for software, subscriptions, licenses and services."
            path="/refund-policy"
            eyebrow="Orders & remedies"
            effectiveDate="26 September 2026"
            intro="This policy explains when refunds, credits, cancellations or re-performance may be available for KMJ software, subscriptions, licenses and digital services. Product-specific order terms or mandatory local consumer law may provide additional rights."
            sections={[
                {
                    title: 'Before payment or fulfillment',
                    paragraphs: [
                        'A product request, quote request, waiting-list registration or unconfirmed order does not by itself create a charge or entitlement. Where checkout is enabled, the final price, currency, billing period and relevant product terms should be displayed before payment.',
                    ],
                },
                {
                    title: 'When a refund or corrective remedy may be available',
                    bullets: [
                        'A duplicate charge for the same order.',
                        'An unauthorized charge where responsibility is established through the applicable payment and security process.',
                        'A payment was captured but KMJ cannot provide the purchased entitlement or service within the promised or legally required period.',
                        'A materially defective digital product or service where applicable law requires refund, repair, replacement, re-performance or another remedy.',
                        'KMJ cancels a prepaid service without cause before delivering the corresponding prepaid period, in which case an appropriate unused portion may be refunded unless a more favorable mandatory remedy applies.',
                    ],
                },
                {
                    title: 'Digital access and activated licenses',
                    paragraphs: [
                        'Because software, cloud access, license keys, activated entitlements, downloads and digital services can be delivered immediately and cannot always be meaningfully “returned”, a change of mind does not automatically create a refund right after delivery or activation.',
                        'This rule does not remove any cooling-off, conformity, defect or other refund right that applicable consumer law makes mandatory. Where your law requires express consent before immediate digital delivery affects a cancellation right, KMJ will obtain the required consent in the applicable checkout flow before relying on that exception.',
                    ],
                },
                {
                    title: 'Subscriptions',
                    paragraphs: [
                        'Unless an order states otherwise, cancelling a subscription stops future renewal and does not automatically refund a current period that has already begun. Access may continue until the end of that paid period.',
                        'If a local law requires a different cancellation or renewal process, that law controls. Enterprise commitments, minimum terms or custom contracts may have separate cancellation provisions.',
                    ],
                },
                {
                    title: 'Services and custom work',
                    paragraphs: [
                        'Professional services, implementation, calibration, configuration, integration or custom engineering may be non-refundable to the extent work has already been performed or committed, subject to the applicable statement of work and mandatory law.',
                        'If KMJ materially fails to perform an agreed service, the primary remedy may be correction or re-performance before refund where lawful and commercially reasonable.',
                    ],
                },
                {
                    title: 'Refund request process',
                    bullets: [
                        'Contact kmjtechno.net@gmail.com with the account email, order or invoice reference, product name, date and reason for the request.',
                        'Do not send full card numbers, passwords or unnecessary sensitive information.',
                        'We may request reasonable evidence to investigate duplicate, unauthorized, failed-delivery or defect claims.',
                        'Approved refunds are generally returned to the original payment method where technically and legally possible. Processing time may depend on the payment provider and financial institution.',
                    ],
                },
                {
                    title: 'Chargebacks and disputes',
                    paragraphs: [
                        'Contacting KMJ first often allows us to resolve a billing or delivery issue more quickly. Nothing in this policy prevents you from exercising a valid statutory chargeback, card-network, consumer-protection or dispute right.',
                        'Fraudulent or abusive chargeback activity may result in suspension of related accounts or licenses where permitted by law.',
                    ],
                },
                {
                    title: 'Promotions, credits and free services',
                    paragraphs: [
                        'Promotional credits, free-tier usage, complimentary access and non-cash benefits have no cash redemption value unless required by law or expressly stated otherwise.',
                    ],
                },
            ]}
        />
    );
}
