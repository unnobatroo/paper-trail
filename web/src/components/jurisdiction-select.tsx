"use client";

import {toast} from "sonner";
import {useMutation} from "@tanstack/react-query";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "@/components/ui/select";
import {api, type Commitment, errorMessage, type Jurisdiction} from "@/lib/api";
import {useInvalidateDomain} from "@/lib/hooks";
import {JURISDICTION_LABEL} from "@/lib/labels";

// who owns the asset = whose sites the evidence search covers
export function JurisdictionSelect({commitment}: { commitment: Commitment }) {
    const invalidate = useInvalidateDomain();
    const change = useMutation({
        mutationFn: (j: Jurisdiction) => api.setJurisdiction(commitment.id, j),
        onSuccess: () => {
            toast.success("Owner updated. The next evidence search covers their sites.");
            invalidate();
        },
        onError: (e) => toast.error(errorMessage(e)),
    });
    return (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Asset owner</span>
            <Select
                value={commitment.asset_owner_jurisdiction ?? "district_municipality"}
                onValueChange={(v) => change.mutate(v as Jurisdiction)}
                disabled={change.isPending}
            >
                <SelectTrigger size="sm" className="h-7 w-auto text-xs">
                    <SelectValue/>
                </SelectTrigger>
                <SelectContent>
                    {(Object.keys(JURISDICTION_LABEL) as Jurisdiction[]).map((j) => (
                        <SelectItem key={j} value={j}>{JURISDICTION_LABEL[j]}</SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}
