import { createContext, useContext, useEffect, useState } from "react";
import { fetchCurrentUser, loginRequest, registerRequest } from "../api/auth";
import { TOKEN_KEY } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isGuest, setIsGuest] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time init, no token to check
      setLoading(false);
      return;
    }
    fetchCurrentUser()
      .then(setUser)
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const { access_token } = await loginRequest({ email, password });
    localStorage.setItem(TOKEN_KEY, access_token);
    const me = await fetchCurrentUser();
    setUser(me);
    setIsGuest(false);
    return me;
  }

  async function register(email, password, fullName) {
    await registerRequest({ email, password, fullName });
    return login(email, password);
  }

  function continueAsGuest() {
    setIsGuest(true);
    setUser(null);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setIsGuest(false);
  }

  const value = {
    user,
    isGuest,
    isAuthenticated: Boolean(user),
    loading,
    login,
    register,
    continueAsGuest,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- co-located hook is intentional here
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}