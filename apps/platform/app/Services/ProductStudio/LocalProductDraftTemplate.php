<?php

namespace App\Services\ProductStudio;

use Illuminate\Support\Str;

/**
 * Owner-invoked offline scaffold, not AI inference or verified product copy.
 * Every claim is explicitly proposed and remains private until owner review.
 */
final class LocalProductDraftTemplate
{
    /** @return array<string, mixed> */
    public function fromBrief(string $brief): array
    {
        // The submitted brief is data, not a command or evidence of real features.
        $clean = trim((string) preg_replace('/[\x00-\x1f\x7f]+/u', ' ', strip_tags($brief)));
        $clean = trim((string) preg_replace('/\s+/u', ' ', $clean));
        $first = preg_split('/[.!?\n]/u', $clean, 2)[0] ?? $clean;
        // A short explicit identity such as "KMJ Calibration Studio is proposed..."
        // should not become "KMJ Calibration Studio is proposed projector...".
        // This is only a conservative name hint, never an AI or factual claim.
        $identity = $first;
        if (preg_match('/^(.+?)\s+(?:is|provides|offers)\s+\S/iu', $first, $matches) === 1) {
            $candidate = trim($matches[1]);
            $candidateWords = preg_split('/\s+/u', $candidate) ?: [];
            if (count($candidateWords) >= 2 && count($candidateWords) <= 8
                && preg_match('/^(?:this|that|our|the|a|an)\b/iu', $candidate) !== 1) {
                $identity = $candidate;
            }
        }
        $words = preg_split('/\s+/u', trim($identity)) ?: [];
        $name = implode(' ', array_slice($words, 0, 9));
        $name = trim((string) preg_replace('/[^\p{L}\p{N}\- ]/u', ' ', $name));
        $name = (string) preg_replace('/\binteactive\b/iu', 'Interactive', $name);
        $name = (string) preg_replace('/\bprojetion\b/iu', 'Projection', $name);
        $name = trim((string) Str::limit($name, 90, ''));
        if ($name === '' || Str::slug($name) === '') {
            $name = 'Proposed Product Concept';
        }

        $subject = (string) Str::limit($clean, 130, '');
        $summary = (string) Str::limit('Proposed concept: '.$subject, 160, '');
        $description = 'Owner-provided concept (not independently verified): '.$clean."\n\n".
            'This is an editable offline planning draft, not AI-generated copy or a statement that the product exists. '.
            'Features, hardware compatibility, pricing, release readiness, performance, and availability must be verified by the owner before publication.';
        $description = (string) Str::limit($description, 4000, '');

        return [
            'name' => $name,
            'category' => 'other',
            'offering_type' => preg_match('/\b(consulting|consultancy|support service|installation service)\b/iu', $clean) === 1
                ? 'service' : 'product',
            'summary' => $summary,
            'headline' => (string) Str::limit('Proposed concept for '.$name, 160, ''),
            'description' => $description,
            'features' => ['Proposed scope: '.(string) Str::limit($clean, 137, '')],
            'faqs' => [
                ['question' => 'Are the features and availability verified?',
                    'answer' => 'No. This is an offline owner-review draft from the supplied description. Details require verification.'],
            ],
            'photo_prompt' => (string) Str::limit('Illustrative conceptual composition for '.$name.
                ', no fabricated product screenshots, hardware guarantees, text, logos or watermarks. Not yet generated.', 600, ''),
            'banner_prompt' => (string) Str::limit('Wide illustrative composition for '.$name.
                ', with negative space; no fictional interface, branding, text, claims or watermarks. Not yet generated.', 600, ''),
        ];
    }
}
