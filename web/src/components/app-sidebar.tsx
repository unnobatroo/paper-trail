"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { toast } from "sonner";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  FileCheck2,
  SearchCheck,
  Route,
  Languages,
  FileText,
  Loader2,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { ThemeToggle } from "./theme-toggle";
import {
  keys,
  useDocuments,
  useJobs,
  useMeta,
} from "@/lib/hooks";
import { useTranslate } from "./en";
import { useQueryClient } from "@tanstack/react-query";

const STEPS = [
  { href: "/commitments", label: "Check commitments", icon: FileCheck2, n: 1 },
  { href: "/evidence", label: "Find evidence", icon: SearchCheck, n: 2 },
  { href: "/trail", label: "Paper trail", icon: Route, n: 3 },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { setOpenMobile } = useSidebar();
  const qc = useQueryClient();
  const { data: meta, isError: metaError } = useMeta();
  const { data: documents } = useDocuments();
  const { on: translateOn, setOn: setTranslateOn } = useTranslate();
  const [jobIds, setJobIds] = useState<string[]>([]);
  const { jobs, settled } = useJobs(jobIds);

  const notifiedBatch = useRef<string>("");
  useEffect(() => {
    const batch = jobIds.join(",");
    if (!settled || notifiedBatch.current === batch) return;
    notifiedBatch.current = batch;
    qc.invalidateQueries({ queryKey: keys.documents });
    qc.invalidateQueries({ queryKey: keys.candidates });
    const failed = jobs.filter((j) => j.status === "failed");
    if (failed.length) {
      toast.error(`Ingest failed: ${failed[0].error ?? "unknown error"}`);
    } else {
      toast.success("Strategy read — review the commitments it produced.");
      jobs
        .flatMap((j) => j.result?.warnings ?? [])
        .forEach((w) => toast.warning(w));
    }
  }, [settled, jobs, jobIds, qc]);

  const hasDocs = (documents?.length ?? 0) > 0;

  return (
    <Sidebar>
      <SidebarHeader className="px-4 pt-4">
        <Link href="/" onClick={() => setOpenMobile(false)} className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-tight">
            Paper Trail
          </span>
          <Badge variant="outline" className="text-[10px]">
            Józsefváros
          </Badge>
        </Link>
        <p className="text-xs text-muted-foreground">
          Promise → evidence → status
        </p>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {STEPS.map(({ href, label, icon: Icon, n }) => (
                <SidebarMenuItem key={href}>
                  <SidebarMenuButton
                    isActive={pathname.startsWith(href)}
                    render={<Link href={href} onClick={() => setOpenMobile(false)} />}
                  >
                    <span className="flex size-5 shrink-0 items-center justify-center rounded-full border text-[10px]">
                      {n}
                    </span>
                    <Icon className="size-4" />
                    <span>{label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="gap-3 px-4 pb-4">
        {jobs
          .filter((j) => j.status === "queued" || j.status === "running")
          .map((j) => (
            <div
              key={j.id}
              className="rounded-md border bg-background p-3 text-xs"
            >
              <div className="flex items-center gap-2 font-medium">
                <Loader2 className="size-3 animate-spin" />
                Reading strategy…
              </div>
              {j.progress && (
                <p className="mt-1 text-muted-foreground">{j.progress}</p>
              )}
            </div>
          ))}

        {!hasDocs && documents !== undefined && (
          <IngestCard onJob={setJobIds} />
        )}

        <Button
          variant={translateOn ? "secondary" : "outline"}
          size="sm"
          className="w-full justify-start gap-2"
          disabled={!meta?.translation}
          onClick={() => setTranslateOn(!translateOn)}
        >
          <Languages className="size-4" />
          {translateOn ? "Hide English" : "Show English"}
        </Button>
        <ThemeToggle />
        <p className="text-[10px] text-muted-foreground">
          Press <kbd className="rounded border px-1">⌘K</kbd> for the command
          menu · <kbd className="rounded border px-1">j</kbd>/<kbd className="rounded border px-1">k</kbd> navigate queues
        </p>
        {meta && !meta.translation && (
          <p className="text-[10px] text-muted-foreground">
            English translation is unavailable.
          </p>
        )}

        <SidebarSeparator />
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <FileText className="size-3" />
          {meta
            ? `${documents?.length ?? 0} document(s) · ${meta.storage} · ${meta.search_provider}`
            : metaError
              ? "API unreachable"
              : "connecting…"}
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

const ingestSchema = z.object({
  name: z.string().min(1, "Pick a document"),
  title: z.string().min(1, "Title required"),
  publisher: z.string(),
  url: z.string().optional(),
});
type IngestValues = z.infer<typeof ingestSchema>;

function IngestCard({ onJob }: { onJob: (ids: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const { data: names } = useQuery({
    queryKey: keys.availableDocs,
    queryFn: api.availableDocuments,
    enabled: open,
  });

  const form = useForm<IngestValues>({
    resolver: zodResolver(ingestSchema),
    defaultValues: {
      name: "",
      title: "Józsefváros Climate Strategy 2021",
      publisher: "Józsefváros Municipality",
      url: "",
    },
  });

  const mutation = useMutation({
    mutationFn: (v: IngestValues) =>
      api.ingest({
        name: v.name,
        title: v.title,
        publisher: v.publisher,
        url: v.url || undefined,
      }),
    onSuccess: (job) => {
      setOpen(false);
      onJob([job.id]);
    },
    onError: (e) =>
      toast.error(`Ingest failed: ${e instanceof Error ? e.message : e}`),
  });

  const name = useWatch({ control: form.control, name: "name" });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" className="w-full gap-2" />}>
        <FileText className="size-4" />
        Read the strategy
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ingest a source document</DialogTitle>
          <DialogDescription>
            Reads a PDF from the document store and extracts candidate
            commitments for review. Runs as a background job — nothing is
            confirmed automatically.
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
        >
          <div className="space-y-1.5">
            <Label>Document</Label>
            {names && names.length > 0 ? (
              <Select
                value={name}
                onValueChange={(v) => form.setValue("name", v as string)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose a file" />
                </SelectTrigger>
                <SelectContent>
                  {names.map((n) => (
                    <SelectItem key={n} value={n}>
                      {n}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input
                {...form.register("name")}
                placeholder="filename.pdf"
              />
            )}
          </div>
          <div className="space-y-1.5">
            <Label>Title</Label>
            <Input {...form.register("title")} />
          </div>
          <div className="space-y-1.5">
            <Label>Publisher</Label>
            <Input {...form.register("publisher")} />
          </div>
          <div className="space-y-1.5">
            <Label>Official URL (optional)</Label>
            <Input {...form.register("url")} placeholder="https://…" />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={mutation.isPending || !name}>
              {mutation.isPending && (
                <Loader2 className="mr-2 size-4 animate-spin" />
              )}
              Start reading
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
