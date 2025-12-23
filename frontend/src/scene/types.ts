export type WeatherMode = "clear" | "cloudy" | "rain" | "snow";

export type SceneQuality = "full" | "reduced" | "static";

export type SceneConfig = {
  logicalWidth: number;
  logicalHeight: number;
  fps: number; // simulation FPS
  maxFps?: number; // draw FPS cap (defaults to fps)
  weather: WeatherMode;
  quality?: SceneQuality;
  dprCap?: number; // clamp devicePixelRatio
};

export type SceneHandle = {
  setWeather: (w: WeatherMode) => void;
  setTimeOfDay: (t01: number) => void; // 0..1 (target)
  setQuality: (q: SceneQuality) => void;
  pause: () => void;
  resume: () => void;
  destroy: () => void;
};
