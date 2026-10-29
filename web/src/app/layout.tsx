import type {Metadata} from "next";
import {Geist, Geist_Mono} from "next/font/google";
import "./globals.css";
import {Providers} from "@/components/providers";
import {TranslateProvider} from "@/components/en";
import {TopNav} from "@/components/top-nav";
import {CommandMenu} from "@/components/command-menu";

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

export const metadata: Metadata = {
    title: "Paper Trail",
    description:
        "Check a municipality's climate promises against evidence from its own official sources.",
};

export default function RootLayout({children}: LayoutProps<"/">) {
    return (
        <html
            lang="en"
            suppressHydrationWarning
            className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
        >
        <body className="min-h-full">
        <Providers>
            <TranslateProvider>
                <TopNav/>
                <main className="mx-auto w-full max-w-[1400px] px-4 py-5">
                    {children}
                </main>
                <CommandMenu/>
            </TranslateProvider>
        </Providers>
        </body>
        </html>
    );
}
