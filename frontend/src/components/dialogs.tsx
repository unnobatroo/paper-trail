import { useState } from "react"
import { useTheme } from "next-themes"
import { toast } from "sonner"

import { useAvailableDocuments, useMeta, useReviewActions } from "@/api/hooks"
import { SimpleSelect } from "@/components/simple-select"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { usePrefs } from "@/lib/prefs"

type DialogProps = { open: boolean; onOpenChange: (open: boolean) => void }

function Choice({ value, id, children }: { value: string; id: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <RadioGroupItem value={value} id={id} />
      <Label htmlFor={id}>{children}</Label>
    </div>
  )
}

/** Review key, reading language and colour scheme, all kept in this browser. */
export function SettingsDialog({ open, onOpenChange }: DialogProps) {
  const { lang, setLang, reviewKey, setReviewKey } = usePrefs()
  const { theme = "system", setTheme } = useTheme()
  const meta = useMeta()
  const [key, setKey] = useState(reviewKey)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>These stay in this browser only.</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5">
          {meta.data?.review_required && (
            <form
              className="flex flex-col gap-2"
              onSubmit={(e) => {
                e.preventDefault()
                setReviewKey(key.trim())
                toast.success(key.trim() ? "Review key saved" : "Review key cleared")
              }}
            >
              <Label htmlFor="review-key">Review key</Label>
              <p id="review-key-hint" className="type-secondary">
                This deployment requires a key to confirm or reject items.
              </p>
              <div className="flex gap-2">
                <Input
                  id="review-key"
                  type="password"
                  autoComplete="off"
                  aria-describedby="review-key-hint"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                />
                <Button type="submit">Save</Button>
              </div>
            </form>
          )}

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 type-body font-medium">Reading language</legend>
            <RadioGroup value={lang} onValueChange={(v) => setLang(v === "orig" ? "orig" : "en")}>
              <Choice value="en" id="lang-en">English reading aid, with the original underneath</Choice>
              <Choice value="orig" id="lang-orig">{meta.data?.language_name || "Original language"} only</Choice>
            </RadioGroup>
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 type-body font-medium">Colour scheme</legend>
            <RadioGroup value={theme} onValueChange={(v) => setTheme(String(v))}>
              <Choice value="system" id="theme-system">Follow my device</Choice>
              <Choice value="light" id="theme-light">Light</Choice>
              <Choice value="dark" id="theme-dark">Dark</Choice>
            </RadioGroup>
          </fieldset>
        </div>

        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  )
}

/** Pick a PDF from the document store and start reading it as a background job. */
export function IngestDialog({ open, onOpenChange }: DialogProps) {
  const available = useAvailableDocuments(open)
  const { ingest } = useReviewActions()
  const [name, setName] = useState("")
  const [title, setTitle] = useState("")
  const [publisher, setPublisher] = useState("")
  const [url, setUrl] = useState("")
  const names = available.data ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Read a strategy</DialogTitle>
          <DialogDescription>
            Paper Trail reads the PDF page by page and proposes commitments for you to confirm.
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            ingest.mutate(
              { name, title: title.trim(), publisher: publisher.trim(), url: url.trim() },
              {
                onSuccess: () => {
                  toast.success("Reading started. It can take a while; progress shows in the header.")
                  onOpenChange(false)
                },
              },
            )
          }}
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="doc-name">Document</Label>
            {names.length ? (
              <SimpleSelect label="Document" value={name} onChange={setName} options={names.map((n) => ({ value: n, label: n }))} />
            ) : (
              <Input id="doc-name" placeholder="filename.pdf" value={name} onChange={(e) => setName(e.target.value)} required />
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="doc-title">Title</Label>
            <Input id="doc-title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="doc-publisher">Publisher</Label>
            <Input id="doc-publisher" value={publisher} onChange={(e) => setPublisher(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="doc-url">Official URL (optional)</Label>
            <Input id="doc-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={ingest.isPending || !name || !title.trim()}>
              Start reading
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

const SHORTCUTS: [string, string][] = [
  ["j  k", "Next and previous commitment"],
  ["c", "Confirm the open commitment (To confirm)"],
  ["r", "Reject the open commitment (To confirm)"],
  ["x", "Select or unselect it for a bulk action"],
  ["s", "Find evidence for it (To search)"],
  ["/", "Go to the search box"],
  ["?", "Show this list"],
]

/** The keyboard shortcuts, because a shortcut nobody can find saves nobody any time. */
export function ShortcutsDialog({ open, onOpenChange }: DialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>They work when no dialog is open and you are not typing.</DialogDescription>
        </DialogHeader>
        <dl className="grid grid-cols-[5rem_1fr] items-center gap-x-3 gap-y-2 type-body">
          {SHORTCUTS.map(([keys, what]) => (
            <div key={keys} className="contents">
              <dt className="flex gap-1">
                {keys.split("  ").map((k) => (
                  <kbd key={k} className="layer-raised rounded-md px-2 py-0.5 type-num">
                    {k}
                  </kbd>
                ))}
              </dt>
              <dd>{what}</dd>
            </div>
          ))}
        </dl>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  )
}

/** The terms and codes used in the source documents, in plain words. */
export function GlossaryDialog({ open, onOpenChange }: DialogProps) {
  const meta = useMeta()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Glossary</DialogTitle>
          <DialogDescription>Words and codes you will meet in the strategy.</DialogDescription>
        </DialogHeader>
        <dl className="grid max-h-[60vh] grid-cols-[6rem_1fr] gap-x-3 gap-y-2 overflow-y-auto type-body">
          {meta.data?.glossary.map((g) => (
            <div key={g.term} className="contents">
              <dt className="font-mono">{g.term}</dt>
              <dd>{g.meaning}</dd>
            </div>
          ))}
        </dl>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  )
}
