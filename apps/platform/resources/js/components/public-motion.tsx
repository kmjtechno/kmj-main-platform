import Lenis from 'lenis';
import { ArrowUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import 'lenis/dist/lenis.css';

/** Cards that fade up the first time they are scrolled into view. */
const REVEAL = [
    '.lock-trust > div',
    '.lock-heading',
    '.lock-product',
    '.lock-capabilities > a',
    '.lock-ecosystem-scene',
    '.lock-industries > a',
    '.lock-roadmap-steps > div',
    '.kmj-card',
].join(',');

/** Cards with a soft light that follows the mouse. */
const SPOTLIGHT = [
    '.lock-product',
    '.lock-capabilities > a',
    '.lock-roadmap-steps > div',
    '.kmj-card',
].join(',');

/**
 * Smooth scrolling and motion for public pages. Everything stays visible and
 * natively scrollable without JavaScript or when reduced motion is requested.
 */
export default function PublicMotion() {
    const smooth = useRef<Lenis | null>(null);
    const [deep, setDeep] = useState(false);

    const toTop = () => {
        if (smooth.current) {
            smooth.current.scrollTo(0);
        } else {
            window.scrollTo(0, 0);
        }

        document
            .querySelector<HTMLElement>('.kmj-public-header a')
            ?.focus({ preventScroll: true });
    };

    useEffect(() => {
        const header =
            document.querySelector<HTMLElement>('.kmj-public-header');
        const onScroll = () => {
            const range =
                document.documentElement.scrollHeight - window.innerHeight;
            header?.toggleAttribute('data-scrolled', window.scrollY > 12);
            setDeep(window.scrollY > 500);
            header?.style.setProperty(
                '--kmj-progress',
                String(range > 0 ? Math.min(window.scrollY / range, 1) : 0),
            );
        };
        onScroll();
        window.addEventListener('scroll', onScroll, { passive: true });
        const stopHeader = () => window.removeEventListener('scroll', onScroll);

        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return stopHeader;
        }

        const lenis = new Lenis({
            autoRaf: true,
            lerp: 0.1,
            anchors: { offset: -88 },
            allowNestedScroll: true,
            stopInertiaOnNavigate: true,
            prevent: (node) => node.getAttribute('role') === 'dialog',
        });

        smooth.current = lenis;

        // Dialogs lock the page; smooth scrolling must respect that lock.
        const lock = new MutationObserver(() => {
            if (document.body.hasAttribute('data-scroll-locked')) {
                lenis.stop();
            } else {
                lenis.start();
            }
        });
        lock.observe(document.body, {
            attributes: true,
            attributeFilter: ['data-scroll-locked'],
        });

        const reveal = new IntersectionObserver(
            (entries) => {
                entries
                    .filter((entry) => entry.isIntersecting)
                    .forEach((entry, index) => {
                        const element = entry.target as HTMLElement;
                        reveal.unobserve(element);
                        // Only cards fade. Text sections slide at full
                        // opacity so they never drop below readable contrast.
                        const fade = element.hasAttribute('data-reveal');
                        element.removeAttribute('data-reveal');
                        element.animate(
                            [
                                {
                                    opacity: fade ? 0 : 1,
                                    translate: '0 36px',
                                },
                                { opacity: 1, translate: '0 0' },
                            ],
                            {
                                duration: 800,
                                delay: Math.min(index, 7) * 75,
                                easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)',
                                fill: 'backwards',
                            },
                        );
                    });
            },
            { rootMargin: '0px 0px -6% 0px' },
        );
        const targets = [
            ...document.querySelectorAll<HTMLElement>(REVEAL),
            // Other public pages reveal whole sections below the first one.
            ...[
                ...document.querySelectorAll<HTMLElement>(
                    'main > section:not(:first-of-type)',
                ),
            ].filter((section) => !section.querySelector(REVEAL)),
        ];
        targets
            // Content already on screen is never hidden, so nothing flashes.
            .filter(
                (element) =>
                    element.getBoundingClientRect().top >
                    window.innerHeight * 0.94,
            )
            .forEach((element) => {
                if (element.matches(REVEAL)) {
                    element.setAttribute('data-reveal', '');
                }

                reveal.observe(element);
            });

        const onPointer = (event: PointerEvent) => {
            if (event.pointerType !== 'mouse') {
                return;
            }

            const target = event.target as Element;
            const card = target.closest<HTMLElement>(SPOTLIGHT);

            if (card) {
                const box = card.getBoundingClientRect();
                card.style.setProperty('--mx', `${event.clientX - box.left}px`);
                card.style.setProperty('--my', `${event.clientY - box.top}px`);
            }

            const hero = target.closest<HTMLElement>('.lock-hero');

            if (hero) {
                const box = hero.getBoundingClientRect();
                hero.style.setProperty(
                    '--px',
                    String((event.clientX - box.left) / box.width - 0.5),
                );
                hero.style.setProperty(
                    '--py',
                    String((event.clientY - box.top) / box.height - 0.5),
                );
            }
        };
        document.addEventListener('pointermove', onPointer, { passive: true });

        return () => {
            stopHeader();
            document.removeEventListener('pointermove', onPointer);
            reveal.disconnect();
            lock.disconnect();
            targets.forEach((element) =>
                element.removeAttribute('data-reveal'),
            );
            smooth.current = null;
            lenis.destroy();
        };
    }, []);

    return (
        <button
            type="button"
            className="kmj-to-top"
            data-visible={deep || undefined}
            aria-label="Scroll to top"
            title="Scroll to top"
            onClick={toTop}
        >
            <ArrowUp aria-hidden="true" size={20} />
        </button>
    );
}
