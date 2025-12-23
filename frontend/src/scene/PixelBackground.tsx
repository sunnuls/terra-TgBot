import React, { useEffect, useRef } from "react";
import { createPixelScene } from "./pixelScene";
import { fetchKrasnodarWeather, krasnodarTime01 } from "./weather";
import type { SceneQuality } from "./types";

function readModeOverride(): "auto" | SceneQuality {
  try {
    const v = (localStorage.getItem("terra_bg_mode") || "").toLowerCase();
    if (v === "full" || v === "reduced" || v === "static") return v;
    return "auto";
  } catch {
    return "auto";
  }
}

function detectLowEnd(): boolean {
  // Conservative heuristics for Telegram WebView stability.
  // If we mis-detect, user can override via localStorage key: terra_bg_mode.
  const nav: any = navigator as any;
  const cores = Number(nav.hardwareConcurrency || 0);
  const mem = Number(nav.deviceMemory || 0);
  const dpr = Number(window.devicePixelRatio || 1);

  if (mem && mem <= 2) return true;
  if (cores && cores <= 4) return true;
  if (dpr >= 3) return true;
  return false;
}

function pickQuality(): SceneQuality {
  const override = readModeOverride();
  if (override !== "auto") return override;
  return detectLowEnd() ? "static" : "full";
}

export function PixelBackground() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;

    const quality = pickQuality();
    const maxFps = quality === "full" ? 30 : quality === "reduced" ? 24 : 1;
    const simFps = quality === "full" ? 30 : quality === "reduced" ? 20 : 1;
    const dprCap = quality === "full" ? 2 : 1;

    let scene: ReturnType<typeof createPixelScene> | null = null;
    let timeTimer: number | null = null;
    let weatherTimer: number | null = null;

    let aborted = false;
    let controller: AbortController | null = null;
    let paused = false;

    const setPaused = (p: boolean) => {
      paused = p;
      if (!scene) return;
      if (paused) scene.pause();
      else scene.resume();
    };

    const updateWeather = async () => {
      if (aborted || paused) return;
      try {
        controller?.abort();
        controller = new AbortController();
        const w = await fetchKrasnodarWeather(controller.signal);
        if (aborted || paused || !scene) return;
        scene.setWeather(w.mode);
      } catch {
        // ignore network errors: keep previous theme
      }
    };

    const updateTime = () => {
      if (aborted || paused || !scene) return;
      scene.setTimeOfDay(krasnodarTime01(new Date()));
    };

    const onVisibility = () => {
      // In Telegram WebView visibility changes are common during overlays.
      const hidden = document.visibilityState === "hidden";
      setPaused(hidden);
      if (!hidden) {
        updateTime();
        // avoid immediate heavy work on resume in low-end modes
        if (quality === "full") updateWeather();
      }
    };

    const initScene = () => {
      if (aborted || scene) return;
      scene = createPixelScene(canvas, {
        logicalWidth: 480,
        logicalHeight: 270,
        fps: simFps,
        maxFps,
        dprCap,
        quality,
        weather: "clear",
      });

      // initial
      updateTime();
      updateWeather();

      // Time sync (every minute)
      timeTimer = window.setInterval(updateTime, 60_000);

      // Weather sync (every 15 minutes) — skip for static mode
      if (quality !== "static") {
        weatherTimer = window.setInterval(updateWeather, 15 * 60_000);
      }

      // Pause/resume hooks
      document.addEventListener("visibilitychange", onVisibility, { passive: true });
      window.addEventListener("pagehide", () => setPaused(true), { passive: true });
      window.addEventListener("focus", () => setPaused(false), { passive: true });
      window.addEventListener("blur", () => setPaused(true), { passive: true });
    };

    // Lazy init: let Telegram WebView settle first.
    const ric = (window as any).requestIdleCallback as
      | ((cb: () => void, opts?: { timeout: number }) => number)
      | undefined;
    let idleId: number | null = null;
    if (ric) {
      idleId = ric(initScene, { timeout: 800 });
    } else {
      const t = window.setTimeout(initScene, 0);
      idleId = t as unknown as number;
    }

    return () => {
      aborted = true;
      try {
        controller?.abort();
      } catch {
        // ignore
      }
      if (idleId != null) {
        const cic = (window as any).cancelIdleCallback as ((id: number) => void) | undefined;
        if (cic) cic(idleId);
        else window.clearTimeout(idleId);
      }
      if (timeTimer != null) window.clearInterval(timeTimer);
      if (weatherTimer != null) window.clearInterval(weatherTimer);
      document.removeEventListener("visibilitychange", onVisibility as any);
      if (scene) scene.destroy();
    };
  }, []);

  return (
    <canvas
      ref={ref}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
    />
  );
}
