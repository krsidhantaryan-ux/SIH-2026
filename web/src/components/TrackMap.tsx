import { useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import { latLngBounds } from "leaflet";
import type { TrackPoint } from "../types";

interface TrackMapProps {
  track: TrackPoint[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

function FitTrack({ track }: { track: TrackPoint[] }) {
  const map = useMap();
  useEffect(() => {
    if (!track.length) return;
    const bounds = latLngBounds(track.map((point) => [point.latitude, point.longitude]));
    map.fitBounds(bounds.pad(0.18), { animate: false });
  }, [map, track]);
  return null;
}

function pointColor(wind: number): string {
  if (wind >= 120) return "#c084fc";
  if (wind >= 90) return "#fb7185";
  if (wind >= 64) return "#f97316";
  if (wind >= 34) return "#facc15";
  return "#38bdf8";
}

export default function TrackMap({ track, selectedIndex, onSelect }: TrackMapProps) {
  const selected = track[selectedIndex];
  const positions = track.map((point) => [point.latitude, point.longitude] as [number, number]);

  return (
    <div className="map-shell" aria-label="Cyclone Phailin track map">
      <MapContainer
        center={[selected.latitude, selected.longitude]}
        zoom={5}
        zoomControl={false}
        attributionControl
        className="track-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Polyline positions={positions} pathOptions={{ color: "#7dd3fc", weight: 2, opacity: 0.65 }} />
        {track.map((point, index) => {
          const active = index === selectedIndex;
          return (
            <CircleMarker
              key={point.valid_time}
              center={[point.latitude, point.longitude]}
              radius={active ? 9 : point.vmax_kt >= 90 ? 5 : 3.5}
              eventHandlers={{ click: () => onSelect(index) }}
              pathOptions={{
                color: active ? "#ffffff" : pointColor(point.vmax_kt),
                fillColor: pointColor(point.vmax_kt),
                fillOpacity: active ? 1 : 0.82,
                weight: active ? 3 : 1,
              }}
            >
              <Tooltip>
                <strong>{point.vmax_kt.toFixed(0)} kt</strong>
                <br />
                {new Date(point.valid_time).toLocaleString("en-IN", {
                  timeZone: "UTC",
                  day: "2-digit",
                  month: "short",
                  hour: "2-digit",
                  minute: "2-digit",
                })} UTC
              </Tooltip>
            </CircleMarker>
          );
        })}
        <FitTrack track={track} />
      </MapContainer>
      <div className="map-topline">
        <span className="live-dot" /> Historical track
        <span className="map-time">Valid {formatCompact(selected.valid_time)}</span>
      </div>
      <div className="map-coordinates">
        {selected.latitude.toFixed(2)}°N · {selected.longitude.toFixed(2)}°E
      </div>
    </div>
  );
}

function formatCompact(value: string): string {
  return new Date(value)
    .toLocaleString("en-GB", {
      timeZone: "UTC",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
    .replace(",", "") + " UTC";
}
