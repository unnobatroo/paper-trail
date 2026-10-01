"use client";

import { CircleHelp } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { PAGE_GUIDES } from "@/lib/labels";

export function PageHeader({
  title,
  guide,
}: {
  title: string;
  guide: keyof typeof PAGE_GUIDES;
}) {
  const g = PAGE_GUIDES[guide];
  return (
    <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{g.description}</p>
      </div>
      <Popover>
        <PopoverTrigger
          render={<Button variant="ghost" size="sm" className="gap-1.5" />}
        >
          <CircleHelp className="size-4" />
          Review guide
        </PopoverTrigger>
        <PopoverContent className="w-80 space-y-3" align="end">
          <p className="font-medium">How to read this view</p>
          {g.terms.map(([term, def]) => (
            <div key={term}>
              <p className="text-sm font-medium">{term}</p>
              <p className="text-sm text-muted-foreground">{def}</p>
            </div>
          ))}
        </PopoverContent>
      </Popover>
    </div>
  );
}
