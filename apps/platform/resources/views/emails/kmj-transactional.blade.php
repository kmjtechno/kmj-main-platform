<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <title>{{ $subject }}</title>
    <style>
        @media only screen and (max-width: 640px) {
            .kmj-wrap { width:100%!important; max-width:100%!important; }
            .kmj-pad { padding-left:24px!important; padding-right:24px!important; }
            .kmj-head { padding-top:28px!important; padding-bottom:26px!important; }
            .kmj-main { padding-top:36px!important; padding-bottom:31px!important; }
            .kmj-title { font-size:31px!important; line-height:38px!important; }
            .kmj-logo { width:320px!important; max-width:100%!important; }
            .kmj-button { display:block!important; text-align:center!important; }
        }
    </style>
</head>
<body style="margin:0;padding:0;width:100%;background:#edf0f4;color:#1a2436;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
    <div style="display:none!important;visibility:hidden;opacity:0;height:0;width:0;overflow:hidden;color:transparent;mso-hide:all;">{{ $preheader }}</div>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" bgcolor="#edf0f4" style="border-collapse:collapse;width:100%;background:#edf0f4;">
        <tr><td align="center" style="padding:32px 12px 40px;">
            <table class="kmj-wrap" role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:640px;max-width:640px;">
                <tr><td height="5" bgcolor="#cd2141" style="font-size:0;line-height:5px;background:#cd2141;">&nbsp;</td></tr>
                <tr><td class="kmj-pad kmj-head" bgcolor="#101722" style="padding:35px 43px 33px;background:#101722;">
                    <a href="https://kmjtechno.com" style="text-decoration:none;display:inline-block;">
                        <img class="kmj-logo" src="https://kmjtechno.com/assets/brand/kmj-email-lockup-dark-trim.png" width="440" alt="KMJ TECHNO — INNOVATE | BUILD | SCALE" style="display:block;border:0;outline:0;width:360px;max-width:100%;height:auto;color:#ffffff;font-weight:bold;font-size:20px;">
                    </a>
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:25px;"><tr><td style="border-top:1px solid #353c49;font-size:1px;line-height:1px;">&nbsp;</td></tr></table>
                    <p style="margin:20px 0 0;color:#c4ccd8;font-size:11px;line-height:19px;font-weight:bold;letter-spacing:1.6px;text-transform:uppercase;">{{ $eyebrow }}</p>
                </td></tr>
                <tr><td class="kmj-pad kmj-main" bgcolor="#ffffff" style="padding:44px 43px 41px;background:#ffffff;border-left:1px solid #dfe4ea;border-right:1px solid #dfe4ea;">
                    <p style="margin:0 0 13px;color:#bf1b3d;font-size:12px;line-height:19px;font-weight:bold;letter-spacing:1.6px;text-transform:uppercase;">KMJ TECHNO / {{ $category }}</p>
                    <h1 class="kmj-title" style="margin:0 0 20px;color:#141e30;font-size:36px;line-height:43px;letter-spacing:-.7px;font-weight:bold;">{{ $heading }}</h1>
                    <p style="margin:0 0 20px;color:#42516a;font-size:16px;line-height:27px;">{{ $greeting }}</p>
                    <p style="margin:0 0 26px;color:#42516a;font-size:15px;line-height:26px;">{{ $intro }}</p>
                    @if (count($details) > 0)
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f5f7fa" style="width:100%;border-collapse:collapse;background:#f5f7fa;border:1px solid #e4e9ef;">
                        <tr><td style="padding:20px 23px 5px;color:#66758a;font-size:11px;line-height:18px;letter-spacing:1.2px;font-weight:bold;">DETAILS</td></tr>
                        @foreach ($details as $detail)
                        <tr><td style="padding:10px 23px 11px;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;">
                                <tr>
                                    <td valign="top" width="43%" style="padding:0 10px 0 0;color:#69778a;font-size:13px;line-height:21px;">{{ $detail['label'] }}</td>
                                    <td valign="top" style="padding:0;color:#172336;font-size:14px;line-height:21px;font-weight:bold;word-break:break-word;">{{ $detail['value'] }}</td>
                                </tr>
                            </table>
                        </td></tr>
                        @endforeach
                        <tr><td style="height:12px;font-size:0;line-height:12px;">&nbsp;</td></tr>
                    </table>
                    @endif
                    @if ($actionUrl !== null && $actionText !== null)
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:30px;border-collapse:separate;"><tr>
                        <td bgcolor="#c7193d" style="background:#c7193d;border-radius:7px;">
                            <a class="kmj-button" href="{{ $actionUrl }}" target="_blank" style="display:inline-block;padding:16px 26px;color:#ffffff;text-decoration:none;font-size:15px;line-height:23px;font-weight:bold;">{{ $actionText }} &rarr;</a>
                        </td>
                    </tr></table>
                    <p style="margin:18px 0 0;color:#7b8798;font-size:12px;line-height:20px;">If the button does not work, open this link:</p>
                    <p style="margin:5px 0 0;color:#a81d3d;font-size:12px;line-height:21px;overflow-wrap:anywhere;word-break:break-all;"><a href="{{ $actionUrl }}" style="color:#a81d3d;text-decoration:underline;">{{ $actionUrl }}</a></p>
                    @endif
                    @if ($notice !== null)
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:27px;border-collapse:collapse;background:#fff7f8;">
                        <tr><td width="4" bgcolor="#c7193d" style="font-size:0;line-height:0;width:4px;">&nbsp;</td><td style="padding:16px 19px;color:#5d4860;font-size:13px;line-height:22px;">{{ $notice }}</td></tr>
                    </table>
                    @endif
                    <p style="margin:28px 0 0;color:#69778a;font-size:13px;line-height:22px;">Need help? Contact <a href="mailto:info@kmjtechno.com" style="color:#a91d3d;text-decoration:underline;">info@kmjtechno.com</a>. For your security, never send passwords, OTPs or private recovery links by email.</p>
                </td></tr>
                <tr><td class="kmj-pad" bgcolor="#f9fafc" style="padding:27px 43px;border:1px solid #dfe4ea;border-top:0;background:#f9fafc;">
                    <p style="margin:0 0 5px;color:#172236;font-size:16px;line-height:23px;font-weight:bold;">KMJ TECHNO</p>
                    <p style="margin:0 0 16px;color:#79869a;font-size:13px;line-height:20px;letter-spacing:1px;font-weight:bold;">INNOVATE | BUILD | SCALE</p>
                    <p style="margin:0 0 12px;color:#67758b;font-size:12px;line-height:21px;">This is a service notification about your KMJ TECHNO account or a transaction you initiated. It is not a promotional email.</p>
                    <p style="margin:0;color:#67758b;font-size:12px;line-height:20px;"><a href="https://kmjtechno.com" style="color:#a91d3d;text-decoration:none;">kmjtechno.com</a> &nbsp; | &nbsp; <a href="mailto:info@kmjtechno.com" style="color:#a91d3d;text-decoration:none;">Support</a></p>
                </td></tr>
                <tr><td align="center" style="padding:20px 12px;color:#8691a1;font-size:11px;line-height:18px;">&copy; {{ date('Y') }} KMJ TECHNO. Secure service communication.</td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>
