import { Navigate, Route, Routes } from "react-router-dom";
import { CircularProgress, Box } from "@mui/material";
import { useAuth } from "./auth/AuthContext";
import { AppLayout } from "./components/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { DevicesPage } from "./pages/DevicesPage";
import { ConfigsPage } from "./pages/ConfigsPage";
import { JobsPage } from "./pages/JobsPage";
import { SharesPage } from "./pages/SharesPage";

function FullScreenLoader() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
      <CircularProgress />
    </Box>
  );
}

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <FullScreenLoader />;

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <AppLayout>
      <Routes>
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/configs" element={<ConfigsPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/shares" element={<SharesPage />} />
        <Route path="*" element={<Navigate to="/devices" replace />} />
      </Routes>
    </AppLayout>
  );
}
