import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import NetworkCheckIcon from "@mui/icons-material/NetworkCheck";
import BackupIcon from "@mui/icons-material/Backup";
import UploadIcon from "@mui/icons-material/Upload";
import {
  useApplyJob,
  useBackupJob,
  useConfigs,
  useCreateDevice,
  useDeleteDevice,
  useDevices,
  useDrivers,
  useTestDevice,
} from "../api/hooks";
import type { Device, DeviceCreate } from "../api/types";
import { apiErrorMessage } from "../api/client";

const EMPTY_DEVICE: DeviceCreate = {
  name: "",
  platform: "",
  host: "",
  port: 22,
  transport: "mock",
  username: "",
  secret: "",
};

export function DevicesPage() {
  const devices = useDevices();
  const drivers = useDrivers();
  const configs = useConfigs();
  const createDevice = useCreateDevice();
  const deleteDevice = useDeleteDevice();
  const testDevice = useTestDevice();
  const backupJob = useBackupJob();
  const applyJob = useApplyJob();

  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState<DeviceCreate>(EMPTY_DEVICE);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [backupFor, setBackupFor] = useState<Device | null>(null);
  const [backupName, setBackupName] = useState("");

  const [applyFor, setApplyFor] = useState<Device | null>(null);
  const [applyConfigId, setApplyConfigId] = useState("");
  const [dryRun, setDryRun] = useState(true);

  const compatibleConfigs = useMemo(
    () => (applyFor ? (configs.data ?? []).filter((c) => c.platform === applyFor.platform) : []),
    [applyFor, configs.data],
  );

  async function submitCreate() {
    setError(null);
    try {
      await createDevice.mutateAsync({
        ...form,
        secret: form.secret || undefined,
        username: form.username || undefined,
      });
      setAddOpen(false);
      setForm(EMPTY_DEVICE);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function runTest(device: Device) {
    setNotice(null);
    setError(null);
    try {
      const result = await testDevice.mutateAsync(device.id);
      setNotice(`${device.name}: ${result.detail}`);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function submitBackup() {
    if (!backupFor) return;
    setError(null);
    try {
      await backupJob.mutateAsync({ device_id: backupFor.id, name: backupName });
      setNotice(`Backup started for ${backupFor.name}. Check the Jobs page.`);
      setBackupFor(null);
      setBackupName("");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function submitApply() {
    if (!applyFor || !applyConfigId) return;
    setError(null);
    try {
      await applyJob.mutateAsync({
        device_id: applyFor.id,
        config_file_id: applyConfigId,
        dry_run: dryRun,
      });
      setNotice(`Apply ${dryRun ? "(dry run) " : ""}started for ${applyFor.name}.`);
      setApplyFor(null);
      setApplyConfigId("");
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Devices</Typography>
        <Button startIcon={<AddIcon />} variant="contained" onClick={() => setAddOpen(true)}>
          Add Device
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert severity="info" sx={{ mb: 2 }} onClose={() => setNotice(null)}>{notice}</Alert>}

      <Paper>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Platform</TableCell>
              <TableCell>Host</TableCell>
              <TableCell>Transport</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(devices.data ?? []).map((device) => (
              <TableRow key={device.id} hover>
                <TableCell>{device.name}</TableCell>
                <TableCell>
                  <Chip size="small" label={device.platform} />
                </TableCell>
                <TableCell>
                  {device.host}:{device.port}
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={device.transport === "mock" ? "default" : "success"}
                    label={device.transport}
                  />
                </TableCell>
                <TableCell align="right">
                  <Tooltip title="Test connectivity">
                    <IconButton onClick={() => runTest(device)}>
                      <NetworkCheckIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Create config file from device">
                    <IconButton
                      color="primary"
                      onClick={() => {
                        setBackupFor(device);
                        setBackupName(`${device.name}-golden`);
                      }}
                    >
                      <BackupIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Apply a config to device">
                    <IconButton color="secondary" onClick={() => setApplyFor(device)}>
                      <UploadIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete device">
                    <IconButton color="error" onClick={() => deleteDevice.mutate(device.id)}>
                      <DeleteIcon />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
            {devices.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography color="text.secondary" align="center" py={3}>
                    No devices yet. Add one to get started.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>

      {/* Add device dialog */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Add Device</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField
              label="Name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              fullWidth
            />
            <TextField
              select
              label="Platform"
              value={form.platform}
              onChange={(e) => {
                const driver = drivers.data?.find((d) => d.platform === e.target.value);
                setForm({
                  ...form,
                  platform: e.target.value,
                  port: driver?.default_port ?? 22,
                });
              }}
              fullWidth
            >
              {(drivers.data ?? []).map((d) => (
                <MenuItem key={d.platform} value={d.platform}>
                  {d.display_name}
                </MenuItem>
              ))}
            </TextField>
            <Stack direction="row" spacing={2}>
              <TextField
                label="Host"
                value={form.host}
                onChange={(e) => setForm({ ...form, host: e.target.value })}
                fullWidth
              />
              <TextField
                label="Port"
                type="number"
                value={form.port}
                onChange={(e) => setForm({ ...form, port: Number(e.target.value) })}
                sx={{ width: 120 }}
              />
            </Stack>
            <Stack direction="row" spacing={2}>
              <TextField
                label="Username"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                fullWidth
              />
              <TextField
                label="Password / Token"
                type="password"
                value={form.secret}
                onChange={(e) => setForm({ ...form, secret: e.target.value })}
                fullWidth
              />
            </Stack>
            <TextField
              select
              label="Transport"
              value={form.transport}
              onChange={(e) =>
                setForm({ ...form, transport: e.target.value as DeviceCreate["transport"] })
              }
            >
              <MenuItem value="mock">mock (simulator, no hardware)</MenuItem>
              <MenuItem value="real">real (live SSH / REST)</MenuItem>
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={submitCreate}
            disabled={!form.name || !form.platform || !form.host}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Backup dialog */}
      <Dialog open={!!backupFor} onClose={() => setBackupFor(null)} fullWidth maxWidth="xs">
        <DialogTitle>Create Config File</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Capture the running configuration of <b>{backupFor?.name}</b> into a reusable
            config file.
          </Typography>
          <TextField
            label="Config file name"
            value={backupName}
            onChange={(e) => setBackupName(e.target.value)}
            fullWidth
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBackupFor(null)}>Cancel</Button>
          <Button variant="contained" onClick={submitBackup} disabled={!backupName}>
            Capture
          </Button>
        </DialogActions>
      </Dialog>

      {/* Apply dialog */}
      <Dialog open={!!applyFor} onClose={() => setApplyFor(null)} fullWidth maxWidth="xs">
        <DialogTitle>Apply Config</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Apply a <b>{applyFor?.platform}</b>-compatible config to <b>{applyFor?.name}</b>.
          </Typography>
          {compatibleConfigs.length === 0 ? (
            <Alert severity="warning">
              No compatible config files. Capture one first or get one shared with you.
            </Alert>
          ) : (
            <Stack spacing={2}>
              <TextField
                select
                label="Config file"
                value={applyConfigId}
                onChange={(e) => setApplyConfigId(e.target.value)}
                fullWidth
              >
                {compatibleConfigs.map((c) => (
                  <MenuItem key={c.id} value={c.id}>
                    {c.name} (v{c.version})
                  </MenuItem>
                ))}
              </TextField>
              <FormControlLabel
                control={<Switch checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />}
                label="Dry run (preview diff only)"
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setApplyFor(null)}>Cancel</Button>
          <Button variant="contained" onClick={submitApply} disabled={!applyConfigId}>
            Apply
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
