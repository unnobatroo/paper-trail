"use client";

import {useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import {useTheme} from "next-themes";
import {FileCheck2, Languages, LayoutDashboard, ListChecks, Moon, Route, SearchCheck, Sun,} from "lucide-react";
import {
    CommandDialog,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/command";
import {useLang} from "./en";

const NAV = [
    {href: "/", label: "Workspace: everything", icon: LayoutDashboard},
    {href: "/?stage=confirm", label: "To confirm", icon: FileCheck2},
    {href: "/?stage=search", label: "To search", icon: SearchCheck},
    {href: "/?stage=review", label: "To review", icon: ListChecks},
    {href: "/?stage=done", label: "Done", icon: Route},
];

export function CommandMenu() {
    const [open, setOpen] = useState(false);
    const router = useRouter();
    const {resolvedTheme, setTheme} = useTheme();
    const {lang, setLang} = useLang();

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                setOpen((o) => !o);
            }
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, []);

    const go = (href: string) => {
        setOpen(false);
        router.push(href);
    };

    return (
        <CommandDialog open={open} onOpenChange={setOpen}>
            <CommandInput placeholder="Go to…"/>
            <CommandList>
                <CommandEmpty>Nothing found.</CommandEmpty>
                <CommandGroup heading="Steps">
                    {NAV.map(({href, label, icon: Icon}) => (
                        <CommandItem key={href} onSelect={() => go(href)}>
                            <Icon className="size-4"/>
                            {label}
                        </CommandItem>
                    ))}
                </CommandGroup>
                <CommandGroup heading="View">
                    <CommandItem
                        onSelect={() => {
                            setTheme(resolvedTheme === "dark" ? "light" : "dark");
                            setOpen(false);
                        }}
                    >
                        {resolvedTheme === "dark" ? (
                            <Sun className="size-4"/>
                        ) : (
                            <Moon className="size-4"/>
                        )}
                        Toggle theme
                    </CommandItem>
                    <CommandItem
                        onSelect={() => {
                            setLang(lang === "en" ? "orig" : "en");
                            setOpen(false);
                        }}
                    >
                        <Languages className="size-4"/>
                        Show {lang === "en" ? "original language" : "English"}
                    </CommandItem>
                </CommandGroup>
            </CommandList>
        </CommandDialog>
    );
}
