import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import VisibilityIcon from "@mui/icons-material/Visibility";
import DownloadIcon from "@mui/icons-material/Download";
import { useConfig, useConfigs, useDeleteConfig } from "../api/hooks";
import { useMe } from "../api/hooks";
import { api } from "../api/client";

export function ConfigsPage() {
  const configs = useConfigs();
  const me = useMe();
  const deleteConfig = useDeleteConfig();
  const [viewId, setViewId] = useState<string | null>(null);
  const viewed = useConfig(viewId);

  async function download(id: string, name: string) {
    const res = await api.get(`/configs/${id}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Box>
      <Typography variant="h5" mb={2}>
        Config Files
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        Config files you own plus any that have been shared with you. Capture new ones from the
        Devices page.
      </Alert>

      <Paper>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Platform</TableCell>
              <TableCell>Format</TableCell>
              <TableCell>Version</TableCell>
              <TableCell>Owner</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(configs.data ?? []).map((c) => {
              const owned = c.owner_id === me.data?.id;
              return (
                <TableRow key={c.id} hover>
                  <TableCell>{c.name}</TableCell>
                  <TableCell>
                    <Chip size="small" label={c.platform} />
                  </TableCell>
                  <TableCell>{c.format}</TableCell>
                  <TableCell>v{c.version}</TableCell>
                  <TableCell>
                    {owned ? <Chip size="small" color="primary" label="you" /> : "shared"}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="View">
                      <IconButton onClick={() => setViewId(c.id)}>
                        <VisibilityIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Download">
                      <IconButton onClick={() => download(c.id, `${c.name}.txt`)}>
                        <DownloadIcon />
                      </IconButton>
                    </Tooltip>
                    {owned && (
                      <Tooltip title="Delete">
                        <IconButton color="error" onClick={() => deleteConfig.mutate(c.id)}>
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            {configs.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={6}>
                  <Typography color="text.secondary" align="center" py={3}>
                    No config files yet.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>

      <Dialog open={!!viewId} onClose={() => setViewId(null)} fullWidth maxWidth="md">
        <DialogTitle>{viewed.data?.name}</DialogTitle>
        <DialogContent dividers>
          <Stack direction="row" spacing={1} mb={2}>
            <Chip size="small" label={viewed.data?.platform} />
            <Chip size="small" label={viewed.data?.format} />
            <Chip size="small" label={`v${viewed.data?.version ?? ""}`} />
          </Stack>
          <Box
            component="pre"
            sx={{
              bgcolor: "#0d1117",
              color: "#c9d1d9",
              p: 2,
              borderRadius: 1,
              overflow: "auto",
              fontSize: 13,
              maxHeight: 480,
            }}
          >
            {viewed.isLoading ? "Loading…" : viewed.data?.content}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setViewId(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
