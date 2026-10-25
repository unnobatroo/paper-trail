import type { Metadata } from "next";
import { Geist, Geist_Mono, Newsreader } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { TranslateProvider } from "@/components/en";
import { AppSidebar } from "@/components/app-sidebar";
import { CommandMenu } from "@/components/command-menu";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

// latin-ext carries ő and ű; with latin alone every Hungarian quote fell
// back to the system font mid-word
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin", "latin-ext"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin", "latin-ext"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin", "latin-ext"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "Paper Trail",
  description:
    "Check a municipality's climate promises against evidence from its own official sources.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${newsreader.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <Providers>
          <TranslateProvider>
            <SidebarProvider>
              <AppSidebar />
              <SidebarInset className="min-w-0 overflow-y-auto">
                <header className="flex items-center gap-2 border-b px-4 py-3 md:hidden">
                  <SidebarTrigger aria-label="Open navigation" />
                  <span className="font-heading text-base font-medium pencil-mark">Paper Trail</span>
                </header>
                {children}
              </SidebarInset>
              <CommandMenu />
            </SidebarProvider>
          </TranslateProvider>
        </Providers>
      </body>
    </html>
  );
}
