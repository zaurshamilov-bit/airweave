import { Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/toaster";
import Dashboard from "@/pages/Dashboard";
import DashboardLayout from "@/components/DashboardLayout";
import WhiteLabel from "@/pages/WhiteLabel";
import CreateWhiteLabel from "@/pages/CreateWhiteLabel";
import { NotFound } from "@/pages/NotFound";
import SyncTableView from "@/pages/SyncTableView";
import Destinations from "@/pages/Destinations";
import Profile from "@/pages/Profile";
import Chat from "@/pages/Chat";
import { AuthCallback } from "./pages/AuthCallback";
import ViewEditWhiteLabel from "./pages/ViewEditWhiteLabel";
import { LoginPage } from "./pages/LoginPage";
import { CallbackPage } from "./pages/CallbackPage";
import { AuthGuard } from "./components/AuthGuard";
import CollectionsView from "./pages/CollectionsView";
import CollectionDetailView from "./pages/CollectionDetailView";
import { CollectionsProvider } from "./lib/collectionsContext";

function App() {
  return (
    <CollectionsProvider>
      <Routes>
        <Route
          element={
            <AuthGuard>
              <DashboardLayout />
            </AuthGuard>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />

          <Route path="/sync">
            <Route index element={<SyncTableView />} />
          </Route>

          <Route path="/api-keys" />

          <Route path="/destinations" element={<Destinations />} />

          <Route path="/white-label">
            <Route index element={<WhiteLabel />} />
            <Route path="create" element={<CreateWhiteLabel />} />
            <Route path=":id" element={<ViewEditWhiteLabel />} />
          </Route>

          <Route path="/profile" element={<Profile />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/chat/:id" element={<Chat />} />
          <Route path="/collections" element={<CollectionsView />} />
          <Route path="/collections/:readable_id" element={<CollectionDetailView />} />
        </Route>

        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/callback" element={<CallbackPage />} />
        <Route path="/auth/callback/:short_name" element={<AuthCallback />} />

        {/* 404 route */}
        <Route path="*" element={<NotFound />} />
      </Routes>
      <Toaster />
    </CollectionsProvider>
  );
}

export default App;
