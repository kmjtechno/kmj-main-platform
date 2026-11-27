import { Form, Head } from '@inertiajs/react';
import { useState } from 'react';
import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';

export default function CompleteProfile({ email }: { email: string }) {
    const [accountType, setAccountType] = useState<'individual' | 'business'>(
        'individual',
    );

    return (
        <>
            <Head title="Complete your profile" />
            <Form
                method="post"
                action="/onboarding/profile"
                disableWhileProcessing
                className="flex flex-col gap-6"
            >
                {({ processing, errors }) => (
                    <div className="grid gap-6">
                        <p className="text-muted-foreground text-sm">
                            Signed in as <strong>{email}</strong>. We use these
                            details to contact you about your account and
                            purchases. You can change them later.
                        </p>
                        <div className="grid gap-2">
                            <Label htmlFor="account_type">Account type</Label>
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
                                <option value="individual">Individual</option>
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
                                />
                                <InputError message={errors.company_name} />
                            </div>
                        )}
                        <div className="grid gap-2">
                            <Label htmlFor="phone">Contact phone number</Label>
                            <Input
                                id="phone"
                                name="phone"
                                type="tel"
                                required
                                maxLength={32}
                                autoComplete="tel"
                                placeholder="+91 98765 43210"
                            />
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
                            />
                            <InputError message={errors.country} />
                        </div>
                        <Button type="submit" disabled={processing}>
                            {processing && <Spinner />}
                            Save and continue
                        </Button>
                    </div>
                )}
            </Form>
        </>
    );
}

CompleteProfile.layout = {
    title: 'Complete your profile',
    description: 'A few contact details, only once.',
};
