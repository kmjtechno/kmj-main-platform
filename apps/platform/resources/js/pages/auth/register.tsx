import { passwordRequirements } from '@/lib/password-rules-hint';
import { Form, Head } from '@inertiajs/react';
import { useState } from 'react';
import GoogleSignInButton from '@/components/google-signin-button';
import InputError from '@/components/input-error';
import PasswordInput from '@/components/password-input';
import TextLink from '@/components/text-link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { login } from '@/routes';
import { store } from '@/routes/register';

type Props = {
    passwordRules: string;
    registrationAvailable: boolean;
    formToken: string;
};

export default function Register({
    passwordRules,
    registrationAvailable,
    formToken,
}: Props) {
    const [accountType, setAccountType] = useState<'individual' | 'business'>(
        'individual',
    );
    const [password, setPassword] = useState('');
    const requirements = passwordRequirements(passwordRules);

    return (
        <>
            <Head title="Register" />
            <GoogleSignInButton label="Sign up with Google" />
            <Form
                {...store.form()}
                resetOnSuccess={['password', 'password_confirmation']}
                disableWhileProcessing
                className="flex flex-col gap-6"
            >
                {({ processing, errors }) => (
                    <>
                        {!registrationAvailable && (
                            <p
                                role="alert"
                                className="rounded-lg border p-3 text-sm"
                            >
                                Registration is temporarily unavailable while
                                verification email delivery is being restored.
                                For assistance, email{' '}
                                <TextLink href="mailto:info@kmjtechno.com">
                                    info@kmjtechno.com
                                </TextLink>
                                . Never send passwords or verification codes.
                            </p>
                        )}
                        <input
                            type="hidden"
                            name="kmj_form_token"
                            value={formToken}
                        />
                        {/* Honeypot: invisible to people and assistive tech, bots tend to fill it. */}
                        <div
                            aria-hidden="true"
                            style={{
                                position: 'absolute',
                                left: '-10000px',
                                width: '1px',
                                height: '1px',
                                overflow: 'hidden',
                            }}
                        >
                            <input
                                type="text"
                                name="website_url"
                                tabIndex={-1}
                                autoComplete="off"
                                defaultValue=""
                            />
                        </div>
                        <InputError message={errors.registration} />
                        <div className="grid gap-6">
                            <div className="grid gap-2">
                                <Label htmlFor="name">Name</Label>
                                <Input
                                    id="name"
                                    type="text"
                                    required
                                    autoFocus
                                    autoComplete="name"
                                    name="name"
                                    placeholder="Full name"
                                />
                                <InputError
                                    message={errors.name}
                                    className="mt-2"
                                />
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="email">Email address</Label>
                                <Input
                                    id="email"
                                    type="email"
                                    required
                                    autoComplete="email"
                                    name="email"
                                    placeholder="email@example.com"
                                />
                                <InputError message={errors.email} />
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="account_type">
                                    Account type
                                </Label>
                                <select
                                    id="account_type"
                                    name="account_type"
                                    required
                                    value={accountType}
                                    onChange={(event) =>
                                        setAccountType(
                                            event.target.value as
                                                | 'individual'
                                                | 'business',
                                        )
                                    }
                                    className="border-input bg-background h-10 w-full rounded-md border px-3 text-sm"
                                >
                                    <option value="individual">
                                        Individual
                                    </option>
                                    <option value="business">
                                        Business / organization
                                    </option>
                                </select>
                                <InputError message={errors.account_type} />
                            </div>

                            {accountType === 'business' && (
                                <div className="grid gap-2">
                                    <Label htmlFor="company_name">
                                        Company / organization name
                                    </Label>
                                    <Input
                                        id="company_name"
                                        name="company_name"
                                        type="text"
                                        required
                                        maxLength={160}
                                        autoComplete="organization"
                                        placeholder="Registered or operating name"
                                    />
                                    <InputError message={errors.company_name} />
                                </div>
                            )}

                            <div className="grid gap-2">
                                <Label htmlFor="phone">
                                    Contact phone number
                                </Label>
                                <Input
                                    id="phone"
                                    name="phone"
                                    type="tel"
                                    required
                                    maxLength={32}
                                    autoComplete="tel"
                                    placeholder="+91 98765 43210"
                                />
                                <p className="text-muted-foreground text-xs">
                                    Include your country code, for example +91.
                                </p>
                                <InputError message={errors.phone} />
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="country">Country</Label>
                                <Input
                                    id="country"
                                    name="country"
                                    type="text"
                                    required
                                    maxLength={80}
                                    autoComplete="country-name"
                                    placeholder="Your country"
                                />
                                <InputError message={errors.country} />
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="service_interest">
                                    Primary interest (optional)
                                </Label>
                                <select
                                    id="service_interest"
                                    name="service_interest"
                                    defaultValue=""
                                    className="border-input bg-background h-10 w-full rounded-md border px-3 text-sm"
                                >
                                    <option value="">Select later</option>
                                    <option value="software">
                                        Software & AI
                                    </option>
                                    <option value="cloud">
                                        CloudOS & hosting
                                    </option>
                                    <option value="remote_access">
                                        OmniDesk remote access
                                    </option>
                                    <option value="calibration">
                                        Calibration technology
                                    </option>
                                    <option value="cinema">
                                        Cinema & immersive
                                    </option>
                                    <option value="other">
                                        Other services
                                    </option>
                                </select>
                                <InputError message={errors.service_interest} />
                                <p className="text-muted-foreground text-xs leading-5">
                                    We request billing addresses, tax IDs and
                                    installation-site contacts only if your
                                    purchase or service needs them.
                                </p>
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="password">Password</Label>
                                <PasswordInput
                                    id="password"
                                    required
                                    autoComplete="new-password"
                                    name="password"
                                    placeholder="Password"
                                    passwordrules={passwordRules}
                                    value={password}
                                    onChange={(event) =>
                                        setPassword(event.target.value)
                                    }
                                    aria-describedby="password-requirements"
                                />
                                <ul
                                    id="password-requirements"
                                    className="text-muted-foreground grid gap-1 text-xs"
                                >
                                    {requirements.map((item) => (
                                        <li
                                            key={item.id}
                                            className={
                                                item.test(password)
                                                    ? 'text-emerald-600 dark:text-emerald-400'
                                                    : undefined
                                            }
                                        >
                                            {item.test(password) ? '✓' : '○'}{' '}
                                            {item.label}
                                        </li>
                                    ))}
                                </ul>
                                <InputError message={errors.password} />
                            </div>

                            <div className="grid gap-2">
                                <Label htmlFor="password_confirmation">
                                    Confirm password
                                </Label>
                                <PasswordInput
                                    id="password_confirmation"
                                    required
                                    autoComplete="new-password"
                                    name="password_confirmation"
                                    placeholder="Confirm password"
                                    passwordrules={passwordRules}
                                />
                                <InputError
                                    message={errors.password_confirmation}
                                />
                            </div>

                            <div className="text-muted-foreground text-xs leading-5">
                                By creating an account, you agree to the{' '}
                                <TextLink href="/terms">
                                    Terms & Conditions
                                </TextLink>{' '}
                                and acknowledge the{' '}
                                <TextLink href="/privacy">
                                    Privacy Policy
                                </TextLink>
                                .
                            </div>

                            <p className="text-muted-foreground text-xs leading-5">
                                What happens next: we email you a verification
                                link, you confirm your email, and your dashboard
                                opens with the steps to request a product.
                            </p>

                            <Button
                                type="submit"
                                disabled={processing || !registrationAvailable}
                                className="mt-2 w-full"
                                data-test="register-user-button"
                            >
                                {processing && <Spinner />}
                                Create account
                            </Button>
                        </div>

                        <div className="text-muted-foreground text-center text-sm">
                            Already have an account?{' '}
                            <TextLink href={login()}>Log in</TextLink>
                        </div>
                    </>
                )}
            </Form>
        </>
    );
}

Register.layout = {
    title: 'Create an account',
    description:
        'Secure access for individuals and businesses — no billing details required yet',
};
