import type {LucideIcon} from "lucide-react";
import type {ReactNode} from "react";
import {Badge} from "@/components/ui/badge";
import {Separator} from "@/components/ui/separator";

// panel section: icon + title + count, keeps the long detail readable
export function Section({
                            icon: Icon,
                            title,
                            count,
                            children,
                        }: {
    icon: LucideIcon;
    title: string;
    count?: number;
    children: ReactNode;
}) {
    return (
        <section className="group/section space-y-2.5 pt-4 first:pt-0">
            <Separator className="mb-4 group-first/section:hidden"/>
            <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                <Icon className="size-3.5"/>
                {title}
                {count != null && (
                    <Badge variant="secondary" className="h-auto px-1.5 py-0 font-normal tabular-nums normal-case">
                        {count}
                    </Badge>
                )}
            </h3>
            {children}
        </section>
    );
}
