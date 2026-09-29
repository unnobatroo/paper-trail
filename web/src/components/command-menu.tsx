"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  FileCheck2,
  SearchCheck,
  Route,
  LayoutDashboard,
  Moon,
  Sun,
  Languages,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useTranslate } from "./en";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/commitments", label: "Check commitments", icon: FileCheck2 },
  { href: "/evidence", label: "Find evidence", icon: SearchCheck },
  { href: "/trail", label: "Paper trail", icon: Route },
];

export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const { on: translateOn, setOn: setTranslateOn } = useTranslate();

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
      <CommandInput placeholder="Go to…" />
      <CommandList>
        <CommandEmpty>Nothing found.</CommandEmpty>
        <CommandGroup heading="Steps">
          {NAV.map(({ href, label, icon: Icon }) => (
            <CommandItem key={href} onSelect={() => go(href)}>
              <Icon className="size-4" />
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
              <Sun className="size-4" />
            ) : (
              <Moon className="size-4" />
            )}
            Toggle theme
          </CommandItem>
          <CommandItem
            onSelect={() => {
              setTranslateOn(!translateOn);
              setOpen(false);
            }}
          >
            <Languages className="size-4" />
            {translateOn ? "Hide" : "Show"} English translation
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
