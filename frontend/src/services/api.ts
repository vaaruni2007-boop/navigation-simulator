const API_BASE_URL = "http://127.0.0.1:8000";

export interface OptimizeRequest {
  station_id: string;
  resource_name: string;
  cargo_weight_tonnes: number;
  current_datetime: string;
  departure_dates: string[];
  safety_buffer_days: number;
  max_alternatives: number;
  inventory: {
    resource_name: string;
    current_quantity: number;
    unit: string;
    daily_consumption: number;
    minimum_safety_threshold: number;
    required_resupply_quantity: number;
  };
}

export interface VoyageOption {
  vessel_id: string;
  vessel_name: string;
  route_id: string;
  route_name: string;
  origin_port_id: string;
  origin_port_name: string;
  destination_station_id: string;
  destination_station_name: string;
  departure: string;
  arrival: string;
  distance_km: number;
  distance_nm: number;
  voyage_duration_days: number;
  fuel_required_litres: number;
  fuel_cost: number;
  operating_cost: number;
  total_cost: number;
  cost_per_tonne: number;
  safety_margin_days: number;
  feasible: boolean;
  rejection_reason: string | null;
}

export interface OptimizationResponse {
  status: string;
  message: string;
  recommended_option: VoyageOption;
  alternatives: VoyageOption[];
  infeasible_options: VoyageOption[];
}

export interface MissionCreateRequest {
  station_id: string;
  vessel_id: string;
  route_id: string;
  cargo_weight_tonnes: number;
  departure_datetime: string;
  safety_buffer_days: number;
}

export interface MissionUpdateRequest {
  elapsed_seconds: number;
}

export interface MissionState {
  status: string;

  simulation_datetime?: string;

  station: {
    id: string;
    name: string;
  };

  vessel: {
    id: string;
    name: string;
  };

  route: {
    id: string;
    name: string;
  };

  vessel_position?: {
    latitude: number;
    longitude: number;
  };

  vessel_progress: number;

  fuel_consumed_litres?: number;
  fuel_remaining_litres?: number;
  fuel_remaining_percent?: number;

  estimated_total_fuel_litres?: number;
  estimated_total_cost?: string | number;

  predicted_critical_date?: string;
  latest_safe_arrival?: string;
  estimated_arrival?: string;

  delay_days?: number;

  inventory?: Record<string, number>;

  environment?: {
    weather_severity: number;
    sea_ice_severity: number;
    current_factor: number;
    visibility_factor: number;
    overall_severity: number;
    active_event: string | null;
  };

  risk?: {
    overall_status: string;
    arrival_status: string;
    arrival_feasible: boolean;
    safety_margin_days: number;
    delay_days: number;
    estimated_arrival: string;
    latest_safe_arrival: string;
    predicted_critical_date: string;
    resources?: Record<
      string,
      {
        resource_name: string;
        current_quantity: number;
        daily_consumption: number;
        critical_date: string;
        latest_safe_arrival: string;
        status: string;
        days_until_critical: number;
      }
    >;
  };

  mission?: {
    cargo_weight_tonnes: number;
    departure_datetime: string;
    status: string;
  };

  progress_percent?: number;
}

export interface MissionResponse {
  status: string;
  message?: string;
  mission_id: string;
  mission: MissionState;
}

async function handleResponse<T>(
  response: Response,
  operation: string
): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text();

    throw new Error(
      `${operation} failed (${response.status}): ${errorText}`
    );
  }

  return response.json();
}

export async function optimizeResupply(
  request: OptimizeRequest
): Promise<OptimizationResponse> {
  const response = await fetch(`${API_BASE_URL}/api/optimize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  return handleResponse<OptimizationResponse>(
    response,
    "Optimization"
  );
}

export async function createMission(
  request: MissionCreateRequest
): Promise<MissionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/mission`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  return handleResponse<MissionResponse>(
    response,
    "Mission creation"
  );
}

export async function getMission(
  missionId: string
): Promise<MissionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/mission/${missionId}`
  );

  return handleResponse<MissionResponse>(
    response,
    "Mission fetch"
  );
}

export async function startMission(
  missionId: string
): Promise<MissionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/mission/${missionId}/start`,
    {
      method: "POST",
    }
  );

  return handleResponse<MissionResponse>(
    response,
    "Mission start"
  );
}

export async function updateMission(
  missionId: string,
  elapsedSeconds: number
): Promise<MissionResponse> {
  const request: MissionUpdateRequest = {
    elapsed_seconds: elapsedSeconds,
  };

  const response = await fetch(
    `${API_BASE_URL}/api/mission/${missionId}/update`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    }
  );

  return handleResponse<MissionResponse>(
    response,
    "Mission update"
  );
}

export async function pauseMission(
  missionId: string
): Promise<MissionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/mission/${missionId}/pause`,
    {
      method: "POST",
    }
  );

  return handleResponse<MissionResponse>(
    response,
    "Mission pause"
  );
}

export async function resumeMission(
  missionId: string
): Promise<MissionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/mission/${missionId}/resume`,
    {
      method: "POST",
    }
  );

  return handleResponse<MissionResponse>(
    response,
    "Mission resume"
  );
}