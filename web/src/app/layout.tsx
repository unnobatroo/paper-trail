import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { TranslateProvider } from "@/components/en";
import { AppSidebar } from "@/components/app-sidebar";
import { CommandMenu } from "@/components/command-menu";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <Providers>
          <TranslateProvider>
            <SidebarProvider>
              <AppSidebar />
              <SidebarInset className="min-w-0 overflow-y-auto">
                <header className="flex items-center gap-2 border-b px-4 py-3 md:hidden">
                  <SidebarTrigger aria-label="Open navigation" />
                  <span className="text-sm font-semibold">Paper Trail</span>
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
