import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./context/AuthContext";

import AuthPage from "./pages/AuthPage";
import ChatPage from "./pages/ChatPage";

import { Spinner } from "./components/ui/Spinner";


export default function App() {
  const {
    isAuthenticated,
    isGuest,
    loading,
  } = useAuth();


  if (loading) {
    return (
      <div
        className="
          flex
          h-screen
          items-center
          justify-center
          bg-paper-50
          text-brand-500
        "
      >
        <Spinner className="h-6 w-6" />
      </div>
    );
  }


  /*
   * IMPORTANT:
   *
   * Guests are allowed to return to /auth using
   * the browser Back button.
   *
   * Authenticated users are redirected to /chat
   * if they manually visit /auth.
   */
  const authRoute = isAuthenticated
    ? <Navigate to="/chat" replace />
    : <AuthPage />;


  /*
   * A user can enter the chat if they are either:
   *
   * 1. Authenticated
   * 2. Using guest mode
   */
  const canEnterChat =
    isAuthenticated || isGuest;


  return (
    <Routes>

      {/* =================================================
          AUTHENTICATION
          
          Guest users can return here using the browser
          Back button.
      ================================================= */}

      <Route
        path="/auth"
        element={authRoute}
      />


      {/* =================================================
          CHAT
      ================================================= */}

      <Route
        path="/chat"
        element={
          canEnterChat
            ? <ChatPage />
            : <Navigate
                to="/auth"
                replace
              />
        }
      />


      {/* =================================================
          DEFAULT
      ================================================= */}

      <Route
        path="*"
        element={
          <Navigate
            to="/auth"
            replace
          />
        }
      />

    </Routes>
  );
}