<?php

declare(strict_types=1);

namespace App\Services\Seo;

use App\Services\Commerce\CloudOSProductCatalog;

/**
 * Plain question-and-answer facts for a public product. The same list is shown
 * on the page, published as FAQ structured data and served to crawlers, so
 * search and answer engines never read a claim a visitor cannot see.
 */
final class ProductAnswers
{
    public const ACCESS_TRIAL = 'trial';

    public const ACCESS_REQUEST = 'request';

    public const ACCESS_PREREGISTER = 'preregister';

    /** @param array<string, mixed> $product */
    public function access(array $product): string
    {
        if (($product['purchase_enabled'] ?? false) !== true) {
            return self::ACCESS_PREREGISTER;
        }

        return ($product['slug'] ?? null) === CloudOSProductCatalog::SLUG
            && (bool) config('services.kmj_signup_trial.enabled', false)
                ? self::ACCESS_TRIAL
                : self::ACCESS_REQUEST;
    }

    /**
     * @param  array<string, mixed>  $product
     * @param  array{plans: list<array<string, mixed>>}|null  $pricing
     * @return list<array{question: string, answer: string}>
     */
    public function forProduct(array $product, ?array $pricing): array
    {
        $name = $this->text($product['name'] ?? null);
        if ($name === '') {
            return [];
        }

        $onSale = ($product['purchase_enabled'] ?? false) === true;
        $status = $this->text($product['lifecycle_label'] ?? null);
        $answers = [];

        $summary = $this->text($product['summary'] ?? null);
        if ($summary !== '') {
            $answers[] = ['question' => "What is {$name}?", 'answer' => $summary];
        }

        $answers[] = [
            'question' => "Is {$name} available now?",
            'answer' => $onSale
                ? "Yes. {$name} is listed as {$status} and you can request access today."
                : "Not yet. {$name} is listed as {$status} and is not on sale. You can pre-register your interest.",
        ];

        $plans = $this->planSentences($pricing);
        if ($plans !== []) {
            $answers[] = [
                'question' => "How much does {$name} cost?",
                'answer' => ($onSale ? 'Published prices' : 'Planned prices, not on sale yet')
                    .': '.implode('; ', $plans).'. GST is extra and nothing is charged automatically.',
            ];
        }

        $answers[] = [
            'question' => "How do I get {$name}?",
            'answer' => match ($this->access($product)) {
                self::ACCESS_TRIAL => 'Create a KMJ account and verify your email to start a 30-day free trial. A paid plan starts only after KMJ confirms your payment.',
                self::ACCESS_REQUEST => 'Create a KMJ account and request access. Access is activated after KMJ confirms your payment.',
                default => 'Create a KMJ account to pre-register. Pre-registration is free and does not give access until the product is released.',
            },
        ];

        $faqs = $product['content']['faqs'] ?? [];
        foreach (is_array($faqs) ? array_slice($faqs, 0, 8) : [] as $faq) {
            $question = $this->text($faq['question'] ?? null);
            $answer = $this->text($faq['answer'] ?? null);
            if ($question !== '' && $answer !== '') {
                $answers[] = ['question' => $question, 'answer' => $answer];
            }
        }

        return $answers;
    }

    /**
     * @param  array{plans: list<array<string, mixed>>}|null  $pricing
     * @return list<string>
     */
    public function planSentences(?array $pricing): array
    {
        $sentences = [];

        foreach ($pricing['plans'] ?? [] as $plan) {
            $unit = $this->text($plan['unit'] ?? null);
            $parts = [];

            if (isset($plan['quote_from_minor'])) {
                $parts[] = 'price on quote, from '.$this->rupees((int) $plan['quote_from_minor'])." + GST per {$unit}";
            } elseif (($plan['monthly_minor'] ?? null) === 0) {
                $parts[] = 'free';
            } else {
                if (isset($plan['monthly_minor'])) {
                    $parts[] = $this->rupees((int) $plan['monthly_minor'])." + GST per {$unit} per month";
                }
                if (isset($plan['annual_minor'])) {
                    $parts[] = $this->rupees((int) $plan['annual_minor'])." + GST per {$unit} per year";
                }
                if (isset($plan['minimum_units'])) {
                    $parts[] = 'minimum '.(int) $plan['minimum_units']." {$unit}s";
                }
            }

            if ($parts !== []) {
                $sentences[] = $this->text($plan['name'] ?? null).' - '.implode(', ', $parts);
            }
        }

        return $sentences;
    }

    /** Rupees from paise with Indian digit grouping, e.g. ₹1,49,900. */
    private function rupees(int $minor): string
    {
        $whole = (string) intdiv($minor, 100);
        $paise = $minor % 100;

        if (strlen($whole) > 3) {
            $head = preg_replace('/\B(?=(\d{2})+(?!\d))/', ',', substr($whole, 0, -3));
            $whole = $head.','.substr($whole, -3);
        }

        return '₹'.$whole.($paise === 0 ? '' : '.'.str_pad((string) $paise, 2, '0', STR_PAD_LEFT));
    }

    /** One line of plain text; anything else publishes nothing. */
    private function text(mixed $value): string
    {
        return is_string($value) ? trim((string) preg_replace('/\s+/u', ' ', $value)) : '';
    }
}
