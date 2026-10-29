"use client";

import {useState} from "react";
import {toast} from "sonner";
import {KeyRound} from "lucide-react";
import {Button} from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger
} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {getReviewKey, setReviewKey} from "@/lib/api";

export function ReviewKeyDialog() {
    const [open, setOpen] = useState(false);
    const [value, setValue] = useState("");

    return (
        <Dialog
            open={open}
            onOpenChange={(o) => {
                setOpen(o);
                if (o) setValue(getReviewKey());
            }}
        >
            <DialogTrigger
                render={
                    <Button variant="ghost" size="sm" className="gap-1.5"/>
                }
            >
                <KeyRound className="size-4"/>
                Review key
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Review key</DialogTitle>
                    <DialogDescription>
                        This deployment requires a key to confirm or reject items. It
                        is stored only in this browser.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-1.5">
                    <Label htmlFor="review-key">Key</Label>
                    <Input
                        id="review-key"
                        type="password"
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                    />
                </div>
                <DialogFooter>
                    <Button
                        onClick={() => {
                            setReviewKey(value.trim());
                            setOpen(false);
                            toast.success(
                                value.trim() ? "Review key saved" : "Review key cleared",
                            );
                        }}
                    >
                        Save
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
