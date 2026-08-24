export type StatusState = "ready" | "not_configured" | "degraded" | "unavailable";

export interface Category {
  name: string;
  code: string;
  tone: string;
}

export interface Forecast {
  horizon_hours: number;
  valid_time: string;
  vmax_kt: number;
  change_kt: number;
  lower_kt: number;
  upper_kt: number;
  persistence_kt: number;
  historical_reference_kt: number | null;
}

export interface TrackPoint {
  valid_time: string;
  vmax_kt: number;
  latitude: number;
  longitude: number;
  category: Category;
  satellites: string[];
  source_count: number;
  eye_signal: number | null;
  quality: { status: string; reason_codes: string[]; coverage: number };
  motion: { speed_kmh: number; bearing_degrees: number; direction: string };
  change_12h_kt: number | null;
  change_24h_kt: number | null;
  trend_kt_per_hour: number;
  ri: {
    probability: number;
    threshold: number;
    definition_id: string;
    definition: string;
    alert_eligible: boolean;
    method: string;
  };
  forecasts: Forecast[];
}

export interface ImageryKeyframe {
  valid_time: string;
  url: string;
  label: string;
  source: string;
  embedded_wind_kt: number;
}

export interface Alert {
  alert_id: string;
  type: string;
  severity: string;
  status: string;
  storm_id: string;
  storm_name: string;
  valid_time: string;
  probability: number;
  threshold: number;
  definition: string;
  method: string;
  review?: {
    action: string;
    reason: string | null;
    reviewer: string;
    reviewed_at: string;
  };
}

export interface Storm {
  storm_id: string;
  sid: string;
  name: string;
  basin: string;
  mode: string;
  status: string;
  category_profile_id: string;
  first_valid_time: string;
  last_valid_time: string;
  peak: { vmax_kt: number; valid_time: string; category: Category };
  track: TrackPoint[];
  observation_count: number;
  source_row_count: number;
  satellites: string[];
  alerts: Alert[];
  imagery_keyframes: ImageryKeyframe[];
}

export interface SystemStatus {
  environment: string;
  mode: string;
  release: string;
  overall_status: string;
  disclaimer: string;
  dataset: {
    storm_count: number;
    observation_count: number;
    source_row_count: number;
    satellites: string[];
    index_path: string;
    category_profile_id: string;
  };
  model: {
    id: string;
    status: string;
    task: string;
    sha256: string | null;
    source_repository: string;
    training_dataset: string;
    runtime: string;
    validation_status: string;
    replaceable_via: string;
    load_error: string | null;
  };
  sources: Array<{
    id: string;
    name: string;
    status: StatusState;
    mode: string;
    detail: string;
  }>;
  capabilities: Array<{
    id: string;
    name: string;
    status: StatusState;
    qualification?: string;
  }>;
}

export interface UploadResult {
  analysis_id: string;
  mode: string;
  status: string;
  filename: string;
  size_bytes: number;
  dimensions: { width: number; height: number };
  quality: { status: string; reason_codes: string[] };
  result: {
    vmax_kt: number;
    raw_model_output_kt: number;
    lower_kt: number | null;
    upper_kt: number | null;
    confidence: number | null;
    uncertainty_status: string;
    category: Category;
    pattern: string;
    metrics: Record<string, number>;
    method: {
      id: string;
      type: string;
      trained_model: boolean;
      replaceable: boolean;
      validation_status: string;
      limitations: string[];
    };
  };
  disclaimer: string;
}

export type ViewName = "overview" | "comparison" | "analysis" | "data";
