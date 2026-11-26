export type PasswordRequirement = {
    id: string;
    label: string;
    test: (password: string) => boolean;
};

/**
 * Turn the server's Apple-style `passwordrules` string (for example
 * "minlength: 12; required: lower; required: upper; required: digit;
 * required: [-]") into human requirements. The server stays authoritative;
 * this only tells people what to type before they submit.
 */
export function passwordRequirements(rules: string): PasswordRequirement[] {
    const out: PasswordRequirement[] = [];
    const min = /minlength:\s*(\d+)/i.exec(rules);
    if (min) {
        const n = Number(min[1]);
        out.push({
            id: 'length',
            label: `At least ${n} characters`,
            test: (password) => password.length >= n,
        });
    }
    if (/required:\s*lower/i.test(rules)) {
        out.push({
            id: 'lower',
            label: 'A lowercase letter',
            test: (password) => /[a-z]/.test(password),
        });
    }
    if (/required:\s*upper/i.test(rules)) {
        out.push({
            id: 'upper',
            label: 'An uppercase letter',
            test: (password) => /[A-Z]/.test(password),
        });
    }
    if (/required:\s*digit/i.test(rules)) {
        out.push({
            id: 'digit',
            label: 'A number',
            test: (password) => /\d/.test(password),
        });
    }
    if (/required:\s*(special|\[)/i.test(rules)) {
        out.push({
            id: 'symbol',
            label: 'A symbol (for example ! @ # $)',
            test: (password) => /[^A-Za-z0-9]/.test(password),
        });
    }

    return out;
}
