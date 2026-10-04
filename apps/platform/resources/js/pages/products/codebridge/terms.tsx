import LegalDocument from '@/components/legal/legal-document';

export default function CodeBridgeTerms() {
    return (
        <LegalDocument
            title="KMJ CodeBridge Terms of Service"
            description="Product-specific terms governing use of the KMJ CodeBridge ChatGPT plugin, MCP service, gateway, agent and authorized project operations."
            path="/products/kmj-codebridge/terms"
            eyebrow="KMJ CodeBridge legal"
            effectiveDate="4 October 2026"
            intro="These product-specific Terms govern your use of KMJ CodeBridge, including its ChatGPT plugin, MCP endpoint, gateway, device agent, project-scoped tools and related account or licensing services. They supplement the KMJ TECHNO Terms & Conditions. If these Terms conflict with the general Terms for a CodeBridge-specific matter, these Terms control for that matter."
            sections={[
                {
                    title: 'Authorized use and project boundaries',
                    bullets: [
                        'Use CodeBridge only with computers, workstations, VPSs, repositories, organizations and projects that you own or are authorized to administer.',
                        'CodeBridge is intentionally project-scoped. Access is limited by the device, project, organization, entitlement and permission boundaries configured for your account.',
                        'Read, write and execute capabilities are separate permissions. Administrator-defined quality gates may permit specific commands without exposing unrestricted arbitrary shell access.',
                        'You must not use CodeBridge to bypass access controls, obtain unauthorized access, deploy malware, exfiltrate secrets or interfere with systems you are not authorized to control.',
                    ],
                },
                {
                    title: 'ChatGPT, MCP and connected services',
                    paragraphs: [
                        'CodeBridge may be invoked through ChatGPT or another compatible MCP client. The client may provide tool inputs and relevant context necessary to perform your request. The client provider’s separate terms, privacy settings and account controls also apply.',
                        'Optional integrations such as GitHub operate only when configured and authorized. Third-party service terms and availability remain separate from these CodeBridge Terms.',
                    ],
                },
                {
                    title: 'Accounts, OAuth and device enrollment',
                    bullets: [
                        'Keep your KMJ account, OAuth session, device enrollment credentials and recovery methods secure.',
                        'Do not share authentication secrets or paste passwords, API keys, MFA codes or private tokens into support requests or ordinary chat prompts.',
                        'You are responsible for approving only devices and projects you recognize and for revoking access that is no longer required.',
                        'KMJ may refuse or revoke a session, device credential or entitlement when reasonably necessary to protect security, comply with law or respond to suspected abuse.',
                    ],
                },
                {
                    title: 'Code changes and execution responsibility',
                    paragraphs: [
                        'CodeBridge can inspect files, create or modify approved project files, review Git state and run configured quality gates when the relevant permission is granted. You remain responsible for deciding what systems and projects may be changed.',
                        'AI-generated or AI-assisted changes can be incomplete or incorrect. Maintain appropriate version control, backups, review practices, testing and deployment safeguards before relying on changes in production.',
                    ],
                },
                {
                    title: 'Quality gates and durable jobs',
                    paragraphs: [
                        'Configured quality gates are administrator-defined commands and are not a guarantee that software is secure, correct or fit for production. A passing gate means only that the configured check completed successfully under the reported conditions.',
                        'Durable or long-running jobs may be monitored through CodeBridge, but external system failures, network interruptions, dependency failures and client disconnects can still affect completion.',
                    ],
                },
                {
                    title: 'Licensing, previews and availability',
                    paragraphs: [
                        'Access may depend on a free, preview, evaluation, subscription or enterprise entitlement issued by KMJ TECHNO. Entitlements may limit devices, organizations, permissions, usage or features.',
                        'Preview and pre-release capabilities may change, be suspended or be withdrawn. Product version numbers identify released software or package versions and do not themselves create a service-level commitment.',
                    ],
                },
                {
                    title: 'Security and responsible disclosure',
                    paragraphs: [
                        'Do not probe, attack or attempt to defeat CodeBridge security controls outside a separately authorized security-testing scope. If you discover a vulnerability, stop exploiting it and report it through the support channel listed on the CodeBridge support page.',
                        'We may temporarily restrict functionality to contain a security incident, protect users or complete emergency maintenance.',
                    ],
                },
                {
                    title: 'Intellectual property and open-source components',
                    paragraphs: [
                        'KMJ TECHNO retains rights in the KMJ CodeBridge name, branding, hosted services and proprietary materials. Source components made available under an open-source license remain governed by the license published with those components.',
                        'These Terms do not grant rights to use KMJ trademarks, logos or branding except as necessary to identify the service you are using.',
                    ],
                },
                {
                    title: 'Warranty and liability',
                    paragraphs: [
                        'To the maximum extent permitted by law, preview, beta, free and evaluation CodeBridge services are provided “as is” and “as available”. No tool result, code change, Git operation or quality-gate result is a warranty that a project is secure, error-free or production-ready.',
                        'The liability limitations in the KMJ TECHNO Terms & Conditions apply to CodeBridge except where a signed agreement or mandatory law provides otherwise.',
                    ],
                },
                {
                    title: 'Suspension and termination',
                    paragraphs: [
                        'You may stop using CodeBridge and revoke connected devices or accounts at any time, subject to any applicable commercial commitment. KMJ may suspend or terminate access for material breach, non-payment, security risk, unlawful use or where continued operation would create material legal or technical risk.',
                    ],
                },
                {
                    title: 'Governing terms and contact',
                    paragraphs: [
                        'The KMJ TECHNO Terms & Conditions, Acceptable Use Policy and KMJ CodeBridge Privacy Policy are incorporated by reference. Unless mandatory law or a signed agreement requires otherwise, the governing-law and dispute provisions in the KMJ TECHNO Terms & Conditions apply.',
                        'Questions about these CodeBridge Terms may be sent to kmjtechno.net@gmail.com. Do not include passwords, API keys, MFA codes or other authentication secrets.',
                    ],
                },
            ]}
        />
    );
}
