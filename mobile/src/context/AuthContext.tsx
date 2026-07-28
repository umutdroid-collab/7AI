import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import secureStorage from "../utils/secureStorage";
import Alert from "../utils/alert";
import { setOnUnauthorized, TOKEN_KEY } from "../api/client";
import { fetchMe, login as loginRequest } from "../api/services";
import { User } from "../types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const userRef = useRef<User | null>(null);
  userRef.current = user;

  useEffect(() => {
    setOnUnauthorized(() => {
      // Uygulama ilk açılırken süresi geçmiş eski bir token'la karşılaşılırsa
      // kullanıcı zaten giriş ekranını görecek; uyarıyı yalnızca aktif bir
      // oturum ortasında düşerse göster.
      const hadActiveSession = userRef.current !== null;
      setUser(null);
      if (hadActiveSession) {
        Alert.alert("Oturum süresi doldu", "Güvenliğiniz için oturumunuz kapatıldı. Lütfen tekrar giriş yapın.");
      }
    });
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
    <AuthContext.Provider value={{ user, isLoading, login, logout, updateUser: setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
