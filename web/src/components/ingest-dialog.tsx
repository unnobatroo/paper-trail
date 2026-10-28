"use client";

import { useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import { keys } from "@/lib/hooks";

const ingestSchema = z.object({
  name: z.string().min(1, "Pick a document"),
  title: z.string().min(1, "Title required"),
  publisher: z.string(),
  url: z.string().optional(),
});
type IngestValues = z.infer<typeof ingestSchema>;

export function IngestDialog({ onJob }: { onJob: (ids: string[]) => void }) {
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
      title: "",
      publisher: "",
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
      <DialogTrigger render={<Button size="sm" variant="outline" className="gap-1.5" />}>
        <FileText className="size-4" />
        Ingest
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
