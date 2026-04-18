import React, { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "./store/authStore";
import Layout from "./components/Layout";
import { ToastContainer } from "./components/Toast";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/HomePage";
import StatisticsPage from "./pages/StatisticsPage";
import FormFlowPage from "./pages/FormFlowPage";
import ReportsExportPage from "./pages/ReportsExportPage";
import ChatRoomsPage from "./pages/ChatRoomsPage";
import ReportsFeedPage from "./pages/ReportsFeedPage";
import JoinPlaceholderPage from "./pages/JoinPlaceholderPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuthStore();
  if (isLoading) return <div className="flex items-center justify-center h-screen"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-700" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <div className="flex items-center justify-center h-screen text-red-600">Доступ только для администраторов</div>;
  return <>{children}</>;
}

export default function App() {
  const loadUser = useAuthStore((s) => s.loadUser);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <BrowserRouter>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/join/:token" element={<JoinPlaceholderPage />} />
        <Route
          path="/*"
          element={
            <RequireAuth>
              <Layout>
                <Routes>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/statistics" element={<StatisticsPage />} />
                  <Route path="/dictionaries" element={<FormFlowPage />} />
                  <Route path="/reports" element={<ReportsExportPage />} />
                  <Route path="/export" element={<Navigate to="/reports?tab=export" replace />} />
                  <Route path="/chat" element={<ChatRoomsPage />} />
                  <Route path="/feed" element={<ReportsFeedPage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
