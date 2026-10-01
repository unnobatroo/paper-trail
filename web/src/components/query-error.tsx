"use client";

import { Button } from "@/components/ui/button";

export function QueryError({ error, retry }: { error: Error; retry: () => unknown }) {
  return (
    <div role="alert" className="my-4 rounded-md border border-destructive/30 p-4 text-sm">
      <p className="font-medium">Could not load this view</p>
      <p className="mt-1 text-muted-foreground">{error.message}</p>
      <Button className="mt-3" size="sm" variant="outline" onClick={() => retry()}>Try again</Button>
    </div>
  );
}
