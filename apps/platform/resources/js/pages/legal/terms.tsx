import LegalDocument from '@/components/legal/legal-document';

export default function Terms() {
    return (
        <LegalDocument
            title="Terms & Conditions"
            description="Terms governing access to KMJ TECHNO websites, accounts, software, cloud services, previews, licenses and digital products."
            path="/terms"
            eyebrow="Commercial terms"
            effectiveDate="26 September 2026"
            intro="These Terms govern your use of KMJ TECHNO websites, accounts, software, cloud services, previews, licenses, downloads and related digital products. By creating an account, placing an order, activating a license or using a KMJ service, you agree to these Terms and any product-specific order terms presented to you."
            sections={[
                {
                    title: 'Who these Terms apply to',
                    paragraphs: [
                        'These Terms apply to individuals and organizations using KMJ TECHNO services. If you use a service for an organization, you confirm that you are authorized to bind that organization. “KMJ”, “we”, “us” and “our” refer to KMJ TECHNO.',
                    ],
                },
                {
                    title: 'Accounts and authority',
                    bullets: [
                        'You must provide accurate account information and keep credentials, passkeys and recovery methods secure.',
                        'You are responsible for activity performed through your account unless applicable law provides otherwise.',
                        'Organization-scoped access, entitlement and licensing rights are controlled by the authoritative KMJ platform and may require additional verification.',
                        'We may suspend or restrict access when reasonably necessary to protect security, prevent abuse, comply with law or investigate suspected unauthorized activity.',
                    ],
                },
                {
                    title: 'Products, previews and roadmap items',
                    paragraphs: [
                        'Product lifecycle labels matter. A roadmap, development, preview, beta or demonstration item is not a promise of production availability, release date, feature set, performance level or commercial availability.',
                        'Only capabilities expressly identified as available and backed by the applicable product entitlement or license are delivered as current service commitments.',
                    ],
                },
                {
                    title: 'Orders, pricing and taxes',
                    bullets: [
                        'A purchase request does not by itself create product access. Access may require order confirmation, entitlement issuance and license activation.',
                        'Prices, currency, billing period, included usage and taxes are shown in the applicable order flow or written quote.',
                        'You are responsible for applicable taxes, duties and governmental charges unless we state that they are included.',
                        'We may correct obvious pricing or catalog errors before fulfillment and will not knowingly charge a corrected higher amount without obtaining required consent.',
                    ],
                },
                {
                    title: 'Licenses and acceptable use',
                    paragraphs: [
                        'Unless a separate written license says otherwise, KMJ software is licensed, not sold. You receive only the rights expressly granted for the applicable product, organization, users, devices, environments and term.',
                    ],
                    bullets: [
                        'Do not bypass license controls, access restrictions, rate limits, safety controls or technical protection measures.',
                        'Do not reverse engineer, decompile or attempt to derive source code except to the limited extent such restriction is prohibited by applicable law.',
                        'Do not resell, sublicense, rent or provide hosted access to a KMJ product unless your order or written agreement expressly permits it.',
                        'Additional prohibited conduct appears in the Acceptable Use Policy and forms part of these Terms.',
                    ],
                },
                {
                    title: 'Customer content and data',
                    paragraphs: [
                        'You retain rights in content and data you lawfully provide to the service. You grant KMJ the limited rights reasonably necessary to host, transmit, process, back up and secure that content for providing and improving the contracted service, subject to our Privacy Policy and any applicable data-processing terms.',
                        'You must have the rights and lawful basis required to provide personal data, confidential information, code, media or other content to the service.',
                    ],
                },
                {
                    title: 'Intellectual property',
                    paragraphs: [
                        'KMJ TECHNO, its logos, product names, software, interfaces, documentation, designs and other proprietary materials are protected by intellectual-property laws. Except for rights expressly granted to you, KMJ and its licensors reserve all rights.',
                        'Feedback may be used by KMJ without obligation to you, provided we do not identify you publicly without permission.',
                    ],
                },
                {
                    title: 'Availability, changes and maintenance',
                    paragraphs: [
                        'We may update, secure, maintain or improve services and may modify features where reasonably necessary. For paid production services, we will use commercially reasonable efforts to avoid material adverse changes without notice where practicable.',
                        'Preview, beta, free and evaluation services may change or end with less notice and may have lower support or availability commitments.',
                    ],
                },
                {
                    title: 'Third-party services',
                    paragraphs: [
                        'Some products may interoperate with third-party infrastructure, models, payment providers, identity systems or other services. Their separate terms and privacy practices may apply. KMJ is not responsible for third-party services outside our reasonable control, but we remain responsible for obligations that applicable law places directly on us.',
                    ],
                },
                {
                    title: 'Warranty and service limitations',
                    paragraphs: [
                        'To the maximum extent permitted by law, free, preview, beta and evaluation services are provided “as is” and “as available”. For paid services, any express warranty or service level stated in the applicable order, product terms or written agreement controls.',
                        'We do not promise that every service will be uninterrupted, error-free or suitable for every use case. Nothing in these Terms excludes warranties, guarantees or remedies that cannot legally be excluded.',
                    ],
                },
                {
                    title: 'Limitation of liability',
                    paragraphs: [
                        'To the maximum extent permitted by law, neither party will be liable for indirect, incidental, special, punitive or consequential loss, or lost profits, revenue, business or data, except where such exclusion is prohibited by law.',
                        'Unless a separate signed agreement states otherwise, KMJ’s aggregate contractual liability for a paid service will not exceed the fees paid or payable for that service during the twelve months preceding the event giving rise to the claim. This cap does not apply where liability cannot legally be limited, including applicable liability for fraud, willful misconduct or other non-excludable obligations.',
                    ],
                },
                {
                    title: 'Suspension and termination',
                    paragraphs: [
                        'You may stop using the service at any time, subject to applicable order commitments. KMJ may suspend or terminate access for material breach, non-payment, security risk, unlawful use, sanctions/export restrictions or where continuing the service would create material legal or technical risk.',
                        'Where reasonably possible and legally permitted, we will provide notice and an opportunity to cure before terminating a paid service for breach.',
                    ],
                },
                {
                    title: 'Governing law and disputes',
                    paragraphs: [
                        'Unless mandatory law or a signed enterprise agreement requires otherwise, these Terms are governed by the laws of India, without regard to conflict-of-laws rules. Courts with competent jurisdiction in Madhya Pradesh, India will have jurisdiction, subject always to any non-waivable consumer forum, privacy authority or other mandatory venue rights available to you.',
                        'Before formal proceedings, the parties should first attempt in good faith to resolve the dispute through written notice and reasonable discussion.',
                    ],
                },
                {
                    title: 'Changes and contact',
                    paragraphs: [
                        'We may update these Terms to reflect legal, security, product or business changes. Material changes will be communicated where required by law, and the effective date will be updated.',
                        'Questions about these Terms or a commercial order may be sent to kmjtechno.net@gmail.com.',
                    ],
                },
            ]}
        />
    );
}
