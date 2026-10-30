"use client";

import {CircleHelp} from "lucide-react";
import {Button} from "@/components/ui/button";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {PAGE_GUIDES} from "@/lib/labels";

export function PageTitle({
                              title,
                              hint,
                              guide,
                          }: {
    title: string;
    hint: string;
    guide?: keyof typeof PAGE_GUIDES | (keyof typeof PAGE_GUIDES)[];
}) {
    const keys = guide ? [guide].flat() : [];
    const terms = keys.flatMap((k) => PAGE_GUIDES[k].terms);
    const g = terms.length ? {terms} : null;
    return (
        <div className="flex items-start justify-between gap-4">
            <div>
                <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
                <p className="text-sm text-muted-foreground">{hint}</p>
            </div>
            {g && (
                <Popover>
                    <PopoverTrigger render={<Button variant="ghost" size="sm" className="gap-1.5"/>}>
                        <CircleHelp className="size-4"/>
                        Guide
                    </PopoverTrigger>
                    <PopoverContent className="w-80 space-y-3" align="end">
                        {g.terms.map(([term, def]) => (
                            <div key={term}>
                                <p className="text-sm font-medium">{term}</p>
                                <p className="text-sm text-muted-foreground">{def}</p>
                            </div>
                        ))}
                    </PopoverContent>
                </Popover>
            )}
        </div>
    );
}
