import LegalDocument from '@/components/legal/legal-document';

export default function AcceptableUse() {
    return (
        <LegalDocument
            title="Acceptable Use Policy"
            description="Rules for lawful, secure and responsible use of KMJ TECHNO software, cloud systems, automation and digital services."
            path="/acceptable-use"
            eyebrow="Security & responsible use"
            effectiveDate="26 September 2026"
            intro="This policy protects KMJ customers, systems and third parties from abusive, unlawful or unsafe use. It applies to accounts, software, APIs, cloud systems, automation, agents, previews and related services."
            sections={[
                {
                    title: 'Illegal or harmful activity',
                    bullets: [
                        'Do not use KMJ services to violate law, sanctions, export restrictions, court orders or third-party rights.',
                        'Do not use the service to facilitate fraud, phishing, credential theft, malware distribution, unauthorized access or destructive cyber activity.',
                        'Do not knowingly upload, process or distribute content that is unlawful to possess or distribute in the applicable jurisdiction.',
                    ],
                },
                {
                    title: 'Security abuse',
                    bullets: [
                        'Do not probe, scan, exploit or bypass security controls except under an expressly authorized security-testing program.',
                        'Do not evade rate limits, tenant boundaries, license enforcement, authentication or access controls.',
                        'Do not interfere with service availability, infrastructure, monitoring, logs or abuse-prevention systems.',
                        'Report suspected vulnerabilities responsibly instead of exploiting them.',
                    ],
                },
                {
                    title: 'Automation and agents',
                    paragraphs: [
                        'Automated systems must remain within the authority, scope and data classification granted to them. You are responsible for configuring automation so it does not exceed your permissions or violate applicable law.',
                    ],
                    bullets: [
                        'Do not use agents to make unauthorized purchases, access unrelated customer data or alter production systems without required approval.',
                        'Do not intentionally route confidential or regulated data through providers not approved for that data class.',
                        'Do not use automation to generate deceptive traffic, spam, fake engagement or abusive resource consumption.',
                    ],
                },
                {
                    title: 'Content and intellectual property',
                    paragraphs: [
                        'You must have the rights needed to upload, process, transform or distribute content through KMJ services. Do not use KMJ systems to infringe copyright, trademark, privacy, publicity, confidentiality or other rights.',
                    ],
                },
                {
                    title: 'Resource fairness',
                    paragraphs: [
                        'Free or shared resources may have quotas, concurrency controls and fair-use limits. We may throttle or restrict workloads that materially degrade service for others, create unusual cost, or indicate automated abuse.',
                    ],
                },
                {
                    title: 'Enforcement',
                    paragraphs: [
                        'Depending on severity, KMJ may warn, throttle, isolate, suspend or terminate access, preserve relevant evidence, and cooperate with lawful investigations. We will use proportionate measures and provide notice where reasonably possible and legally permitted.',
                    ],
                },
                {
                    title: 'Security reports',
                    paragraphs: [
                        'Security or abuse reports may be sent to kmjtechno.net@gmail.com. Include reproducible details and avoid accessing data beyond what is necessary to demonstrate the issue.',
                    ],
                },
            ]}
        />
    );
}
