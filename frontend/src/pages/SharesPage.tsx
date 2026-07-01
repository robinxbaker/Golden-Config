import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import {
  useDecideShare,
  useIncomingShares,
  useOutgoingShares,
  useRequestShare,
} from "../api/hooks";
import { apiErrorMessage } from "../api/client";
import type { ShareStatus } from "../api/types";

const STATUS_COLOR: Record<ShareStatus, "default" | "success" | "error"> = {
  pending: "default",
  accepted: "success",
  denied: "error",
};

export function SharesPage() {
  const incoming = useIncomingShares();
  const outgoing = useOutgoingShares();
  const requestShare = useRequestShare();
  const decideShare = useDecideShare();

  const [configId, setConfigId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function submitRequest() {
    setError(null);
    setNotice(null);
    try {
      await requestShare.mutateAsync({
        config_file_id: configId.trim(),
        message: message || undefined,
      });
      setNotice("Request sent.");
      setConfigId("");
      setMessage("");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <Box>
      <Typography variant="h5" mb={2}>
        Shares
      </Typography>

      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" mb={1}>
            Request access to a config file
          </Typography>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Paste the ID of a config file owned by another user. They&apos;ll be able to accept
            or deny your request.
          </Typography>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              label="Config file ID"
              value={configId}
              onChange={(e) => setConfigId(e.target.value)}
              fullWidth
            />
            <TextField
              label="Message (optional)"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              fullWidth
            />
            <Button variant="contained" onClick={submitRequest} disabled={!configId.trim()}>
              Request
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Typography variant="h6" mb={1}>
            Incoming requests
          </Typography>
          <Divider sx={{ mb: 2 }} />
          {(incoming.data ?? []).length === 0 && (
            <Typography color="text.secondary">No incoming requests.</Typography>
          )}
          <Stack spacing={2}>
            {(incoming.data ?? []).map((req) => (
              <Card key={req.id} variant="outlined">
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Box>
                      <Typography variant="subtitle2">
                        {req.requester?.username ?? req.requester_id} wants access
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {req.message || "(no message)"}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Config: {req.config_file_id}
                      </Typography>
                    </Box>
                    {req.status === "pending" ? (
                      <Stack direction="row" spacing={1}>
                        <Button
                          size="small"
                          color="success"
                          variant="contained"
                          startIcon={<CheckIcon />}
                          onClick={() => decideShare.mutate({ id: req.id, accept: true })}
                        >
                          Accept
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          variant="outlined"
                          startIcon={<CloseIcon />}
                          onClick={() => decideShare.mutate({ id: req.id, accept: false })}
                        >
                          Deny
                        </Button>
                      </Stack>
                    ) : (
                      <Chip size="small" color={STATUS_COLOR[req.status]} label={req.status} />
                    )}
                  </Stack>
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Grid>

        <Grid item xs={12} md={6}>
          <Typography variant="h6" mb={1}>
            Your requests
          </Typography>
          <Divider sx={{ mb: 2 }} />
          {(outgoing.data ?? []).length === 0 && (
            <Typography color="text.secondary">You haven&apos;t requested anything.</Typography>
          )}
          <Stack spacing={2}>
            {(outgoing.data ?? []).map((req) => (
              <Card key={req.id} variant="outlined">
                <CardContent>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Config: {req.config_file_id}
                      </Typography>
                      <Typography variant="body2">{req.message || "(no message)"}</Typography>
                    </Box>
                    <Chip size="small" color={STATUS_COLOR[req.status]} label={req.status} />
                  </Stack>
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}
