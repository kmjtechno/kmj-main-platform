import { usePage } from '@inertiajs/react';

export type WebsiteSection =
    | 'trust'
    | 'products'
    | 'capabilities'
    | 'ecosystem'
    | 'industries'
    | 'roadmap';
export type WebsiteHeading = Exclude<WebsiteSection, 'trust'>;
export type WebsiteFeature =
    | 'smooth_scrolling'
    | 'scroll_animations'
    | 'scroll_to_top'
    | 'kristi'
    | 'language_button';
export type RoadmapStep = { title: string; summary: string; text: string };

export type Website = {
    features: Record<WebsiteFeature, boolean>;
    sections: Record<WebsiteSection, boolean>;
    headings: Record<WebsiteHeading, { title: string; subtitle: string }>;
    roadmap: RoadmapStep[];
    team_published: boolean;
};

/** Same values as WebsiteSettings::defaults() on the server. */
export const websiteDefaults: Website = {
    features: {
        smooth_scrolling: true,
        scroll_animations: true,
        scroll_to_top: true,
        kristi: true,
        language_button: false,
    },
    sections: {
        trust: true,
        products: true,
        capabilities: true,
        ecosystem: true,
        industries: true,
        roadmap: true,
    },
    headings: {
        products: {
            title: 'Our Flagship Products',
            subtitle:
                'Powerful solutions for immersive experiences, intelligent operations and real-world impact.',
        },
        capabilities: {
            title: 'What We Build',
            subtitle:
                'From idea to global deployment — we build any kind of software, system or immersive experience.',
        },
        ecosystem: {
            title: 'A Complete and Connected Ecosystem',
            subtitle:
                'Our products work together to create a unified platform for creation, control, deployment and growth.',
        },
        industries: {
            title: 'Industries We Serve',
            subtitle: 'Real solutions for real-world challenges.',
        },
        roadmap: {
            title: 'Our Roadmap',
            subtitle: 'Building a future-ready ecosystem.',
        },
    },
    roadmap: [
        {
            title: 'Now',
            summary: 'Available Products',
            text: 'Review platform and product availability.',
        },
        {
            title: 'Next',
            summary: 'Enhanced Features',
            text: 'Advanced capabilities and new integrations.',
        },
        {
            title: 'In Development',
            summary: 'New Products',
            text: 'Ongoing development and testing.',
        },
        {
            title: 'Future',
            summary: 'Ecosystem Expansion',
            text: 'More industries, more tools and global reach.',
        },
    ],
    team_published: false,
};

/** Owner-controlled website settings, with the shipped values as fallback. */
export function useWebsite(): Website {
    const { website } = usePage().props as { website?: Website };

    return website ?? websiteDefaults;
}
