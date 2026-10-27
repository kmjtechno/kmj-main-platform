const categoryRank = new Map([
    ['Cloud & Infrastructure', 0],
    ['Industrial & Calibration', 1],
    ['Cinema & Immersive', 2],
    ['Business & Platform', 3],
    ['Developer & AI', 4],
    ['Platform & Infrastructure', 0],
    ['Engineering & Automation', 1],
    ['Calibration & Vision Systems', 2],
    ['Secure Access & Connectivity', 3],
    ['Commerce & Licensing', 4],
    ['Media & Immersive Experience', 5],
]);

export function compareProductCategories(left, right) {
    const rank =
        (categoryRank.get(left) ?? Number.MAX_SAFE_INTEGER) -
        (categoryRank.get(right) ?? Number.MAX_SAFE_INTEGER);
    return rank || left.localeCompare(right);
}
