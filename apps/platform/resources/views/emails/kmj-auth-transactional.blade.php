<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <title>{{ $subject }}</title>
    <style>
        @media only screen and (max-width: 640px) {
            .kmj-wrap { width: 100% !important; }
            .kmj-padded { padding: 30px 22px !important; }
            .kmj-title { font-size: 28px !important; line-height: 35px !important; }
            .kmj-button { display: block !important; text-align: center !important; }
        }
    </style>
</head>
<body style="margin:0;padding:0;background:#f2f4f8;color:#172033;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;">
    <div style="display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0;overflow:hidden;mso-hide:all;">{{ $preheader }}</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;background:#f2f4f8;">
        <tr><td align="center" style="padding:40px 14px;">
            <table role="presentation" class="kmj-wrap" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:100%;border-collapse:separate;border-spacing:0;">
                <tr>
                    <td class="kmj-padded" style="padding:30px 36px;background:#11151d;border-radius:16px 16px 0 0;">
                        <a href="https://kmjtechno.com" style="text-decoration:none;border:0;display:inline-block;" target="_blank">
                            <img src="https://kmjtechno.com/assets/brand/kmj-logo-horizontal.webp" width="178" alt="KMJ TECHNO" style="display:block;max-width:178px;height:auto;min-height:24px;border:0;outline:none;text-decoration:none;color:#ffffff;font-size:19px;font-weight:800;">
                        </a>
                    </td>
                </tr>
                <tr>
                    <td class="kmj-padded" style="background:#ffffff;padding:40px 36px;border-left:1px solid #e6e9f0;border-right:1px solid #e6e9f0;">
                        <p style="margin:0 0 12px;font-size:12px;line-height:18px;color:#ba163b;font-weight:bold;letter-spacing:1.6px;text-transform:uppercase;">{{ $eyebrow }}</p>
                        <h1 class="kmj-title" style="margin:0 0 20px;font-size:33px;line-height:42px;font-weight:800;color:#101827;">{{ $heading }}</h1>
                        <p style="margin:0 0 24px;color:#465368;font-size:16px;line-height:27px;">{{ $intro }}</p>
                        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:separate;border-spacing:0;">
                            <tr><td bgcolor="#d82446" style="border-radius:9px;background:#d82446;">
                                <a class="kmj-button" href="{{ $actionUrl }}" target="_blank" style="display:inline-block;border:1px solid #d82446;border-radius:9px;padding:15px 28px;text-decoration:none;color:#ffffff;font-size:15px;line-height:21px;font-weight:bold;">{{ $actionText }} &rarr;</a>
                            </td></tr>
                        </table>
                        <p style="margin:28px 0 12px;font-size:14px;line-height:23px;color:#465368;">{{ $expiryText }}</p>
                        <p style="margin:0;font-size:13px;line-height:22px;color:#657187;">If you did not request this action, you can safely ignore this email. Never share account recovery links or codes with anyone.</p>
                        <div style="margin:30px 0 14px;border-top:1px solid #e7ebf1;"></div>
                        <p style="margin:0 0 7px;font-size:12px;line-height:20px;color:#657187;">Button not working? Copy and paste this secure link into your browser:</p>
                        <p style="margin:0;font-size:12px;line-height:19px;word-break:break-all;overflow-wrap:anywhere;">
                            <a href="{{ $actionUrl }}" style="color:#b91e40;text-decoration:underline;">{{ $actionUrl }}</a>
                        </p>
                    </td>
                </tr>
                <tr>
                    <td class="kmj-padded" style="background:#fafbfc;border:1px solid #e6e9f0;border-top:0;border-radius:0 0 16px 16px;padding:26px 36px;">
                        <p style="margin:0 0 5px;font-size:14px;line-height:22px;font-weight:bold;color:#192333;">KMJ TECHNO</p>
                        <p style="margin:0 0 10px;color:#667286;font-size:12px;line-height:20px;">Secure account communications &middot; INNOVATE | BUILD | SCALE</p>
                        <p style="margin:0;font-size:12px;line-height:20px;">
                            <a href="https://kmjtechno.com" style="color:#b91e40;text-decoration:none;">kmjtechno.com</a>
                            &nbsp;&middot;&nbsp;
                            <a href="mailto:info@kmjtechno.com" style="color:#b91e40;text-decoration:none;">info@kmjtechno.com</a>
                        </p>
                    </td>
                </tr>
                <tr><td align="center" style="padding:22px 12px;color:#8490a1;font-size:11px;line-height:18px;">&copy; {{ date('Y') }} KMJ TECHNO. This is an account security email, not a marketing promotion.</td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>
