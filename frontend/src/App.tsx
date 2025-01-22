import { Route, Routes, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/toaster";
import { Layout } from "@/components/layout/Layout";
import Dashboard from "@/pages/Dashboard";
import DashboardLayout from "@/components/DashboardLayout";
import Settings from "@/pages/Settings";
import WhiteLabel from "@/pages/WhiteLabel";
import CreateWhiteLabel from "@/pages/CreateWhiteLabel";
import { NotFound } from "@/pages/NotFound";
import SyncCreate from "@/pages/SyncCreate";
import SyncTableView from "@/pages/SyncTableView";
import ViewEditSync from "@/pages/ViewEditSync";
import ViewEditWhiteLabelSync from "@/pages/ViewEditWhiteLabelSync";
import Destinations from "@/pages/Destinations";
import Profile from "@/pages/Profile";
import Chat from "@/pages/Chat";
import Index from "@/pages/Index";
import Sources from "@/pages/Sources";
import { AuthCallback } from "./pages/AuthCallback";
import ViewEditWhiteLabel from "./pages/ViewEditWhiteLabel";
import Login from "./pages/Login";

// Simple auth check for demo purposes
const RequireAuth = ({ children }: { children: JSX.Element }) => {
  const isAuthenticated = !!localStorage.getItem("user");
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Index />} />
          <Route path="login" element={<Login />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        <Route element={
          <RequireAuth>
            <DashboardLayout />
          </RequireAuth>
        }>
          <Route path="/dashboard" element={<Dashboard />} />
          
          {/* Configure section routes */}
          <Route path="/sync">
            <Route index element={<SyncTableView />} />
            <Route path="create" element={<SyncCreate />} />
            <Route path="white-label/:id" element={<ViewEditWhiteLabelSync />} />
            <Route path=":id" element={<ViewEditSync />} />
          </Route>

          <Route path="/sources" element={<Sources />} />
          <Route path="/destinations" element={<Destinations />} />
          
          <Route path="/white-label">
            <Route index element={<WhiteLabel />} />
            <Route path="create" element={<CreateWhiteLabel />} />
            <Route path=":id" element={<ViewEditWhiteLabel />} />
          </Route>

          {/* Settings and Profile routes */}
          <Route path="/settings" element={<Settings />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/chat" element={<Chat />} />
        </Route>

        <Route path="/auth/callback/:short_name" element={<AuthCallback />} />
      </Routes>
      <Toaster />
    </>
  );
}

export default App;