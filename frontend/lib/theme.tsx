"use client"
import { createContext, useContext, useEffect, useState, ReactNode } from "react"

type Theme = "light" | "dark"
const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({ theme: "light", toggle: () => {} })

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light")

  useEffect(() => {
    const saved = localStorage.getItem("ol-theme") as Theme | null
    const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
    const initial = saved || preferred
    setTheme(initial)
    document.documentElement.setAttribute("data-theme", initial)
  }, [])

  function toggle() {
    setTheme(prev => {
      const next = prev === "light" ? "dark" : "light"
      localStorage.setItem("ol-theme", next)
      document.documentElement.setAttribute("data-theme", next)
      return next
    })
  }

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>
}

export const useTheme = () => useContext(ThemeContext)
