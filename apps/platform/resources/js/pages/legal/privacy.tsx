import LegalDocument from '@/components/legal/legal-document';

export default function Privacy() {
    return (
        <LegalDocument
            title="Privacy Policy"
            description="How KMJ TECHNO collects, uses, protects, shares and retains personal data across its international software and cloud services."
            path="/privacy"
            eyebrow="Privacy & data protection"
            effectiveDate="26 September 2026"
            intro="This Privacy Policy explains how KMJ TECHNO handles personal data when you visit our websites, create an account, use a product, request support, interact with a preview or enter into a commercial relationship with us."
            sections={[
                {
                    title: 'Data we collect',
                    bullets: [
                        'Account and identity data such as name, email address, authentication identifiers and organization membership.',
                        'Commercial data such as product requests, orders, entitlements, licenses, billing status and support history. Payment-card data should be processed by an approved payment provider rather than stored by KMJ where feasible.',
                        'Technical data such as device, browser, IP address, security events, session data, logs, diagnostics and service telemetry.',
                        'Content you choose to provide, including support messages, uploaded files, product configuration, code or other customer content.',
                        'Marketing and communication preferences where you provide them.',
                    ],
                },
                {
                    title: 'Why we process personal data',
                    bullets: [
                        'Provide, authenticate, secure and administer accounts, products, entitlements and licenses.',
                        'Process orders, customer requests, support and contractual obligations.',
                        'Detect abuse, fraud, security incidents and operational failures.',
                        'Maintain, troubleshoot and improve products and service reliability.',
                        'Meet legal, accounting, regulatory and enforcement obligations.',
                        'Send product or marketing communications where permitted and provide opt-out mechanisms where required.',
                    ],
                },
                {
                    title: 'Legal bases and consent',
                    paragraphs: [
                        'Depending on the service and jurisdiction, processing may be based on performance of a contract, steps requested before entering a contract, legitimate interests, compliance with legal obligations, consent, or another lawful basis recognized by applicable law.',
                        'Where we rely on consent, you may withdraw it through the applicable product controls or by contacting us. Withdrawal does not make prior lawful processing unlawful.',
                    ],
                },
                {
                    title: 'Data minimization and retention',
                    paragraphs: [
                        'We aim to collect only data reasonably necessary for stated purposes. Retention periods depend on account status, contractual needs, security requirements, legal obligations, dispute preservation and the type of data involved.',
                        'When data is no longer reasonably required, we will delete, anonymize or securely isolate it in accordance with applicable law and operational backup constraints.',
                    ],
                },
                {
                    title: 'Sharing and processors',
                    paragraphs: [
                        'We may share data with hosting, infrastructure, communications, analytics, support, identity, security, payment or other service providers that process data for legitimate service purposes. We may also disclose data where required by law, to protect rights or security, in connection with a corporate transaction, or with your direction.',
                        'We do not treat customer conversations or private customer content as advertising inventory. We do not sell personal data in the ordinary meaning of selling data for money. If a jurisdiction applies a broader statutory definition of “sale” or “sharing”, we will provide any notice or opt-out required by that law.',
                    ],
                },
                {
                    title: 'International transfers',
                    paragraphs: [
                        'Because KMJ operates internationally and may use global infrastructure, personal data may be processed in countries other than your own. Where required, we use appropriate contractual, technical or organizational safeguards for cross-border transfers.',
                    ],
                },
                {
                    title: 'Security',
                    bullets: [
                        'Authentication, session and organization-scoped authorization controls.',
                        'Least-privilege access and separation between customer, operator and product authority.',
                        'Encryption in transit where supported and appropriate security controls for stored data.',
                        'Logging, monitoring, backup and incident-response measures proportionate to the service.',
                    ],
                },
                {
                    title: 'Your privacy rights',
                    paragraphs: [
                        'Depending on your jurisdiction, you may have rights to be informed, access personal data, correct inaccurate data, request deletion, restrict or object to processing, receive portable data, withdraw consent, opt out of certain sale/sharing or targeted advertising activities, or lodge a complaint with a competent authority.',
                        'Rights may be subject to lawful exceptions. We may verify identity and authority before fulfilling a request.',
                    ],
                },
                {
                    title: 'Children',
                    paragraphs: [
                        'KMJ business and enterprise services are not directed to children. Do not create an account or provide personal data if you are below the minimum age at which you may validly use the service in your jurisdiction without required parental or guardian authorization.',
                    ],
                },
                {
                    title: 'Automated systems and AI',
                    paragraphs: [
                        'KMJ may use automation or AI-assisted systems to support engineering, operations, security, customer service or product functions. We apply access and cost/privacy controls appropriate to the workload. We do not intentionally route confidential customer content to a provider that has not been approved for that data classification.',
                    ],
                },
                {
                    title: 'Cookies and similar technologies',
                    paragraphs: [
                        'We may use strictly necessary technologies for authentication, security, preferences and service operation, and may use optional analytics or similar technologies where permitted. See the Cookie Policy for details and available controls.',
                    ],
                },
                {
                    title: 'Requests and complaints',
                    paragraphs: [
                        'Privacy requests, complaints or questions may be sent to kmjtechno.net@gmail.com. Please include enough information for us to understand and verify the request without sending unnecessary sensitive information.',
                        'Where applicable, you may also contact or complain to your local data-protection authority or other competent regulator.',
                    ],
                },
            ]}
        />
    );
}
