import { Head, Link, useForm } from '@inertiajs/react';
import {
    ArrowDown,
    ArrowUp,
    ExternalLink,
    Package,
    Plus,
    Save,
    Trash2,
    Upload,
} from 'lucide-react';
import { useState, type ReactNode } from 'react';
import OperatorModuleNavigation from '@/components/operator-module-navigation';
import type {
    Website,
    WebsiteFeature,
    WebsiteHeading,
    WebsiteSection,
} from '@/lib/website';
import type { TeamMember } from '@/pages/team';

type Member = TeamMember & { visible: boolean };
type Team = { published: boolean; intro: string; members: Member[] };
type Settings = Omit<Website, 'team_published'> & { team: Team };

const featureLabels: Record<WebsiteFeature, [string, string]> = {
    smooth_scrolling: ['Smooth scrolling', 'Gliding scroll on public pages.'],
    scroll_animations: [
        'Scroll animations',
        'Cards fade in and react to the mouse.',
    ],
    scroll_to_top: ['Scroll to top button', 'Arrow button after scrolling.'],
    kristi: ['Kristi guide', 'Avatar button with the product guide.'],
    language_button: [
        'Hindi / English button',
        'Visitors who saved Hindi always see the English button.',
    ],
};
const sectionLabels: Record<WebsiteSection, string> = {
    trust: 'Highlights strip',
    products: 'Flagship products',
    capabilities: 'What we build',
    ecosystem: 'Ecosystem',
    industries: 'Industries',
    roadmap: 'Roadmap',
};

const card = 'bg-card border-border rounded-2xl border p-5 sm:p-6';
const input =
    'bg-background border-border focus-visible:ring-ring min-h-11 w-full rounded-lg border px-3 py-2 text-sm outline-none focus-visible:ring-2';
const primary =
    'inline-flex min-h-11 items-center gap-2 rounded-lg bg-[#c1121f] px-5 text-sm font-bold text-white disabled:opacity-50';
const quiet =
    'border-border inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 text-xs font-bold disabled:opacity-40';

function Toggle({
    label,
    help,
    checked,
    onChange,
}: {
    label: string;
    help?: string;
    checked: boolean;
    onChange: (value: boolean) => void;
}) {
    return (
        <label className="border-border flex min-h-14 cursor-pointer items-center justify-between gap-4 rounded-xl border px-4 py-3">
            <span>
                <span className="block text-sm font-bold">{label}</span>
                {help && (
                    <span className="text-muted-foreground block text-xs">
                        {help}
                    </span>
                )}
            </span>
            <input
                type="checkbox"
                role="switch"
                checked={checked}
                onChange={(event) => onChange(event.target.checked)}
                className="h-5 w-5 shrink-0 accent-[#c1121f]"
            />
        </label>
    );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
    return (
        <label className="block text-xs font-bold">
            <span className="mb-1.5 block">{label}</span>
            {children}
        </label>
    );
}

function Errors({ errors }: { errors: Record<string, string | undefined> }) {
    const messages = Object.values(errors).filter(Boolean);

    return messages.length ? (
        <ul role="alert" className="text-sm font-semibold text-red-500">
            {messages.map((message, index) => (
                <li key={index}>{message}</li>
            ))}
        </ul>
    ) : null;
}

async function uploadPhoto(file: File): Promise<string> {
    const token = document.cookie
        .split('; ')
        .find((item) => item.startsWith('XSRF-TOKEN='))
        ?.slice('XSRF-TOKEN='.length);
    const body = new FormData();
    body.append('photo', file);
    const response = await fetch('/operator/website/team/photo', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            Accept: 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            ...(token ? { 'X-XSRF-TOKEN': decodeURIComponent(token) } : {}),
        },
        body,
    });
    const result = (await response.json().catch(() => null)) as {
        path?: string;
        message?: string;
    } | null;

    if (!response.ok || !result?.path) {
        throw new Error(
            response.status === 423
                ? 'Confirm your password again, then retry.'
                : (result?.message ?? 'Photo upload failed.'),
        );
    }

    return result.path;
}

