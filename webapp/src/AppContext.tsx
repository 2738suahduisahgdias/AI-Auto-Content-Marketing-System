import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, errorText } from "@/lib/api";
import type { AppResources } from "@/lib/types";

interface AppContextValue {
  resources: AppResources | null;
  loading: boolean;
  loadError: string;
  notice: { text: string; error: boolean } | null;
  refresh: () => Promise<void>;
  run: <T>(action: () => Promise<T>, success?: string, reload?: boolean) => Promise<T | null>;
  notify: (message: string, error?: boolean) => void;
}
const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [resources, setResources] = useState<AppResources | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState<AppContextValue["notice"]>(null);
  const notify = useCallback((text: string, error = false) => {
    setNotice({ text, error });
    window.setTimeout(() => setNotice(current => current?.text === text ? null : current), error ? 12000 : 4000);
  }, []);
  const refresh = useCallback(async () => {
    try {
      const [core, topics, agents, accounts, articles, knowledge] = await Promise.all([
        api("/api/bootstrap"), api("/api/topics/bootstrap"), api("/api/agents/config"),
        api("/api/accounts/bootstrap"), api("/api/articles/bootstrap"), api("/api/knowledge/bootstrap"),
      ]);
      setResources({ core, topics, agents, accounts, articles, knowledge });
      setLoadError("");
    } catch (error) { setLoadError(errorText(error)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);
  const run = useCallback(async <T,>(action: () => Promise<T>, success?: string, reload = true): Promise<T | null> => {
    try {
      const result = await action();
      if (reload) await refresh();
      if (success) notify(success);
      return result;
    } catch (error) { notify(errorText(error), true); return null; }
  }, [notify, refresh]);
  const value = useMemo(() => ({ resources, loading, loadError, notice, refresh, run, notify }), [resources, loading, loadError, notice, refresh, run, notify]);
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp must be used inside AppProvider");
  return value;
}
