// TanStack Query hooks wrapping the REST API.
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "./client";
import type {
  ConfigFile,
  ConfigFileSummary,
  Device,
  DeviceConnectivity,
  DeviceCreate,
  DriverInfo,
  Job,
  ShareRequest,
  User,
  UserPublic,
} from "./types";

// ---- Drivers ----
export function useDrivers() {
  return useQuery({
    queryKey: ["drivers"],
    queryFn: async () => (await api.get<DriverInfo[]>("/drivers")).data,
    staleTime: 1000 * 60 * 60,
  });
}

// ---- Current user ----
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => (await api.get<User>("/auth/me")).data,
  });
}

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get<UserPublic[]>("/users")).data,
  });
}

// ---- Devices ----
export function useDevices() {
  return useQuery({
    queryKey: ["devices"],
    queryFn: async () => (await api.get<Device[]>("/devices")).data,
  });
}

export function useCreateDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: DeviceCreate) =>
      (await api.post<Device>("/devices", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useDeleteDevice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/devices/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
}

export function useTestDevice() {
  return useMutation({
    mutationFn: async (id: string) =>
      (await api.post<DeviceConnectivity>(`/devices/${id}/test`)).data,
  });
}

// ---- Config files ----
export function useConfigs() {
  return useQuery({
    queryKey: ["configs"],
    queryFn: async () => (await api.get<ConfigFileSummary[]>("/configs")).data,
  });
}

export function useConfig(id: string | null) {
  return useQuery({
    queryKey: ["config", id],
    enabled: !!id,
    queryFn: async () => (await api.get<ConfigFile>(`/configs/${id}`)).data,
  });
}

export function useDeleteConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => api.delete(`/configs/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["configs"] }),
  });
}

// ---- Jobs ----
export function useJobs(pollMs = 4000) {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: async () => (await api.get<Job[]>("/jobs")).data,
    refetchInterval: pollMs,
  });
}

export function useBackupJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { device_id: string; name: string; description?: string }) =>
      (await api.post<Job>("/jobs/backup", payload)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["configs"] });
    },
  });
}

export function useApplyJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      device_id: string;
      config_file_id: string;
      dry_run: boolean;
    }) => (await api.post<Job>("/jobs/apply", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

// ---- Shares ----
export function useIncomingShares() {
  return useQuery({
    queryKey: ["shares", "incoming"],
    queryFn: async () => (await api.get<ShareRequest[]>("/shares/incoming")).data,
  });
}

export function useOutgoingShares() {
  return useQuery({
    queryKey: ["shares", "outgoing"],
    queryFn: async () => (await api.get<ShareRequest[]>("/shares/outgoing")).data,
  });
}

export function useRequestShare() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { config_file_id: string; message?: string }) =>
      (await api.post<ShareRequest>("/shares", payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shares", "outgoing"] }),
  });
}

export function useDecideShare() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, accept }: { id: string; accept: boolean }) =>
      (await api.post<ShareRequest>(`/shares/${id}/decision`, { accept })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shares", "incoming"] });
      qc.invalidateQueries({ queryKey: ["configs"] });
    },
  });
}
