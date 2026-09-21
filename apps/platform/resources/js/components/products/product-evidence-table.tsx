type EvidenceRow = {
    criterion: string;
    value: string;
    state: string;
    evidence_ref: string;
};

type TrustState = {
    purchase_boundary: string;
    demo_boundary: string;
    license_authority: string;
    production_signing: string;
};

export default function ProductEvidenceTable({
    evidence,
    trust,
}: {
    evidence: EvidenceRow[];
    trust: TrustState;
}) {
    return (
        <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.02]">
            <div className="border-b border-white/[0.07] px-5 py-4">
                <div className="text-xs font-bold tracking-[0.16em] text-white/45 uppercase">
                    Evidence-backed comparison
                </div>
                <p className="mt-2 text-sm leading-6 text-white/40">
                    Only repository or authority-backed facts are shown here.
                    No ratings, fabricated benchmarks or unsupported claims.
                </p>
            </div>

            <div className="divide-y divide-white/[0.06]">
                {evidence.map((row) => (
                    <div
                        key={row.criterion}
                        className="grid gap-2 px-5 py-4 sm:grid-cols-[10rem_1fr]"
                    >
                        <div className="text-xs font-bold tracking-[0.08em] text-white/42 uppercase">
                            {row.criterion}
                        </div>
                        <div>
                            <div className="text-sm font-semibold text-white/72">
                                {row.value}
                            </div>
                            <div className="mt-1 text-xs leading-5 text-white/32">
                                Evidence: {row.evidence_ref}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <div className="grid gap-3 border-t border-white/[0.07] bg-black/20 p-5 sm:grid-cols-2 lg:grid-cols-4">
                {[
                    ['Purchase', trust.purchase_boundary],
                    ['Demo', trust.demo_boundary],
                    ['License', trust.license_authority],
                    ['Signing', trust.production_signing],
                ].map(([label, value]) => (
                    <div
                        key={label}
                        className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3"
                    >
                        <div className="text-[10px] font-bold tracking-[0.12em] text-white/30 uppercase">
                            {label}
                        </div>
                        <div className="mt-2 text-xs font-semibold text-white/60">
                            {value}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