function SiteForm({ settings, ready }: { settings: Settings; ready: boolean }) {
    const form = useForm({
        features: settings.features,
        sections: settings.sections,
        headings: settings.headings,
        roadmap: settings.roadmap,
    });
    const { data, setData } = form;

    return (
        <form
            className="space-y-5"
            onSubmit={(event) => {
                event.preventDefault();
                form.put('/operator/website/site', { preserveScroll: true });
            }}
        >
            <section className={card}>
                <h2 className="text-lg font-extrabold">Features</h2>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {(Object.keys(featureLabels) as WebsiteFeature[]).map(
                        (key) => (
                            <Toggle
                                key={key}
                                label={featureLabels[key][0]}
                                help={featureLabels[key][1]}
                                checked={data.features[key]}
                                onChange={(value) =>
                                    setData('features', {
                                        ...data.features,
                                        [key]: value,
                                    })
                                }
                            />
                        ),
                    )}
                </div>
            </section>
            <section className={card}>
                <h2 className="text-lg font-extrabold">Home page sections</h2>
                <div className="mt-4 grid gap-4">
                    {(Object.keys(sectionLabels) as WebsiteSection[]).map(
                        (key) => (
                            <div key={key} className="grid gap-3">
                                <Toggle
                                    label={`Show ${sectionLabels[key]}`}
                                    checked={data.sections[key]}
                                    onChange={(value) =>
                                        setData('sections', {
                                            ...data.sections,
                                            [key]: value,
                                        })
                                    }
                                />
                                {key !== 'trust' && (
                                    <div className="grid gap-3 md:grid-cols-[1fr_2fr]">
                                        {(['title', 'subtitle'] as const).map(
                                            (field) => (
                                                <Field
                                                    key={field}
                                                    label={`${sectionLabels[key]} ${field}`}
                                                >
                                                    <input
                                                        className={input}
                                                        required
                                                        maxLength={
                                                            field === 'title'
                                                                ? 80
                                                                : 200
                                                        }
                                                        value={
                                                            data.headings[
                                                                key as WebsiteHeading
                                                            ][field]
                                                        }
                                                        onChange={(event) =>
                                                            setData(
                                                                'headings',
                                                                {
                                                                    ...data.headings,
                                                                    [key]: {
                                                                        ...data
                                                                            .headings[
                                                                            key as WebsiteHeading
                                                                        ],
                                                                        [field]:
                                                                            event
                                                                                .target
                                                                                .value,
                                                                    },
                                                                },
                                                            )
                                                        }
                                                    />
                                                </Field>
                                            ),
                                        )}
                                    </div>
                                )}
                            </div>
                        ),
                    )}
                </div>
            </section>
            <section className={card}>
                <h2 className="text-lg font-extrabold">Roadmap steps</h2>
                <p className="text-muted-foreground mt-1 text-xs">
                    Write only plans you are ready to show publicly.
                </p>
                <div className="mt-4 grid gap-4 xl:grid-cols-2">
                    {data.roadmap.map((step, index) => (
                        <fieldset
                            key={index}
                            className="border-border grid gap-3 rounded-xl border p-4"
                        >
                            <legend className="px-1 text-xs font-extrabold">
                                Step {index + 1}
                            </legend>
                            {(
                                [
                                    ['title', 'Title', 40],
                                    ['summary', 'Short line', 120],
                                    ['text', 'Details', 240],
                                ] as const
                            ).map(([field, label, max]) => (
                                <Field key={field} label={label}>
                                    <input
                                        className={input}
                                        required
                                        maxLength={max}
                                        value={step[field]}
                                        onChange={(event) =>
                                            setData(
                                                'roadmap',
                                                data.roadmap.map((item, i) =>
                                                    i === index
                                                        ? {
                                                              ...item,
                                                              [field]:
                                                                  event.target
                                                                      .value,
                                                          }
                                                        : item,
                                                ),
                                            )
                                        }
                                    />
                                </Field>
                            ))}
                        </fieldset>
                    ))}
                </div>
            </section>
            <Errors errors={form.errors} />
            <button
                type="submit"
                className={primary}
                disabled={!ready || form.processing}
            >
                <Save aria-hidden="true" size={16} />
                Save website settings
            </button>
            {form.recentlySuccessful && (
                <p role="status" className="text-sm font-bold">
                    Saved.
                </p>
            )}
        </form>
    );
}

