import React, { createContext, useContext, useEffect, useState } from "react";
import secureStorage from "../utils/secureStorage";
import { TOKEN_KEY } from "../api/client";
import { fetchMe, login as loginRequest } from "../api/services";
import { User } from "../types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await secureStorage.getItemAsync(TOKEN_KEY);
      if (token) {
        try {
          const me = await fetchMe();
          setUser(me);
        } catch {
          await secureStorage.deleteItemAsync(TOKEN_KEY);
        }
      }
      setIsLoading(false);
    })();
  }, []);

  async function login(email: string, password: string) {
    const result = await loginRequest(email, password);
    await secureStorage.setItemAsync(TOKEN_KEY, result.access_token);
    setUser(result.user);
  }

  async function logout() {
    await secureStorage.deleteItemAsync(TOKEN_KEY);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
