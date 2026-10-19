import type { Auth } from '@/types/auth';

declare module 'react' {
    interface InputHTMLAttributes<T> {
        passwordrules?: string;
    }
}

declare module '@inertiajs/core' {
    export interface InertiaConfig {
        sharedPageProps: {
            name: string;
            publicSite: {
                base_url: string;
                indexable: boolean;
                registration_available: boolean;
            };
            localization: {
                locale: 'en' | 'hi';
                supported: Array<'en' | 'hi'>;
                switch_locale: 'en' | 'hi';
                switch_label: string;
                switch_url: string;
            };
            auth: Auth;
            sidebarOpen: boolean;
            [key: string]: unknown;
        };
    }
}
