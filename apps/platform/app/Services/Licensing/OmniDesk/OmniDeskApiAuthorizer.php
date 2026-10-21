<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use Illuminate\Http\Request;

interface OmniDeskApiAuthorizer
{
    public function authorize(Request $request): OmniDeskApiPrincipal;
}
