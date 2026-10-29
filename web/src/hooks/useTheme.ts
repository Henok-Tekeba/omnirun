import { useCallback, useEffect, useState } from "react";
import { loadTheme, saveTheme, type Theme } from "../lib/storage";

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => loadTheme() ?? "dark");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    saveTheme(theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  }, []);

  return { theme, setTheme, toggleTheme };
}
