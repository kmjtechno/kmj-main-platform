/** Browser-local greeting; a neutral SSR value avoids hydration mismatches. */
export function ownerGreetingForHour(hour) {
    if (!Number.isInteger(hour) || hour < 0 || hour > 23) return 'Welcome,';
    if (hour < 12) return 'Good Morning,';
    if (hour < 17) return 'Good Afternoon,';
    return 'Good Evening,';
}
