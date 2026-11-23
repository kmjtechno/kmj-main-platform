<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ $heading }}</title>
<style>
@media only screen and (max-width:620px) {
.kmj-wrap{width:100%!important;max-width:100%!important}
.kmj-pad{padding:25px!important}
.kmj-logo{width:320px!important;max-width:100%!important}
}
</style>
</head>
<body style="margin:0;padding:0;background:#edf0f4;color:#172236;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;background:#edf0f4;border-collapse:collapse">
<tr><td align="center" style="padding:28px 12px 36px">
<table class="kmj-wrap" width="620" cellpadding="0" cellspacing="0" role="presentation" style="width:620px;max-width:620px;border-collapse:collapse">
<tr><td height="5" style="background:#cd2141;line-height:5px">&nbsp;</td></tr>
<tr><td class="kmj-pad" style="padding:32px 40px;background:#101722">
<a href="https://kmjtechno.com" style="text-decoration:none">
<img class="kmj-logo" src="https://kmjtechno.com/assets/brand/kmj-email-lockup-dark-trim.png" width="440" alt="KMJ TECHNO — INNOVATE | BUILD | SCALE" style="display:block;border:0;width:360px;max-width:100%;height:auto;color:#fff;font-size:17px;font-weight:bold">
</a>
<p style="margin:25px 0 0;color:#bec8d7;font-size:11px;font-weight:bold;letter-spacing:2px">KMJ MAIL · PROFESSIONAL CORRESPONDENCE</p>
</td></tr>
<tr><td class="kmj-pad" style="padding:35px 40px 40px;background:#fff;border:1px solid #dfe4ea">
<h1 style="margin:0 0 24px;font-size:27px;line-height:35px;color:#172236">{{ $heading }}</h1>
<div style="font-size:15px;line-height:25px;color:#36445a;overflow-wrap:anywhere;white-space:pre-wrap">{{ $body }}</div>
<p style="margin:34px 0 0;border-top:1px solid #e7eaf0;padding-top:20px;color:#546174;font-size:13px;line-height:23px">
With regards,<br><strong style="color:#172236">KMJ TECHNO</strong><br>
<a href="mailto:{{ $senderAddress }}" style="color:#b91c3c;text-decoration:underline">{{ $senderAddress }}</a>
</p>
</td></tr>
<tr><td class="kmj-pad" style="padding:20px 40px;background:#f9fafc;border:1px solid #dfe4ea;border-top:0">
<p style="margin:0 0 5px;color:#172236;font-size:14px;font-weight:bold">KMJ TECHNO</p>
<p style="margin:0;color:#79869a;font-size:13px;line-height:20px;font-weight:bold;letter-spacing:1px">INNOVATE | BUILD | SCALE</p>
<p style="margin:12px 0 0;color:#79869a;font-size:11px">This email was sent through the independent KMJ Mail system. No Gmail connection is required.</p>
</td></tr></table></td></tr></table>
</body></html>
