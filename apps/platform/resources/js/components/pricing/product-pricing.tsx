import { priceLines, type ProductPrices } from '@/lib/price-labels';

/** Colours inherit, so this works on public dark pages and in the app. */
export default function ProductPricing({
    pricing,
    onSale,
}: {
    pricing: ProductPrices;
    onSale: boolean;
}) {
    return (
        <div>
            {!onSale && (
                <p className="mb-3 text-sm font-bold">
                    Planned price. This product is not on sale yet.
                </p>
            )}
            <ul className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,14rem),1fr))] gap-3">
                {pricing.plans.map((plan) => (
                    <li
                        key={plan.name}
                        className="rounded-xl border border-current/15 p-4"
                    >
                        <p className="text-sm font-black">{plan.name}</p>
                        {priceLines(plan).map((line) => (
                            <p key={line} className="mt-1 text-sm opacity-80">
                                {line}
                            </p>
                        ))}
                    </li>
                ))}
            </ul>
            <p className="mt-3 text-xs opacity-70">
                GST is extra. Your own cloud, AI provider, hardware and onsite
                costs are not included. Nothing is charged automatically.
            </p>
        </div>
    );
}
