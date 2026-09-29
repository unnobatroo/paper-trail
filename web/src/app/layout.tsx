import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { TranslateProvider } from "@/components/en";
import { AppSidebar } from "@/components/app-sidebar";
import { CommandMenu } from "@/components/command-menu";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

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
              <SidebarInset className="overflow-y-auto">
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