function TeamForm({ team, ready }: { team: Team; ready: boolean }) {
    const form = useForm<Team>(team);
    const { data, setData } = form;
    const [uploading, setUploading] = useState<number | null>(null);
    const [uploadError, setUploadError] = useState('');

    const change = (index: number, values: Partial<Member>) =>
        setData((current) => ({
            ...current,
            members: current.members.map((member, i) =>
                i === index ? { ...member, ...values } : member,
            ),
        }));
    const move = (index: number, step: -1 | 1) => {
        const members = [...data.members];
        [members[index], members[index + step]] = [
            members[index + step],
            members[index],
        ];
        setData('members', members);
    };

    return (
        <form
            className="space-y-5"
            onSubmit={(event) => {
                event.preventDefault();
                form.transform((values) => ({
                    ...values,
                    members: values.members.map((member) => ({
                        ...member,
                        linkedin: member.linkedin?.trim() || null,
                    })),
                }));
                form.put('/operator/website/team', { preserveScroll: true });
            }}
        >
            <section className={card}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className="text-lg font-extrabold">
                        Team Members page
                    </h2>
                    <a
                        href="/team"
                        target="_blank"
                        rel="noopener noreferrer"
                        className={quiet}
                    >
                        <ExternalLink aria-hidden="true" size={15} />
                        View saved page
                    </a>
                </div>
                <div className="mt-4 grid gap-4">
                    <Toggle
                        label="Publish the Team page"
                        help="Off: only you can preview it. On: public, with links on the Company page and footer."
                        checked={data.published}
                        onChange={(value) => setData('published', value)}
                    />
                    <Field label="Introduction">
                        <input
                            className={input}
                            maxLength={300}
                            value={data.intro}
                            onChange={(event) =>
                                setData('intro', event.target.value)
                            }
                        />
                    </Field>
                    <p className="text-muted-foreground text-xs">
                        The starting profiles are samples. Replace them before
                        publishing, and add only people who agreed to be shown.
                    </p>
                </div>
            </section>
            {data.members.map((member, index) => (
                <fieldset key={index} className={card}>
                    <legend className="px-1 text-sm font-extrabold">
                        Member {index + 1}
                    </legend>
                    <div className="grid gap-3 md:grid-cols-2">
                        <Field label="Name">
                            <input
                                className={input}
                                required
                                maxLength={120}
                                value={member.name}
                                onChange={(event) =>
                                    change(index, { name: event.target.value })
                                }
                            />
                        </Field>
                        <Field label="Role">
                            <input
                                className={input}
                                required
                                maxLength={120}
                                value={member.role}
                                onChange={(event) =>
                                    change(index, { role: event.target.value })
                                }
                            />
                        </Field>
                        <Field label="Short introduction">
                            <textarea
                                className={input}
                                maxLength={400}
                                rows={2}
                                value={member.bio ?? ''}
                                onChange={(event) =>
                                    change(index, { bio: event.target.value })
                                }
                            />
                        </Field>
                        <Field label="LinkedIn link (https://www.linkedin.com/…)">
                            <input
                                className={input}
                                type="url"
                                maxLength={200}
                                value={member.linkedin ?? ''}
                                onChange={(event) =>
                                    change(index, {
                                        linkedin: event.target.value,
                                    })
                                }
                            />
                        </Field>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                        {member.photo && (
                            <img
                                src={member.photo}
                                alt=""
                                width="56"
                                height="56"
                                className="h-14 w-14 rounded-full object-cover"
                            />
                        )}
                        <label className={`${quiet} cursor-pointer`}>
                            <Upload aria-hidden="true" size={15} />
                            {uploading === index
                                ? 'Uploading…'
                                : 'Upload photo'}
                            <input
                                type="file"
                                accept="image/png,image/jpeg,image/webp"
                                className="sr-only"
                                disabled={uploading !== null}
                                onChange={async (event) => {
                                    const file = event.target.files?.[0];
                                    event.target.value = '';

                                    if (!file) {
                                        return;
                                    }

                                    setUploading(index);
                                    setUploadError('');

                                    try {
                                        change(index, {
                                            photo: await uploadPhoto(file),
                                        });
                                    } catch (error) {
                                        setUploadError(
                                            (error as Error).message,
                                        );
                                    } finally {
                                        setUploading(null);
                                    }
                                }}
                            />
                        </label>
                        {member.photo && (
                            <button
                                type="button"
                                className={quiet}
                                onClick={() => change(index, { photo: null })}
                            >
                                Remove photo
                            </button>
                        )}
                        <label className="flex min-h-10 items-center gap-2 text-xs font-bold">
                            <input
                                type="checkbox"
                                checked={member.visible}
                                onChange={(event) =>
                                    change(index, {
                                        visible: event.target.checked,
                                    })
                                }
                                className="h-4 w-4 accent-[#c1121f]"
                            />
                            Show on page
                        </label>
                        <span className="ml-auto flex gap-2">
                            <button
                                type="button"
                                className={quiet}
                                aria-label={`Move member ${index + 1} up`}
                                disabled={index === 0 || uploading !== null}
                                onClick={() => move(index, -1)}
                            >
                                <ArrowUp aria-hidden="true" size={15} />
                            </button>
                            <button
                                type="button"
                                className={quiet}
                                aria-label={`Move member ${index + 1} down`}
                                disabled={
                                    index === data.members.length - 1 ||
                                    uploading !== null
                                }
                                onClick={() => move(index, 1)}
                            >
                                <ArrowDown aria-hidden="true" size={15} />
                            </button>
                            <button
                                type="button"
                                className={quiet}
                                disabled={uploading !== null}
                                onClick={() =>
                                    setData(
                                        'members',
                                        data.members.filter(
                                            (_, i) => i !== index,
                                        ),
                                    )
                                }
                            >
                                <Trash2 aria-hidden="true" size={15} />
                                Remove
                            </button>
                        </span>
                    </div>
                </fieldset>
            ))}
            {uploadError && (
                <p role="alert" className="text-sm font-semibold text-red-500">
                    {uploadError}
                </p>
            )}
            <Errors errors={form.errors} />
            <div className="flex flex-wrap gap-3">
                <button
                    type="button"
                    className={quiet}
                    disabled={data.members.length >= 40}
                    onClick={() =>
                        setData('members', [
                            ...data.members,
                            {
                                name: '',
                                role: '',
                                bio: '',
                                photo: null,
                                linkedin: '',
                                visible: true,
                            },
                        ])
                    }
                >
                    <Plus aria-hidden="true" size={15} />
                    Add member
                </button>
                <button
                    type="submit"
                    className={primary}
                    disabled={!ready || form.processing || uploading !== null}
                >
                    <Save aria-hidden="true" size={16} />
                    Save team page
                </button>
            </div>
            {form.recentlySuccessful && (
                <p role="status" className="text-sm font-bold">
                    Saved.
                </p>
            )}
        </form>
    );
}

