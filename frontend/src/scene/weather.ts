import type { WeatherMode } from "./types";

export type KrasnodarWeather = {
  mode: WeatherMode;
  temperatureC: number;
  cloudCover: number; // 0..100
  precipitationMm: number;
  fetchedAt: number;
};

const KRASNODAR = {
  lat: 45.0355,
  lon: 38.9753,
  timezone: "Europe/Moscow",
};

// Open-Meteo: no API key
// https://open-meteo.com/en/docs
export async function fetchKrasnodarWeather(signal?: AbortSignal): Promise<KrasnodarWeather> {
  const url = new URL("https://api.open-meteo.com/v1/forecast");
  url.searchParams.set("latitude", String(KRASNODAR.lat));
  url.searchParams.set("longitude", String(KRASNODAR.lon));
  url.searchParams.set("timezone", KRASNODAR.timezone);
  url.searchParams.set("current", "temperature_2m,precipitation,cloud_cover,weather_code");

  const res = await fetch(url.toString(), { method: "GET", signal, headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`weather http ${res.status}`);

  const data = (await res.json()) as any;
  const cur = data && data.current ? data.current : null;
  if (!cur) throw new Error("weather: invalid response");

  const temperatureC = Number(cur.temperature_2m ?? 0);
  const precipitationMm = Number(cur.precipitation ?? 0);
  const cloudCover = Number(cur.cloud_cover ?? 0);
  const weatherCode = Number(cur.weather_code ?? 0);

  // Map to simplified modes.
  // Priority: snow/rain based on precipitation and temperature.
  let mode: WeatherMode = "clear";

  if (precipitationMm > 0.05) {
    mode = temperatureC <= 0 ? "snow" : "rain";
  } else {
    // Use cloud cover and some weather codes for cloudy.
    // Open-Meteo codes: 0 clear, 1-3 partly/cloudy, 45/48 fog, 51+ drizzle/rain...
    if (cloudCover >= 60 || (weatherCode >= 1 && weatherCode <= 3) || weatherCode === 45 || weatherCode === 48) {
      mode = "cloudy";
    } else {
      mode = "clear";
    }
  }

  return {
    mode,
    temperatureC,
    cloudCover,
    precipitationMm,
    fetchedAt: Date.now(),
  };
}

export function krasnodarTime01(now: Date = new Date()): number {
  // Use local time. If you want strict Krasnodar time regardless of client TZ,
  // backend could provide it later. For now, client-side local time is acceptable.
  const h = now.getHours();
  const m = now.getMinutes();
  const s = now.getSeconds();
  const t = (h * 3600 + m * 60 + s) / 86400;
  return t;
}
