<?php
namespace App\Services\Licensing\Kslp;
use DomainException;
final class KslpCodec {
    public static function canonical(array $claims): string {
        self::sortRecursive($claims);
        return json_encode($claims, JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
    }
    public static function encode(array $claims, string $kid, callable $sign): string {
        $header=["alg"=>"EdDSA","kid"=>$kid,"typ"=>"KSLP-v1"]; self::sortRecursive($header);
        $h=self::b64(json_encode($header,JSON_THROW_ON_ERROR)); $p=self::b64(self::canonical($claims));
        return $h.".".$p.".".self::b64($sign($h.".".$p));
    }
    public static function decode(string $token): array {
        $parts=explode(".",$token); if(count($parts)!==3) throw new DomainException("KSLP_MALFORMED");
        try {
            $header=json_decode(self::unb64($parts[0]),true,512,JSON_THROW_ON_ERROR);
            $claims=json_decode(self::unb64($parts[1]),true,512,JSON_THROW_ON_ERROR);
        } catch (\JsonException) {
            throw new DomainException("KSLP_MALFORMED");
        }
        if(($header["alg"]??null)!=="EdDSA"||($header["typ"]??null)!=="KSLP-v1") throw new DomainException("KSLP_UNSUPPORTED_ALGORITHM");
        return [$header,$claims,self::unb64($parts[2]),$parts[0].".".$parts[1]];
    }
    private static function b64(string $v): string { return rtrim(strtr(base64_encode($v),"+/","-_"),"="); }
    private static function unb64(string $v): string { $x=base64_decode(strtr($v,"-_","+/"),true); if($x===false) throw new DomainException("KSLP_MALFORMED"); return $x; }
    private static function sortRecursive(array &$v): void { ksort($v); foreach($v as &$x) if(is_array($x)) self::sortRecursive($x); }
}
