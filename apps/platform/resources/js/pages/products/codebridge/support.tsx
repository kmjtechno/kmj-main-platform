import LegalDocument from '@/components/legal/legal-document';

export default function CodeBridgeSupport() {
    return (
        <LegalDocument
            title="KMJ CodeBridge Support"
            description="Official support, security reporting and troubleshooting guidance for the KMJ CodeBridge ChatGPT plugin and MCP service."
            path="/products/kmj-codebridge/support"
            eyebrow="KMJ CodeBridge support"
            effectiveDate="4 October 2026"
            intro="Use this page for KMJ CodeBridge account, connection, device enrollment, project-scope, quality-gate and security support. Send only the minimum information needed to diagnose the issue."
            sections={[
                {
                    title: 'Support contact',
                    paragraphs: [
                        'For CodeBridge support, contact kmjtechno.net@gmail.com. Include the affected product name, approximate time of the issue, the user-visible error, device ID or project ID when relevant, and the troubleshooting steps already attempted.',
                    ],
                },
                {
                    title: 'What to include',
                    bullets: [
                        'The KMJ CodeBridge version shown by the connected service.',
                        'Whether the issue affects connection, authorization, file access, Git operations, a configured quality gate or a durable job.',
                        'A redacted error message or log excerpt that does not contain authentication secrets or unrelated customer content.',
                        'Whether the problem is reproducible and the minimum safe steps that reproduce it.',
                    ],
                },
                {
                    title: 'Security reports',
                    paragraphs: [
                        'If you believe you found a security vulnerability, stop testing once you have enough evidence to explain the issue and contact KMJ TECHNO. Do not access data belonging to another user, degrade service availability or retain data obtained unintentionally.',
                    ],
                },
                {
                    title: 'Connected platforms',
                    paragraphs: [
                        'Problems with ChatGPT installation, account UI or OpenAI platform behavior may also depend on OpenAI services. Problems with GitHub authorization or GitHub availability may depend on GitHub. KMJ will troubleshoot the CodeBridge portion and identify third-party boundaries when reasonably possible.',
                    ],
                },
                {
                    title: 'Product and legal links',
                    paragraphs: [
                        'Use the KMJ CodeBridge product page for current lifecycle information. The KMJ CodeBridge Terms of Service and Privacy Policy contain the product-specific legal and data-handling rules for the plugin and MCP service.',
                    ],
                },
            ]}
        />
    );
}
