import LegalDocument from '@/components/legal/legal-document';

export default function CodeBridgePrivacy() {
    return (
        <LegalDocument
            title="KMJ CodeBridge Privacy Policy"
            description="How KMJ CodeBridge handles account, device, project, tool-input, diagnostic and security data when connecting ChatGPT to authorized development environments."
            path="/products/kmj-codebridge/privacy"
            eyebrow="KMJ CodeBridge privacy"
            effectiveDate="4 October 2026"
            intro="This product-specific Privacy Policy explains how KMJ CodeBridge handles personal data and project-related information when you connect ChatGPT or another compatible MCP client to authorized computers, workstations and VPSs. It supplements the KMJ TECHNO Privacy Policy."
            sections={[
                {
                    title: 'Data CodeBridge may process',
                    bullets: [
                        'Account and identity data such as account identifiers, email address, organization membership, OAuth subject identifiers and entitlement status.',
                        'Device and project metadata such as authorized device ID, project ID, project scope, writable state, configured quality gates and connection status.',
                        'Tool inputs and outputs required for the request, which can include selected source-code content, file paths, Git status or history, diffs, directory listings, quality-gate output and job status.',
                        'Security and operational data such as authentication events, revocation state, rate-limit state, service errors and limited diagnostics required to secure and operate the service.',
                        'Support communications you choose to send to KMJ TECHNO.',
                    ],
                },
                {
                    title: 'What ChatGPT may send to CodeBridge',
                    paragraphs: [
                        'When you use the CodeBridge plugin, ChatGPT may send the tool arguments and context required to fulfill your request according to your ChatGPT settings and permissions. CodeBridge does not require your entire chat history merely to execute a tool call.',
                        'ChatGPT Memory and other ChatGPT-side features are controlled by OpenAI and your ChatGPT settings. Their handling is separate from CodeBridge’s own gateway and device processing.',
                    ],
                },
                {
                    title: 'Authentication and authorization data',
                    paragraphs: [
                        'OAuth tokens and device credentials are used to authenticate requests and enforce account, organization, device and project scope. CodeBridge is designed so ordinary tool results do not expose those credentials to chat.',
                        'Do not submit authentication secrets through ordinary CodeBridge tool inputs or support messages.',
                    ],
                },
                {
                    title: 'How we use data',
                    bullets: [
                        'Authenticate users and devices and enforce organization, project and permission boundaries.',
                        'Execute the tool action you requested and return the relevant result.',
                        'Issue and verify entitlements, device enrollments, revocations and licensing state.',
                        'Detect abuse, investigate security incidents, rate-limit harmful traffic and maintain service reliability.',
                        'Provide support, diagnose failures and comply with legal obligations.',
                    ],
                },
                {
                    title: 'Storage and retention',
                    paragraphs: [
                        'The CodeBridge gateway is designed to treat ordinary tool request payloads and results as transient processing data rather than a general conversation archive. Pending gateway requests are held only while the request is active or waiting for its configured timeout.',
                        'Project files remain on the authorized customer-controlled computer or VPS unless a requested tool operation explicitly changes them. Local agent state remains on that device until the operator removes it or the applicable retention mechanism expires.',
                        'Active account, organization, entitlement and device-enrollment records are retained while required to provide the service. Revoked device-credential metadata and security or audit records may be retained for up to 90 days after revocation or closure, unless a longer period is reasonably required for an active security investigation, dispute or legal obligation.',
                        'Support records may be retained for up to 24 months after the support matter closes. Backup copies may persist for up to 90 additional days before normal rotation removes them, unless legal preservation is required.',
                    ],
                },
                {
                    title: 'Sharing and service providers',
                    paragraphs: [
                        'CodeBridge may use hosting, infrastructure, security, identity and communications providers as processors where necessary to operate the service.',
                        'When you invoke CodeBridge from ChatGPT, OpenAI processes information under its own terms and privacy policy. When you explicitly use an authorized GitHub-backed CodeBridge capability, relevant repository information may be exchanged with GitHub under your configured authorization and GitHub’s terms.',
                        'We do not sell CodeBridge project content or private tool inputs as advertising inventory.',
                    ],
                },
                {
                    title: 'International processing',
                    paragraphs: [
                        'Service infrastructure or processors may operate in more than one country. Where applicable law requires safeguards for international transfers, KMJ will use appropriate contractual, technical or organizational measures.',
                    ],
                },
                {
                    title: 'Security controls',
                    bullets: [
                        'OAuth and device authentication with scoped authorization.',
                        'Explicit device, project and permission boundaries.',
                        'Guarded write operations and administrator-defined execution gates rather than unrestricted remote shell exposure.',
                        'Transport security, rate limiting, security logging and revocation controls appropriate to the service.',
                        'Separation between customer project execution and the KMJ commercial and account control plane.',
                    ],
                },
                {
                    title: 'Your choices and rights',
                    paragraphs: [
                        'You can disconnect the ChatGPT app, revoke an authorized device, stop the local agent or stop using CodeBridge. Depending on your jurisdiction, you may also have rights to access, correct, delete, restrict, object to or receive a copy of personal data.',
                        'Some security, transaction or legal records may need to be retained despite a deletion request where applicable law permits or requires retention.',
                    ],
                },
                {
                    title: 'Contact and complaints',
                    paragraphs: [
                        'Privacy requests or questions about CodeBridge may be sent to kmjtechno.net@gmail.com. Provide only the information necessary to identify the relevant account or issue.',
                        'You may also contact an applicable data-protection authority or regulator where local law gives you that right.',
                    ],
                },
            ]}
        />
    );
}
