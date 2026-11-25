@php($theme = \App\Services\Mail\EnterpriseMailTheme::palette())
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{{ $heading }}</title>
<meta name="format-detection" content="telephone=no,address=no,email=no">
<style>
@media only screen and (max-width:620px) {
  .kmj-wrap{width:100%!important;max-width:100%!important}
  .kmj-pad{padding-left:24px!important;padding-right:24px!important}
  .kmj-brand-mark{width:54px!important;height:54px!important}
  .kmj-brand-name{font-size:23px!important;line-height:28px!important}
  .kmj-tagline{font-size:14px!important;line-height:20px!important}
  .kmj-title{font-size:29px!important;line-height:36px!important}
}
</style>
</head>
<body style="margin:0;padding:0;background:#edf1f5;color:#172236;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
<div style="display:none!important;font-size:1px;line-height:1px;color:#edf1f5;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">{{ $heading }} · KMJ TECHNO official correspondence.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#edf1f5" style="width:100%;background:#edf1f5;border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px 40px;">
<table class="kmj-wrap" role="presentation" width="620" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:620px;border-collapse:collapse;">
@include('emails.partials.kmj-enterprise-header')
<tr><td class="kmj-pad" bgcolor="#ffffff" style="padding:38px 40px 42px;background:#ffffff;border-left:1px solid #e1e6ed;border-right:1px solid #e1e6ed;">
<p style="margin:0 0 13px;color:{{ $theme['accent'] }};font-size:11px;line-height:18px;font-weight:bold;letter-spacing:1.4px;text-transform:uppercase;">OFFICIAL COMMUNICATION</p>
<h1 class="kmj-title" style="margin:0 0 26px;color:#142035;font-size:33px;line-height:41px;letter-spacing:-0.7px;font-weight:800;overflow-wrap:break-word;">{{ $heading }}</h1>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;margin-bottom:25px;"><tr><td width="38" height="3" bgcolor="{{ $theme['accent'] }}" style="width:38px;height:3px;font-size:0;line-height:3px;background:{{ $theme['accent'] }};">&nbsp;</td><td style="border-bottom:1px solid #e7ebf0;font-size:0;line-height:3px;">&nbsp;</td></tr></table>
<div style="font-size:16px;line-height:28px;color:#25354a;overflow-wrap:anywhere;white-space:pre-wrap;">{{ $body }}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;border-collapse:collapse;"><tr><td bgcolor="{{ $theme['tint'] }}" style="padding:15px 18px;border-left:3px solid {{ $theme['accent'] }};color:#26384c;font-size:13px;line-height:21px;"><strong style="color:{{ $theme['accent'] }};">Sent through KMJ TECHNO Mail</strong><br>Official business correspondence</td></tr></table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;margin-top:38px;"><tr><td style="border-top:1px solid #e5eaf0;font-size:0;line-height:0;">&nbsp;</td></tr></table>
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;margin-top:24px;"><tr>
<td width="3" bgcolor="{{ $theme['accent'] }}" style="width:3px;background:{{ $theme['accent'] }};font-size:0;">&nbsp;</td>
<td style="padding:0 0 0 17px;">
<p style="margin:0 0 7px;color:#68778c;font-size:14px;line-height:22px;">With regards,</p>
<p style="margin:0;color:#152238;font-size:16px;line-height:24px;font-weight:bold;">KMJ TECHNO</p>
<p style="margin:4px 0 0;font-size:14px;line-height:21px;"><a href="mailto:{{ $senderAddress }}" style="color:{{ $theme['accent'] }};text-decoration:none;">{{ $senderAddress }}</a></p>
</td></tr></table>
</td></tr>
@include('emails.partials.kmj-enterprise-services')
@include('emails.partials.kmj-enterprise-footer', ['footerNotice' => 'Confidentiality notice: This correspondence may contain confidential information. If received in error, notify the sender and delete it. Verify unexpected messages before replying.'])
<tr><td align="center" style="padding:20px 12px;color:#8590a3;font-size:11px;line-height:18px;">&copy; {{ date('Y') }} KMJ TECHNO. All rights reserved.</td></tr>
</table></td></tr></table>
</body></html>
