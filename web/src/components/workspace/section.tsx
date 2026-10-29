import type {LucideIcon} from "lucide-react";
import type {ReactNode} from "react";

// panel section: icon + title + count, so the long detail reads in clear blocks
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
        <section className="space-y-2.5 border-t pt-4 first:border-t-0 first:pt-0">
            <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                <Icon className="size-3.5"/>
                {title}
                {count != null && (
                    <span className="rounded-full bg-muted px-1.5 font-normal tabular-nums normal-case">{count}</span>
                )}
            </h3>
            {children}
        </section>
    );
}
