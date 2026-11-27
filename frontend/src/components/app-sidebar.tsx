import {
  BanIcon,
  BookOpenIcon,
  CircleCheckIcon,
  ClipboardCheckIcon,
  InboxIcon,
  ListIcon,
  SearchIcon,
  Settings2Icon,
  UploadIcon,
  type LucideIcon,
} from "lucide-react"

import { useMeta } from "@/api/hooks"
import { ToneBadge } from "@/components/tone-badge"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { useCanReview } from "@/lib/can-review"
import { STAGES, STAGE_INFO, type Stage } from "@/lib/labels"

const ICONS: Record<Stage | "all", LucideIcon> = {
  all: ListIcon,
  confirm: ClipboardCheckIcon,
  search: SearchIcon,
  review: InboxIcon,
  done: CircleCheckIcon,
  rejected: BanIcon,
}

type Props = {
  stage: string
  counts: Record<string, number>
  ingesting: boolean
  onStage: (stage: string) => void
  onIngest: () => void
  onGlossary: () => void
  onSettings: () => void
}

/** Navigation by review stage, with a count for each, and the app-level actions at the bottom. */
export function AppSidebar({ stage, counts, ingesting, onStage, onIngest, onGlossary, onSettings }: Props) {
  const meta = useMeta()
  const canReview = useCanReview()
  const all = Object.entries(counts).reduce((n, [s, c]) => n + (s === "rejected" ? 0 : c), 0)
  const items: { id: Stage | "all"; label: string; hint: string; count: number }[] = [
    { id: "all", label: "All", hint: "Everything except rejected", count: all },
    ...STAGES.map((s) => ({ id: s, label: STAGE_INFO[s].label, hint: STAGE_INFO[s].hint, count: counts[s] ?? 0 })),
  ]

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1.5">
          <span className="text-lg font-semibold group-data-[collapsible=icon]:hidden">Paper Trail</span>
          {meta.data?.deployment && (
            <ToneBadge className="group-data-[collapsible=icon]:hidden">{meta.data.deployment}</ToneBadge>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Review stages</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map(({ id, label, hint, count }) => {
                const Icon = ICONS[id]
                return (
                  <SidebarMenuItem key={id}>
                    <SidebarMenuButton isActive={stage === id} tooltip={hint} onClick={() => onStage(id)}>
                      <Icon />
                      <span>{label}</span>
                    </SidebarMenuButton>
                    <SidebarMenuBadge>{count}</SidebarMenuBadge>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Read a strategy PDF" onClick={onIngest} disabled={!canReview || ingesting}>
              <UploadIcon />
              <span>{ingesting ? "Reading…" : "Ingest"}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          {meta.data && meta.data.glossary.length > 0 && (
            <SidebarMenuItem>
              <SidebarMenuButton tooltip="Terms and codes" onClick={onGlossary}>
                <BookOpenIcon />
                <span>Glossary</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}
          <SidebarMenuItem>
            <SidebarMenuButton tooltip="Review key, language, colour scheme" onClick={onSettings}>
              <Settings2Icon />
              <span>Settings</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
