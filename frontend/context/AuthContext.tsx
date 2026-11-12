"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { logoutSession, refreshAccessToken, setAccessTokenUpdater } from "../lib/api";

type AuthContextValue = {
  accessToken: string | null;
  signIn: (token: string) => void;
  signOut: () => void;
  isAuthReady: boolean;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isAuthReady, setIsAuthReady] = useState(false);
  useEffect(() => {
    setAccessTokenUpdater(setAccessToken);
    refreshAccessToken().then((token) => setAccessToken((current) => current ?? token)).finally(() => setIsAuthReady(true));
    return () => setAccessTokenUpdater(null);
  }, []);
  const signIn = useCallback((token: string) => setAccessToken(token), []);
  const signOut = useCallback(() => {
    setAccessToken(null);
    void logoutSession().catch(() => undefined);
  }, []);
  const value = useMemo(
    () => ({
      accessToken,
      signIn,
      signOut,
      isAuthReady,
    }),
    [accessToken, isAuthReady, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
