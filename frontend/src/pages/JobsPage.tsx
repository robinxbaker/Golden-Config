import {
  Box,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useJobs } from "../api/hooks";
import type { JobStatus } from "../api/types";

const STATUS_COLOR: Record<JobStatus, "default" | "info" | "success" | "error"> = {
  pending: "default",
  running: "info",
  succeeded: "success",
  failed: "error",
};

export function JobsPage() {
  const jobs = useJobs();

  return (
    <Box>
      <Typography variant="h5" mb={2}>
        Jobs
      </Typography>
      <Typography variant="body2" color="text.secondary" mb={2}>
        Backup and apply operations run asynchronously on the Celery worker. This list
        refreshes automatically.
      </Typography>

      <Paper>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(jobs.data ?? []).map((job) => (
              <TableRow key={job.id}>
                <TableCell>
                  <Chip size="small" label={job.type} />
                </TableCell>
                <TableCell>
                  <Chip size="small" color={STATUS_COLOR[job.status]} label={job.status} />
                </TableCell>
                <TableCell>{new Date(job.created_at).toLocaleString()}</TableCell>
                <TableCell sx={{ width: "50%" }}>
                  {(job.log || job.error) && (
                    <Accordion disableGutters elevation={0}>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="body2">
                          {job.error ? "Error" : "Output"}
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Box
                          component="pre"
                          sx={{
                            bgcolor: "#0d1117",
                            color: job.error ? "#ff7b72" : "#c9d1d9",
                            p: 1.5,
                            borderRadius: 1,
                            overflow: "auto",
                            fontSize: 12,
                            m: 0,
                          }}
                        >
                          {job.error || job.log}
                        </Box>
                      </AccordionDetails>
                    </Accordion>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {jobs.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={4}>
                  <Typography color="text.secondary" align="center" py={3}>
                    No jobs yet.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
