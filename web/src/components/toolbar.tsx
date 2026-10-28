"use client";

import type { ReactNode } from "react";
import { CircleHelp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { PAGE_GUIDES } from "@/lib/labels";

export function PageTitle({
  title,
  hint,
  guide,
}: {
  title: string;
  hint: string;
  guide?: keyof typeof PAGE_GUIDES;
}) {
  const g = guide ? PAGE_GUIDES[guide] : null;
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">{hint}</p>
      </div>
      {g && (
        <Popover>
          <PopoverTrigger render={<Button variant="ghost" size="sm" className="gap-1.5" />}>
            <CircleHelp className="size-4" />
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

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="mt-4 mb-3 flex flex-wrap items-center gap-2">{children}</div>;
}
