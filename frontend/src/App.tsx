import { useEffect, useMemo, useState } from "react";
import "./App.css";

import MapView from "./components/MapView";

import {
  optimizeResupply,
  createMission,
  startMission,
  updateMission,
  pauseMission,
  resumeMission,
  type OptimizationResponse,
  type MissionState,
} from "./services/api";

import { SIMULATED_ROUTES } from "./types/routes";

function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] =
    useState<OptimizationResponse | null>(null);

  const [missionId, setMissionId] = useState<string | null>(null);
  const [mission, setMission] =
    useState<MissionState | null>(null);

  const [simulationSpeed, setSimulationSpeed] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const plan = result?.recommended_option;

  const selectedRoute = useMemo(() => {
    if (
      plan &&
      SIMULATED_ROUTES[plan.route_id]
    ) {
      return SIMULATED_ROUTES[plan.route_id];
    }

    return SIMULATED_ROUTES.R001;
  }, [plan]);

  /*
   * ---------------------------------------------------------
   * OPTIMIZATION
   * ---------------------------------------------------------
   */

  async function handleOptimize() {
    setLoading(true);
    setError(null);

    try {
      const response = await optimizeResupply({
        station_id: "MAITRI",
        resource_name: "diesel",
        cargo_weight_tonnes: 1500,
        current_datetime: "2026-10-01T00:00:00+00:00",
        departure_dates: [
          "2026-11-15T00:00:00+00:00",
          "2026-12-01T00:00:00+00:00",
          "2026-12-15T00:00:00+00:00",
          "2027-01-01T00:00:00+00:00",
        ],
        safety_buffer_days: 3,
        max_alternatives: 3,
        inventory: {
          resource_name: "diesel",
          current_quantity: 300000,
          unit: "litres",
          daily_consumption: 1800,
          minimum_safety_threshold: 25000,
          required_resupply_quantity: 60000,
        },
      });

      setResult(response);

      setMissionId(null);
      setMission(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to contact optimization engine."
      );
    } finally {
      setLoading(false);
    }
  }

  /*
   * ---------------------------------------------------------
   * MISSION CREATION + START
   * ---------------------------------------------------------
   */

  async function handleStartMission() {
    if (!plan) {
      setError("Run the optimizer before starting a mission.");
      return;
    }

    setError(null);

    try {
      let activeMissionId = missionId;

      if (!activeMissionId) {
        const created = await createMission({
          station_id: plan.destination_station_id,
          vessel_id: plan.vessel_id,
          route_id: plan.route_id,
          cargo_weight_tonnes: 1500,
          departure_datetime: plan.departure,
          safety_buffer_days: 3,
        });

        activeMissionId = created.mission_id;

        setMissionId(activeMissionId);
        setMission(created.mission);
      }

      const started = await startMission(activeMissionId);

      setMission(started.mission);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to start mission."
      );
    }
  }

  /*
   * ---------------------------------------------------------
   * PAUSE
   * ---------------------------------------------------------
   */

  async function handlePauseMission() {
    if (!missionId) {
      return;
    }

    setError(null);

    try {
      const response = await pauseMission(missionId);
      setMission(response.mission);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to pause mission."
      );
    }
  }

  /*
   * ---------------------------------------------------------
   * RESUME
   * ---------------------------------------------------------
   */

  async function handleResumeMission() {
    if (!missionId) {
      return;
    }

    setError(null);

    try {
      const response = await resumeMission(missionId);
      setMission(response.mission);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to resume mission."
      );
    }
  }

  /*
   * ---------------------------------------------------------
   * RESET
   * ---------------------------------------------------------
   */

  function handleResetMission() {
    setMissionId(null);
    setMission(null);
    setError(null);
  }

  /*
   * ---------------------------------------------------------
   * SIMULATION CLOCK
   * ---------------------------------------------------------
   */

  useEffect(() => {
    if (!missionId || !mission) {
      return;
    }

    const status = mission.status.toUpperCase();

    if (
      status !== "RUNNING" &&
      status !== "ACTIVE"
    ) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const elapsedSeconds =
          60 * 60 * simulationSpeed;

        const response = await updateMission(
          missionId,
          elapsedSeconds
        );

        setMission(response.mission);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Simulation update failed."
        );
      }
    }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [missionId, mission, simulationSpeed]);

  /*
   * ---------------------------------------------------------
   * DISPLAY VALUES
   * ---------------------------------------------------------
   */

  const progress =
    mission?.vessel_progress ?? 0;

  const vesselPosition =
    mission?.vessel_position;

  const fuelRemaining =
    mission?.fuel_remaining_percent ?? 100;

  const environment =
    mission?.environment;

  const risk =
    mission?.risk;

  const missionStatus =
    mission?.status?.toUpperCase() ?? "PLANNED";

  const isRunning =
    missionStatus === "RUNNING" ||
    missionStatus === "ACTIVE";

  const isPaused =
    missionStatus === "PAUSED";

  const isComplete =
    missionStatus === "COMPLETED" ||
    missionStatus === "ARRIVED";

  /*
   * ---------------------------------------------------------
   * ENVIRONMENT ANALYSIS
   * ---------------------------------------------------------
   */

  const environmentAnalysis =
    getEnvironmentAnalysis(environment);

  const environmentClass =
    environmentAnalysis.level;

  /*
   * Approximate operational impact calculated from
   * the same environment model used by the simulator.
   *
   * These are visualization values, while the backend
   * remains authoritative for actual ETA/fuel state.
   */

  const weatherSeverity =
    environment?.weather_severity ?? 0;

  const seaIceSeverity =
    environment?.sea_ice_severity ?? 0;

  const visibility =
    environment?.visibility_factor ?? 1;

  const currentFactor =
    environment?.current_factor ?? 1;

  const speedImpact =
    Math.max(
      25,
      Math.round(
        (1 -
          0.35 * weatherSeverity -
          0.4 * seaIceSeverity -
          0.15 * (1 - visibility)) *
          currentFactor *
          100
      )
    );

  const fuelImpact =
    Math.round(
      (
        1 +
        0.3 * weatherSeverity +
        0.4 * seaIceSeverity +
        0.1 * (1 - visibility)
      ) * 100
    );

  return (
    <div className="app">

      {/* =====================================================
          HEADER
      ====================================================== */}

      <header className="topbar">
        <div>
          <div className="eyebrow">
            INDIAN ANTARCTIC PROGRAMME
          </div>

          <h1>
            ANTARCTIC RESUPPLY COMMAND
          </h1>
        </div>

        <div className="system-status">
          <span className="status-dot"></span>
          SYSTEM ONLINE
        </div>
      </header>


      {/* =====================================================
          ENVIRONMENT ALERT
      ====================================================== */}

      {mission && environmentAnalysis.level !== "normal" && (
        <div
          className={`environment-alert ${environmentAnalysis.level}`}
        >
          <div className="alert-icon">
            {environmentAnalysis.icon}
          </div>

          <div className="alert-content">
            <strong>
              {environmentAnalysis.title}
            </strong>

            <span>
              {environmentAnalysis.description}
            </span>
          </div>

          <div className="alert-impact">
            <span>
              SPEED {speedImpact}%
            </span>

            <span>
              FUEL +{fuelImpact - 100}%
            </span>

            <span>
              DELAY +
              {(mission.delay_days ?? 0).toFixed(1)}D
            </span>
          </div>
        </div>
      )}


      {/* =====================================================
          MAIN DASHBOARD
      ====================================================== */}

      <main className="dashboard">

        {/* ===================================================
            LEFT COLUMN
        ==================================================== */}

        <section className="left-column">

          {/* STATION */}

          <div className="panel station-panel">

            <div className="panel-header">

              <div>
                <span className="label">
                  DESTINATION STATION
                </span>

                <h2>MAITRI</h2>
              </div>

              <select defaultValue="MAITRI">
                <option value="MAITRI">
                  Maitri
                </option>

                <option value="BHARATI">
                  Bharati
                </option>
              </select>

            </div>

            <div className="station-location">
              Queen Maud Land · Antarctica
            </div>

            <div className="station-status">
              <span className="status-dot"></span>
              OPERATIONAL
            </div>

          </div>


          {/* INVENTORY */}

          <div className="panel">

            <div className="panel-title">
              <span>STATION INVENTORY</span>

              <span className="muted">
                LIVE MODEL
              </span>
            </div>

            <div className="inventory-main">

              <div>
                <span className="label">
                  DIESEL
                </span>

                <strong>
                  {mission?.inventory?.diesel
                    ? Math.round(
                        mission.inventory.diesel
                      ).toLocaleString()
                    : "300,000"}
                </strong>

                <span className="unit">
                  LITRES
                </span>
              </div>

              <div className="inventory-indicator">

                <div className="inventory-bar">
                  <div
                    className="inventory-fill"
                    style={{
                      width: `${Math.max(
                        0,
                        Math.min(
                          100,
                          ((mission?.inventory
                            ?.diesel ?? 300000) /
                            300000) *
                            100
                        )
                      )}%`,
                    }}
                  />
                </div>

                <span>
                  {risk?.resources?.diesel?.status ??
                    "SAFE"}
                </span>

              </div>

            </div>

            <div className="inventory-details">

              <div>
                <span>
                  Daily consumption
                </span>

                <strong>
                  1,800 L
                </strong>
              </div>

              <div>
                <span>
                  Safety threshold
                </span>

                <strong>
                  25,000 L
                </strong>
              </div>

              <div>
                <span>
                  Predicted critical date
                </span>

                <strong>
                  {mission?.predicted_critical_date
                    ? formatDate(
                        mission.predicted_critical_date
                      )
                    : "02 MAY 2027"}
                </strong>
              </div>

            </div>

          </div>


          {/* RESUPPLY */}

          <div className="panel resupply-panel">

            <div className="panel-title">

              <span>
                RESUPPLY REQUIREMENT
              </span>

              <span className="warning-tag">
                PLANNING
              </span>

            </div>

            <div className="resupply-number">
              1,500 <span>TONNES</span>
            </div>

            <p>
              Recommended cargo quantity based on
              current inventory, predicted consumption
              and station safety requirements.
            </p>

            <button
              className="primary-button"
              onClick={handleOptimize}
              disabled={loading}
            >
              {loading
                ? "RUNNING OPTIMIZER..."
                : "OPTIMIZE RESUPPLY"}

              <span>
                {loading ? "◌" : "→"}
              </span>
            </button>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            {result && !error && (
              <div className="success-message">
                OPTIMIZATION COMPLETE
              </div>
            )}

          </div>


          {/* =================================================
              MISSION CONTROL
          ================================================== */}

          <div className="panel mission-control-panel">

            <div className="panel-title">

              <span>
                MISSION CONTROL
              </span>

              <span
                className={
                  isComplete
                    ? "recommended"
                    : isRunning
                    ? "live-tag"
                    : isPaused
                    ? "warning-tag"
                    : "muted"
                }
              >
                {isComplete
                  ? "ARRIVED"
                  : isRunning
                  ? "RUNNING"
                  : isPaused
                  ? "PAUSED"
                  : "READY"}
              </span>

            </div>

            <div className="mission-vessel">

              <span className="label">
                ACTIVE VESSEL
              </span>

              <h2>
                {mission?.vessel?.name ??
                  plan?.vessel_name ??
                  "SWIFT ARCTIC"}
              </h2>

              <span className="vessel-type">
                {mission?.vessel?.id ??
                  plan?.vessel_id ??
                  "V001"}
                {" · "}
                SIMULATED VESSEL
              </span>

            </div>


            {/* PROGRESS */}

            <div className="mission-progress">

              <div className="progress-labels">

                <span>
                  {mission?.route?.name
                    ? mission.route.name
                    : "MUMBAI → MAITRI"}
                </span>

                <strong>
                  {progress.toFixed(1)}%
                </strong>

              </div>

              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{
                    width: `${progress}%`,
                  }}
                />
              </div>

            </div>


            {/* CONTROLS */}

            <div className="mission-buttons">

              <button
                className="mission-button primary"
                onClick={handleStartMission}
                disabled={
                  isRunning ||
                  isComplete ||
                  loading
                }
              >
                ▶ START
              </button>

              <button
                className="mission-button"
                onClick={handlePauseMission}
                disabled={!isRunning}
              >
                ⏸ PAUSE
              </button>

              <button
                className="mission-button"
                onClick={handleResumeMission}
                disabled={!isPaused}
              >
                ▶ RESUME
              </button>

              <button
                className="mission-button"
                onClick={handleResetMission}
              >
                ↻ RESET
              </button>

            </div>


            {/* SPEED */}

            <div className="simulation-speed">

              <span className="label">
                SIMULATION SPEED
              </span>

              <div className="speed-buttons">

                {[1, 5, 10].map((speed) => (
                  <button
                    key={speed}
                    className={
                      simulationSpeed === speed
                        ? "speed-button active"
                        : "speed-button"
                    }
                    onClick={() =>
                      setSimulationSpeed(speed)
                    }
                  >
                    {speed}×
                  </button>
                ))}

              </div>

            </div>


            {/* LIVE METRICS */}

            <div className="mission-metrics">

              <div>
                <span>PROGRESS</span>

                <strong>
                  {progress.toFixed(1)}%
                </strong>
              </div>

              <div>
                <span>FUEL REMAINING</span>

                <strong>
                  {fuelRemaining.toFixed(1)}%
                </strong>
              </div>

              <div>
                <span>ETA</span>

                <strong>
                  {mission?.estimated_arrival
                    ? formatDate(
                        mission.estimated_arrival
                      )
                    : plan
                    ? formatDate(plan.arrival)
                    : "19 DEC 2026"}
                </strong>
              </div>

              <div>
                <span>DELAY</span>

                <strong
                  className={
                    (mission?.delay_days ?? 0) > 0
                      ? "delay-text"
                      : ""
                  }
                >
                  {(mission?.delay_days ?? 0).toFixed(
                    1
                  )}{" "}
                  DAYS
                </strong>
              </div>

            </div>


            {/* POSITION */}

            <div className="position-display">

              <span className="label">
                CURRENT POSITION
              </span>

              <strong>
                {vesselPosition
                  ? `${vesselPosition.latitude.toFixed(
                      2
                    )}°, ${vesselPosition.longitude.toFixed(
                      2
                    )}°`
                  : "18.97°, 72.83°"}
              </strong>

            </div>

          </div>

        </section>


        {/* ===================================================
            MAP
        ==================================================== */}

        <section className="map-panel">

          <MapView
            waypoints={selectedRoute}
            vesselProgress={progress}
            vesselName={
              mission?.vessel?.name ??
              plan?.vessel_name ??
              "Swift Arctic"
            }
            vesselPosition={
              mission?.vessel_position
            }
          />

          <div className="map-overlay top-left">

            <span className="label">
              MARITIME ROUTE SIMULATION
            </span>

            <strong>
              {plan
                ? `${plan.origin_port_name.toUpperCase()} → ${plan.destination_station_name.toUpperCase()}`
                : "MUMBAI → MAITRI"}
            </strong>

          </div>

          <div className="map-info">

            <div>
              <span>DISTANCE</span>

              <strong>
                {plan
                  ? `${plan.distance_km.toLocaleString()} km`
                  : "14,500 km"}
              </strong>
            </div>

            <div>
              <span>ROUTE RISK</span>

              <strong
                className={
                  environmentClass === "danger"
                    ? "danger-text"
                    : environmentClass === "warning"
                    ? "warning-text"
                    : "safe-text"
                }
              >
                {risk?.overall_status ??
                  "LOW"}
              </strong>
            </div>

            <div>
              <span>ROUTE TYPE</span>

              <strong>
                {plan
                  ? plan.route_name
                      .replace(
                        "Mumbai-Maitri ",
                        ""
                      )
                      .toUpperCase()
                  : "DIRECT"}
              </strong>
            </div>

          </div>

          <div className="map-badge">
            SIMULATED MARITIME CORRIDOR
          </div>

        </section>


        {/* ===================================================
            RIGHT COLUMN
        ==================================================== */}

        <section className="right-column">

          {/* OPTIMAL PLAN */}

          <div className="panel optimal-panel">

            <div className="panel-title">

              <span>
                OPTIMAL RESUPPLY PLAN
              </span>

              <span className="recommended">
                {plan
                  ? "OPTIMIZED"
                  : "AWAITING INPUT"}
              </span>

            </div>

            <div className="vessel-name">

              <span className="label">
                VESSEL
              </span>

              <h2>
                {plan?.vessel_name ??
                  "SWIFT ARCTIC"}
              </h2>

              <span className="vessel-type">
                {plan
                  ? `${plan.vessel_id} · OPTIMAL SELECTION`
                  : "CONTAINER SHIP · V001"}
              </span>

            </div>

            <div className="route-summary">

              <div>

                <span>
                  {plan?.origin_port_name ??
                    "MUMBAI"}
                </span>

                <div className="route-arrow">
                  →
                </div>

                <span>
                  {plan?.destination_station_name ??
                    "MAITRI"}
                </span>

              </div>

            </div>

            <div className="metric-grid">

              <div className="metric">

                <span>
                  DEPARTURE
                </span>

                <strong>
                  {plan
                    ? formatDate(plan.departure)
                    : "01 DEC 2026"}
                </strong>

              </div>

              <div className="metric">

                <span>
                  EST. ARRIVAL
                </span>

                <strong>
                  {mission?.estimated_arrival
                    ? formatDate(
                        mission.estimated_arrival
                      )
                    : plan
                    ? formatDate(plan.arrival)
                    : "19 DEC 2026"}
                </strong>

              </div>

              <div className="metric">

                <span>
                  VOYAGE
                </span>

                <strong>
                  {plan
                    ? `${plan.voyage_duration_days.toFixed(
                        1
                      )} DAYS`
                    : "18.1 DAYS"}
                </strong>

              </div>

              <div className="metric">

                <span>
                  SAFETY MARGIN
                </span>

                <strong
                  className={
                    risk &&
                    risk.safety_margin_days < 30
                      ? "warning-text"
                      : "safe-text"
                  }
                >
                  {mission?.risk
                    ? `${mission.risk.safety_margin_days.toFixed(
                        1
                      )} DAYS`
                    : plan
                    ? `${plan.safety_margin_days.toFixed(
                        1
                      )} DAYS`
                    : "70.7 DAYS"}
                </strong>

              </div>

            </div>

            <div className="cost-section">

              <div>

                <span>
                  FUEL REQUIRED
                </span>

                <strong>
                  {mission?.estimated_total_fuel_litres
                    ? `${Math.round(
                        mission.estimated_total_fuel_litres
                      ).toLocaleString()} L`
                    : plan
                    ? `${Math.round(
                        plan.fuel_required_litres
                      ).toLocaleString()} L`
                    : "217,483 L"}
                </strong>

              </div>

              <div>

                <span>
                  TOTAL COST
                </span>

                <strong>
                  {plan
                    ? `₹${Math.round(
                        plan.total_cost
                      ).toLocaleString()}`
                    : "₹7.14 L"}
                </strong>

              </div>

            </div>

          </div>


          {/* =================================================
              ENVIRONMENT
          ================================================== */}

          <div
            className={`panel environment-panel ${environmentClass}`}
          >

            <div className="panel-title">

              <span>
                ENVIRONMENT
              </span>

              <span className="live-tag">
                LIVE SIMULATION
              </span>

            </div>


            <div className="environment-status">

              <div className="environment-icon">
                {environmentAnalysis.icon}
              </div>

              <div>

                <strong>
                  {environmentAnalysis.title}
                </strong>

                <span>
                  {environment
                    ? `SEVERITY ${(
                        environment.overall_severity *
                        100
                      ).toFixed(0)}%`
                    : "NO ACTIVE EVENTS"}
                </span>

              </div>

            </div>


            {/* IMPACT METRICS */}

            <div className="environment-impact-grid">

              <div className="environment-impact">

                <span>
                  SPEED FACTOR
                </span>

                <strong
                  className={
                    speedImpact < 70
                      ? "danger-text"
                      : speedImpact < 90
                      ? "warning-text"
                      : "safe-text"
                  }
                >
                  {speedImpact}%
                </strong>

                <small>
                  {speedImpact < 100
                    ? `${100 - speedImpact}% REDUCTION`
                    : "NOMINAL"}
                </small>

              </div>


              <div className="environment-impact">

                <span>
                  FUEL IMPACT
                </span>

                <strong
                  className={
                    fuelImpact > 120
                      ? "danger-text"
                      : fuelImpact > 105
                      ? "warning-text"
                      : "safe-text"
                  }
                >
                  +{fuelImpact - 100}%
                </strong>

                <small>
                  CONSUMPTION
                </small>

              </div>


              <div className="environment-impact">

                <span>
                  ETA DELAY
                </span>

                <strong
                  className={
                    (mission?.delay_days ?? 0) > 2
                      ? "danger-text"
                      : (mission?.delay_days ?? 0) > 0
                      ? "warning-text"
                      : "safe-text"
                  }
                >
                  {(mission?.delay_days ?? 0).toFixed(
                    1
                  )}D
                </strong>

                <small>
                  PROJECTED
                </small>

              </div>


              <div className="environment-impact">

                <span>
                  RISK STATE
                </span>

                <strong
                  className={
                    environmentClass === "danger"
                      ? "danger-text"
                      : environmentClass === "warning"
                      ? "warning-text"
                      : "safe-text"
                  }
                >
                  {risk?.overall_status ??
                    "SAFE"}
                </strong>

                <small>
                  LIVE ASSESSMENT
                </small>

              </div>

            </div>


            {/* ENVIRONMENT VARIABLES */}

            <div className="environment-grid">

              <div>
                <span>
                  WEATHER
                </span>

                <strong>
                  {environment
                    ? severityLabel(
                        environment.weather_severity
                      )
                    : "CALM"}
                </strong>
              </div>

              <div>
                <span>
                  SEA ICE
                </span>

                <strong>
                  {environment
                    ? severityLabel(
                        environment.sea_ice_severity
                      )
                    : "LOW"}
                </strong>
              </div>

              <div>
                <span>
                  VISIBILITY
                </span>

                <strong>
                  {environment
                    ? `${Math.round(
                        environment.visibility_factor *
                          100
                      )}%`
                    : "100%"}
                </strong>
              </div>

              <div>
                <span>
                  CURRENT
                </span>

                <strong>
                  {environment
                    ? `${currentFactor.toFixed(2)}×`
                    : "1.00×"}
                </strong>
              </div>

            </div>

          </div>


          {/* =================================================
              RISK
          ================================================== */}

          <div
            className={`panel risk-panel ${environmentClass}`}
          >

            <div className="panel-title">

              <span>
                MISSION RISK
              </span>

              <span className="live-tag">
                LIVE
              </span>

            </div>


            <div className="risk-main">

              <div
                className={`risk-score ${
                  environmentClass === "danger"
                    ? "danger-text"
                    : environmentClass === "warning"
                    ? "warning-text"
                    : ""
                }`}
              >
                {risk?.overall_status ??
                  (plan
                    ? "SAFE"
                    : "PENDING")}
              </div>

              <div className="risk-bar">

                <div
                  className={
                    environmentClass === "danger"
                      ? "risk-fill-danger"
                      : environmentClass === "warning"
                      ? "risk-fill-warning"
                      : ""
                  }
                  style={{
                    width: `${risk
                      ? Math.max(
                          5,
                          Math.min(
                            100,
                            100 -
                              risk.safety_margin_days /
                                2
                          )
                        )
                      : 15}%`,
                  }}
                />

              </div>

            </div>


            <p>
              {risk
                ? risk.arrival_feasible
                  ? `Projected arrival has a ${risk.safety_margin_days.toFixed(
                      1
                    )}-day safety margin before the station inventory deadline.`
                  : "Projected arrival violates the station inventory safety deadline."
                : "Run the optimizer to calculate mission feasibility."}
            </p>


            {environmentAnalysis.level !== "normal" &&
              mission && (
                <div className="risk-consequence">

                  <strong>
                    {environmentAnalysis.level ===
                    "danger"
                      ? "⚠ VOYAGE IMPACT DETECTED"
                      : "⚠ ENVIRONMENTAL DISRUPTION"}
                  </strong>

                  <span>
                    Environmental conditions are
                    affecting vessel performance.
                    The simulation has recalculated
                    speed, fuel consumption and ETA.
                  </span>

                </div>
              )}

          </div>

        </section>

      </main>


      {/* =====================================================
          FOOTER
      ====================================================== */}

      <footer className="footer">

        <div>
          <span className="status-dot"></span>

          {isRunning
            ? "SIMULATION RUNNING"
            : isComplete
            ? "MISSION COMPLETE"
            : "SIMULATION ENGINE READY"}
        </div>

        <div>
          ENVIRONMENT:{" "}
          <strong>
            {environmentAnalysis.title}
          </strong>
        </div>

        <div>
          DATA MODE:{" "}
          <strong>
            SIMULATED
          </strong>
        </div>

        <div>
          OPTIMIZER:{" "}
          <strong>
            {result
              ? "COMPLETE"
              : "READY"}
          </strong>
        </div>

      </footer>

    </div>
  );
}


