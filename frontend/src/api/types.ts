// Shared API types mirroring the backend Pydantic schemas.

export type UserRole = "admin" | "operator" | "viewer";
export type TransportType = "mock" | "real";
export type ConfigFormat = "cli" | "json" | "set";
export type JobType = "backup" | "apply";
export type JobStatus = "pending" | "running" | "succeeded" | "failed";
export type ShareStatus = "pending" | "accepted" | "denied";

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface UserPublic {
  id: string;
  username: string;
  full_name: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface DriverInfo {
  platform: string;
  display_name: string;
  vendor: string;
  transport_kind: string;
  default_port: number;
  config_format: ConfigFormat;
}

export interface Device {
  id: string;
  name: string;
  platform: string;
  vendor: string | null;
  model: string | null;
  host: string;
  port: number;
  transport: TransportType;
  username: string | null;
  has_secret: boolean;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface DeviceCreate {
  name: string;
  platform: string;
  vendor?: string;
  model?: string;
  host: string;
  port: number;
  transport: TransportType;
  username?: string;
  secret?: string;
}

export interface ConfigFileSummary {
  id: string;
  name: string;
  description: string | null;
  platform: string;
  format: ConfigFormat;
  version: number;
  owner_id: string;
  created_at: string;
}

export interface ConfigFile extends ConfigFileSummary {
  content: string;
  source_device_id: string | null;
  updated_at: string;
}

export interface ShareRequest {
  id: string;
  config_file_id: string;
  requester_id: string;
  owner_id: string;
  status: ShareStatus;
  message: string | null;
  responded_at: string | null;
  created_at: string;
  requester: UserPublic | null;
}

export interface Job {
  id: string;
  type: JobType;
  status: JobStatus;
  device_id: string;
  config_file_id: string | null;
  user_id: string;
  celery_task_id: string | null;
  log: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceConnectivity {
  reachable: boolean;
  detail: string;
}
