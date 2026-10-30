"use client";

import {CircleAlert} from "lucide-react";
import {Alert, AlertAction, AlertDescription, AlertTitle} from "@/components/ui/alert";
import {Button} from "@/components/ui/button";

export function QueryError({error, retry}: { error: Error; retry: () => unknown }) {
    return (
        <Alert variant="destructive" className="my-4">
            <CircleAlert/>
            <AlertTitle>Could not load this view</AlertTitle>
            <AlertDescription>{error.message}</AlertDescription>
            <AlertAction>
                <Button size="sm" variant="outline" onClick={() => retry()}>Try again</Button>
            </AlertAction>
        </Alert>
    );
}
