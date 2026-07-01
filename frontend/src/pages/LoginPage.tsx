import { FormEvent, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ShieldIcon from "@mui/icons-material/Shield";
import { useAuth } from "../auth/AuthContext";
import { apiErrorMessage } from "../api/client";

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg,#1f6feb22,#f5b30122)",
      }}
    >
      <Card sx={{ width: 380 }} elevation={4}>
        <CardContent>
          <Stack alignItems="center" spacing={1} sx={{ mb: 2 }}>
            <ShieldIcon color="secondary" sx={{ fontSize: 48 }} />
            <Typography variant="h5">Golden Config</Typography>
            <Typography variant="body2" color="text.secondary">
              Sign in to manage device configurations
            </Typography>
          </Stack>
          <form onSubmit={handleSubmit}>
            <Stack spacing={2}>
              {error && <Alert severity="error">{error}</Alert>}
              <TextField
                label="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                fullWidth
              />
              <TextField
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                fullWidth
              />
              <Button type="submit" variant="contained" disabled={submitting} fullWidth>
                {submitting ? "Signing in…" : "Sign in"}
              </Button>
            </Stack>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
