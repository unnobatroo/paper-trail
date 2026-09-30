"use client";

/** Review-key entry — the API gates mutating endpoints behind a bearer
 *  key when PAPER_TRAIL_API_KEY is set. Enter it once per tab; it's
 *  stored in sessionStorage and sent with every request. */

import { useState } from "react";
import { Lock, LockOpen } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { clearReviewKey, getReviewKey, setReviewKey } from "@/lib/api";

export function ReviewKey() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [hasKey, setHasKey] = useState(() => Boolean(getReviewKey()));

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button
            variant={hasKey ? "secondary" : "outline"}
            size="sm"
            className="w-full justify-start gap-2"
          />
        }
      >
        {hasKey ? (
          <LockOpen className="size-4" />
        ) : (
          <Lock className="size-4" />
        )}
        {hasKey ? "Review key set" : "Unlock reviewing"}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Review key</DialogTitle>
          <DialogDescription>
            Confirming and rejecting work needs the review key — it keeps
            the record human-only on a public deployment. Reads stay open
            either way. The key lives in this tab&apos;s session storage.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!value.trim()) return;
            setReviewKey(value.trim());
            setHasKey(true);
            setOpen(false);
            toast.success("Review key saved for this tab.");
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="review-key">Key</Label>
            <Input
              id="review-key"
              type="password"
              autoComplete="off"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="paste the review key"
            />
          </div>
          <DialogFooter className="gap-2">
            {hasKey && (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  clearReviewKey();
                  setHasKey(false);
                  setValue("");
                  setOpen(false);
                  toast.info("Review key cleared.");
                }}
              >
                Clear key
              </Button>
            )}
            <Button type="submit" disabled={!value.trim()}>
              Save key
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
