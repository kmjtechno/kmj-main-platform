<?php
namespace KMJ\MainPlatform\Catalog\Models;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
final class Plan extends Model {
 use HasUuids;
 protected $table="plans";
 protected $fillable=["product_id","code","name","pricing_model","billing_interval","currency","amount_minor","status","trial_days","features","limits"];
 protected function casts(): array { return ["amount_minor"=>"integer","trial_days"=>"integer","features"=>"array","limits"=>"array"]; }
}
