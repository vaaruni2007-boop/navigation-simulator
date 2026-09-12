import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

interface Waypoint {
  latitude: number;
  longitude: number;
}

interface VesselPosition {
  latitude: number;
  longitude: number;
}

interface MapViewProps {
  waypoints: Waypoint[];
  vesselProgress: number;
  vesselName: string;
  vesselPosition?: VesselPosition;
}

export default function MapView({
  waypoints,
  vesselProgress,
  vesselName,
  vesselPosition,
}: MapViewProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const routeRef = useRef<L.Polyline | null>(null);
  const vesselMarkerRef = useRef<L.Marker | null>(null);

  /*
   * ---------------------------------------------------------
   * CREATE MAP
   * ---------------------------------------------------------
   *
   * The Leaflet map is created only once.
   */
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) {
      return;
    }

    const map = L.map(mapContainerRef.current, {
      worldCopyJump: false,
      minZoom: 2,
      maxZoom: 8,
    }).setView([-20, 45], 3);

    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }
    ).addTo(map);

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      routeRef.current = null;
      vesselMarkerRef.current = null;
    };
  }, []);

  /*
   * ---------------------------------------------------------
   * DRAW ROUTE
   * ---------------------------------------------------------
   *
   * The route is redrawn only when the waypoint array changes.
   */
  useEffect(() => {
    if (!mapRef.current || waypoints.length < 2) {
      return;
    }

    const map = mapRef.current;

    const coordinates: [number, number][] = waypoints.map(
      (point) => [point.latitude, point.longitude]
    );

    /*
     * Remove previous route.
     */
    if (routeRef.current) {
      routeRef.current.remove();
    }

    /*
     * Draw simulated maritime corridor.
     */
    routeRef.current = L.polyline(coordinates, {
      color: "#42d9ff",
      weight: 4,
      opacity: 0.9,
      dashArray: "10 8",
    }).addTo(map);

    /*
     * Fit map to route.
     */
    map.fitBounds(routeRef.current.getBounds(), {
      padding: [40, 40],
    });

    /*
     * Create vessel marker once.
     */
    if (!vesselMarkerRef.current) {
      const vesselIcon = L.divIcon({
        className: "vessel-marker",
        html: `
          <div class="vessel-icon">
            🚢
          </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      });

      const initialPosition: [number, number] = vesselPosition
        ? [
            vesselPosition.latitude,
            vesselPosition.longitude,
          ]
        : coordinates[0];

      vesselMarkerRef.current = L.marker(initialPosition, {
        icon: vesselIcon,
        title: vesselName,
      }).addTo(map);
    }

    /*
     * Set the current vessel position.
     */
    updateVesselPosition(
      vesselMarkerRef.current,
      vesselPosition,
      waypoints,
      vesselProgress
    );
  }, [waypoints]);

  /*
   * ---------------------------------------------------------
   * UPDATE VESSEL POSITION
   * ---------------------------------------------------------
   *
   * The backend position is authoritative.
   *
   * If there is no backend position yet, progress-based
   * interpolation is used.
   */
  useEffect(() => {
    if (!vesselMarkerRef.current) {
      return;
    }

    updateVesselPosition(
      vesselMarkerRef.current,
      vesselPosition,
      waypoints,
      vesselProgress
    );
  }, [
    vesselPosition,
    vesselProgress,
    waypoints,
  ]);

  /*
   * ---------------------------------------------------------
   * UPDATE VESSEL NAME
   * ---------------------------------------------------------
   */
  useEffect(() => {
    if (!vesselMarkerRef.current) {
      return;
    }

    vesselMarkerRef.current.unbindTooltip();

    vesselMarkerRef.current.bindTooltip(vesselName, {
      direction: "top",
      offset: [0, -18],
    });
  }, [vesselName]);

  return (
    <div
      ref={mapContainerRef}
      className="google-map"
    />
  );
}


/*
 * =========================================================
 * POSITION UPDATE
 * =========================================================
 *
 * Priority:
 *
 * 1. Backend vessel_position
 * 2. Progress-based fallback
 */
function updateVesselPosition(
  marker: L.Marker,
  vesselPosition: VesselPosition | undefined,
  waypoints: Waypoint[],
  progress: number
) {
  /*
   * Backend simulation position.
   */
  if (vesselPosition) {
    marker.setLatLng([
      vesselPosition.latitude,
      vesselPosition.longitude,
    ]);

    return;
  }

  /*
   * Pre-mission fallback.
   */
  const fallbackPosition = calculatePositionFromProgress(
    waypoints,
    progress
  );

  if (fallbackPosition) {
    marker.setLatLng(fallbackPosition);
  }
}


/*
 * =========================================================
 * FALLBACK POSITION CALCULATOR
 * =========================================================
 *
 * Interpolates between simulated maritime waypoints.
 *
 * This is only used before the backend supplies an actual
 * simulated vessel position.
 */
function calculatePositionFromProgress(
  waypoints: Waypoint[],
  progress: number
): [number, number] | null {
  if (waypoints.length < 2) {
    return null;
  }

  const safeProgress = Math.max(
    0,
    Math.min(100, progress)
  );

  const normalizedProgress = safeProgress / 100;

  const segmentCount = waypoints.length - 1;

  const exactSegment =
    normalizedProgress * segmentCount;

  const segmentIndex = Math.min(
    Math.floor(exactSegment),
    segmentCount - 1
  );

  const segmentProgress =
    exactSegment - segmentIndex;

  const start = waypoints[segmentIndex];
  const end = waypoints[segmentIndex + 1];

  const latitude =
    start.latitude +
    (end.latitude - start.latitude) *
      segmentProgress;

  const longitude =
    start.longitude +
    (end.longitude - start.longitude) *
      segmentProgress;

  return [latitude, longitude];
}