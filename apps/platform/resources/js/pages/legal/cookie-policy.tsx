import LegalDocument from '@/components/legal/legal-document';

export default function CookiePolicy() {
    return (
        <LegalDocument
            title="Cookie Policy"
            description="How KMJ TECHNO uses cookies, local storage and similar technologies for security, authentication, preferences and analytics."
            path="/cookie-policy"
            eyebrow="Cookies & device storage"
            effectiveDate="26 September 2026"
            intro="This policy explains how KMJ TECHNO may use cookies, local storage and similar technologies. The technologies actually used can vary by product and deployment."
            sections={[
                {
                    title: 'Strictly necessary technologies',
                    paragraphs: [
                        'We may use essential cookies or local storage for authentication, session continuity, security, CSRF protection, fraud prevention, account preferences and other functions required to operate the service. These technologies generally cannot be disabled through a consent tool without breaking the requested service.',
                    ],
                },
                {
                    title: 'Functional technologies',
                    paragraphs: [
                        'Where used, functional technologies remember settings such as language, interface preferences or product state. They may be optional depending on the service.',
                    ],
                },
                {
                    title: 'Analytics and performance',
                    paragraphs: [
                        'KMJ may use privacy-conscious analytics or performance measurement to understand reliability, navigation and product usage. Where applicable law requires consent before non-essential analytics is stored or read on your device, we will request that consent before enabling it.',
                    ],
                },
                {
                    title: 'Advertising technologies',
                    paragraphs: [
                        'KMJ does not need cross-site behavioral advertising technology to operate its core enterprise products. If this changes, the relevant service will disclose the purpose and provide any legally required consent or opt-out controls before such technology is used.',
                    ],
                },
                {
                    title: 'Third-party technologies',
                    paragraphs: [
                        'Embedded or integrated third-party services may set their own technologies when you use them. Their privacy notices may apply. KMJ seeks to limit third-party device storage to what is appropriate for the service.',
                    ],
                },
                {
                    title: 'Your controls',
                    bullets: [
                        'Use any cookie or privacy controls presented by the applicable KMJ service.',
                        'Browser settings can remove or block many cookies, but blocking strictly necessary technologies may prevent login or other requested functionality.',
                        'Where legally recognized and technically applicable, KMJ will respect required opt-out signals or consent choices.',
                    ],
                },
                {
                    title: 'Contact',
                    paragraphs: [
                        'Questions about cookies or tracking technologies may be sent to kmjtechno.net@gmail.com.',
                    ],
                },
            ]}
        />
    );
}
