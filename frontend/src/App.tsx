import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ThemeProvider } from "next-themes"
import { BrowserRouter, Route, Routes } from "react-router"
import { toast } from "sonner"

import { JobsWatcher } from "@/components/jobs-watcher"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { PrefsProvider } from "@/lib/prefs"
import { WorkspacePage } from "@/pages/workspace-page"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 5_000 },
    // Every failed review action surfaces the API's own message.
    mutations: { onError: (error) => toast.error(error.message) },
  },
})

/** Providers around the single page: theme, data cache, router, preferences and notifications. */
export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <PrefsProvider>
          <TooltipProvider>
            <BrowserRouter>
              <Routes>
                <Route path="*" element={<WorkspacePage />} />
              </Routes>
            </BrowserRouter>
            <JobsWatcher />
            <Toaster />
          </TooltipProvider>
        </PrefsProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
