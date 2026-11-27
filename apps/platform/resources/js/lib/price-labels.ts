export type PricePlan = {
    name: string;
    unit: string;
    monthly_minor?: number;
    annual_minor?: number;
    minimum_units?: number;
    quote_from_minor?: number;
};

export type ProductPrices = { plans: PricePlan[] };

/** Rupees from paise, with Indian digit grouping. */
export function rupees(minor: number): string {
    return `₹${(minor / 100).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

/** Every paid amount is shown as exclusive of GST, as the owner approved. */
export function priceLines(plan: PricePlan): string[] {
    if (plan.quote_from_minor !== undefined) {
        return [
            `Price on quote · from ${rupees(plan.quote_from_minor)} + GST per ${plan.unit}`,
        ];
    }

    if (plan.monthly_minor === 0) {
        return ['Free'];
    }

    const lines: string[] = [];

    if (plan.monthly_minor !== undefined) {
        lines.push(
            `${rupees(plan.monthly_minor)} + GST per ${plan.unit} / month`,
        );
    }

    if (plan.annual_minor !== undefined) {
        lines.push(
            `or ${rupees(plan.annual_minor)} + GST per ${plan.unit} / year`,
        );
    }

    if (plan.minimum_units !== undefined) {
        lines.push(`Minimum ${plan.minimum_units} ${plan.unit}s`);
    }

    return lines;
}