/*
 * ===========================================================
 * ENVIRONMENT ANALYSIS
 * ===========================================================
 */

function getEnvironmentAnalysis(
  environment: MissionState["environment"]
) {
  const event =
    environment?.active_event?.toLowerCase() ?? "";

  if (
    event.includes("storm") ||
    (environment?.weather_severity ?? 0) >= 0.7
  ) {
    return {
      level: "danger",
      icon: "⛈",
      title: "SEVERE STORM",
      description:
        "Severe weather detected. Vessel speed and fuel efficiency are being degraded.",
    };
  }

  if (
    event.includes("ice") ||
    (environment?.sea_ice_severity ?? 0) >= 0.4
  ) {
    return {
      level: "warning",
      icon: "🧊",
      title: "HEAVY SEA ICE",
      description:
        "Heavy sea ice detected. Vessel performance is being reduced and fuel demand is increasing.",
    };
  }

  return {
    level: "normal",
    icon: "◉",
    title: "NORMAL CONDITIONS",
    description:
      "Environmental conditions are within normal operating parameters.",
  };
}


/*
 * -----------------------------------------------------------
 * HELPERS
 * -----------------------------------------------------------
 */

function formatDate(
  dateString: string
) {
  const date = new Date(dateString);

  return date
    .toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    })
    .toUpperCase();
}


function severityLabel(
  severity: number
) {
  if (severity < 0.15) {
    return "CALM";
  }

  if (severity < 0.4) {
    return "MODERATE";
  }

  if (severity < 0.7) {
    return "SEVERE";
  }

  return "EXTREME";
}


export default App;