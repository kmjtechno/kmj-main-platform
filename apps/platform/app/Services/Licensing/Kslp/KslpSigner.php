<?php
namespace App\Services\Licensing\Kslp;
interface KslpSigner { public function kid():string; public function sign(string $message):string; }
