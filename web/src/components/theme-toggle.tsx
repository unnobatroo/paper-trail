"use client";

import {useTheme} from "next-themes";
import {Moon, Sun} from "lucide-react";
import {Button} from "@/components/ui/button";

// icon swaps in css (next-themes sets .dark before paint),
// so server + client markup match and nothing flashes
export function ThemeToggle() {
    const {resolvedTheme, setTheme} = useTheme();
    return (
        <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Toggle theme"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
            <Moon className="size-4 dark:hidden"/>
            <Sun className="hidden size-4 dark:block"/>
        </Button>
    );
}
