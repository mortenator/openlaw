import type { Metadata } from "next"
import "./globals.css"
import { ThemeProvider } from "@/lib/theme"

export const metadata: Metadata = {
  title: "OpenLaw",
  description: "AI chief of staff for deal lawyers",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const saved = localStorage.getItem("ol-theme");
                const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
                document.documentElement.setAttribute("data-theme", saved || preferred);
              } catch(e) {}
            `,
          }}
        />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  )
}
