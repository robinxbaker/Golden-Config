import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, tokenStore } from "../api/client";
import type { TokenPair, User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    if (!tokenStore.access) {
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get<User>("/auth/me");
      setUser(data);
    } catch {
      tokenStore.clear();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    const handler = () => logout();
    window.addEventListener("gc:logout", handler);
    return () => window.removeEventListener("gc:logout", handler);
  }, [logout]);

  const login = useCallback(async (username: string, password: string) => {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);
    const { data } = await api.post<TokenPair>("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    tokenStore.set(data);
    const me = await api.get<User>("/auth/me");
    setUser(me.data);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, logout }),
    [user, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