export default function OperatorWebsite({
    settings,
    ready,
}: {
    settings: Settings;
    ready: boolean;
}) {
    const [tab, setTab] = useState<'site' | 'team'>('site');

    return (
        <>
            <Head title="Website controls" />
            <div className="mx-auto w-full max-w-6xl space-y-5 p-4 sm:p-6">
                <OperatorModuleNavigation active="website" />
                <header>
                    <h1 className="text-2xl font-black">Website controls</h1>
                    <p className="text-muted-foreground mt-1 text-sm">
                        Control the public website. Product names, text,
                        pictures and visibility are managed in Products.
                    </p>
                    <Link href="/operator/products" className={`${quiet} mt-3`}>
                        <Package aria-hidden="true" size={15} />
                        Open Products
                    </Link>
                </header>
                {!ready && (
                    <p
                        role="status"
                        className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm font-semibold"
                    >
                        Saving is not ready yet: the release database step has
                        not been run.
                    </p>
                )}
                <div className="flex gap-2">
                    {(
                        [
                            ['site', 'Features and home page'],
                            ['team', 'Team members'],
                        ] as const
                    ).map(([key, label]) => (
                        <button
                            key={key}
                            type="button"
                            aria-pressed={tab === key}
                            onClick={() => setTab(key)}
                            className={tab === key ? primary : quiet}
                        >
                            {label}
                        </button>
                    ))}
                </div>
                {/* Both forms stay mounted so unsaved edits survive a switch. */}
                <div hidden={tab !== 'site'}>
                    <SiteForm settings={settings} ready={ready} />
                </div>
                <div hidden={tab !== 'team'}>
                    <TeamForm team={settings.team} ready={ready} />
                </div>
            </div>
        </>
    );
}
