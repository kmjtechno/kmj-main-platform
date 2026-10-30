// Synthetic, loopback-only fixture for the AI workspace browser check. Never real data.
export const REASONS = {
    conversations:
        'Conversations are stored per organization, user and paired project.',
    chat_executor:
        'Needs an enabled, healthy free provider with an admitted model. Add one in AI providers.',
    job_events:
        'Job status lives on the paired device and is read through CodeBridge in your AI client.',
    device_pairing: 'Pairing stays in the Main Platform Control Center.',
};

export type FixtureMessage = {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    status: 'complete' | 'running' | 'failed' | 'cancelled';
    provider_id: string | null;
    model: string | null;
    error_code: string | null;
    retry_of: string | null;
    started_at: string | null;
    finished_at: string | null;
    elapsed_seconds: number | null;
};

export function message(
    id: string,
    role: 'user' | 'assistant',
    status: FixtureMessage['status'],
    content = '',
    extra: Partial<FixtureMessage> = {},
): FixtureMessage {
    return {
        id,
        role,
        content,
        status,
        provider_id: role === 'assistant' ? 'qa-provider' : null,
        model: role === 'assistant' ? 'qa-free-model' : null,
        error_code: null,
        retry_of: null,
        started_at: role === 'assistant' ? '2026-10-29T12:00:00+00:00' : null,
        finished_at: null,
        elapsed_seconds: role === 'assistant' ? 3 : null,
        ...extra,
    };
}

export function workspaceProps(
    messages: FixtureMessage[] = [],
    events: Record<string, unknown>[] = [],
    chatError: string | null = null,
) {
    return {
        canManage: true,
        devices: [
            {
                id: 'qa-device',
                name: 'Synthetic preview desktop',
                platform: 'windows',
                arch: 'x64',
                projects: [
                    { id: 'qa-project', name: 'Synthetic preview project' },
                ],
                pending_projects: [],
                registered_at: '2026-01-01',
                registration: 'registered',
                pairing_state: 'redeemed',
                connection_status: 'not_verified',
            },
        ],
        providers: [
            {
                id: 'qa-provider',
                name: 'Synthetic free provider',
                host: 'api.example.invalid',
                enabled: true,
                health: 'ok',
                free_tier: 'allowlist',
                default_model: 'qa-free-model',
                free_admitted_models: ['qa-free-model'],
            },
        ],
        selected: { device_id: 'qa-device', project_id: 'qa-project' },
        conversations: [
            {
                id: 'qa-conv',
                title: 'Synthetic chat',
                updated_at: '2026-10-29 12:00:00',
            },
        ],
        activeConversation: { id: 'qa-conv', title: 'Synthetic chat' },
        transcript: { messages, events },
        chatError,
        jobs: [],
        jobEvents: [],
        activeJobId: null,
        tools: [],
        capabilities: {
            conversations: { available: true, reason: REASONS.conversations },
            chat_executor: { available: true, reason: REASONS.chat_executor },
            job_events: { available: false, reason: REASONS.job_events },
            device_pairing: { available: true, reason: REASONS.device_pairing },
        },
        links: {
            control_center: '/services/kmj-codebridge',
            ai_providers: '/services/kmj-codebridge/ai-providers',
        },
    };
}
