<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('operator_action_audits', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('actor_user_id');
            $table->string('action', 80);
            $table->string('outcome', 24);
            $table->json('metadata')->nullable();
            $table->timestamps();

            $table->foreign('actor_user_id')->references('id')->on('users')->restrictOnDelete();
            $table->index(['action', 'created_at']);
            $table->index(['actor_user_id', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('operator_action_audits');
    }
};
