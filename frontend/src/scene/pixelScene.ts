import type { SceneConfig, SceneHandle, SceneQuality, WeatherMode } from "./types";

type Vec2 = { x: number; y: number };

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v));
}

function rand(seed: number) {
  // deterministic-ish PRNG (LCG)
  let s = seed >>> 0;
  return () => {
    s = (1664525 * s + 1013904223) >>> 0;
    return (s & 0xffffffff) / 0x100000000;
  };
}

function easeInOut(t: number) {
  return t * t * (3 - 2 * t);
}

type Cloud = {
  pos: Vec2;
  speed: number;
  w: number;
  h: number;
  layer: 0 | 1;
};

type Bird = {
  pos: Vec2;
  vel: Vec2;
  ttl: number;
  flapT: number;
};

type Particle = {
  pos: Vec2;
  vel: Vec2;
  life: number;
};

export function createPixelScene(canvas: HTMLCanvasElement, cfg: SceneConfig): SceneHandle {
  const ctx = canvas.getContext("2d", { alpha: true })!;
  ctx.imageSmoothingEnabled = false;

  const initialQuality: SceneQuality = cfg.quality || "full";
  const maxFps = Math.max(1, cfg.maxFps ?? cfg.fps);

  const state = {
    logicalW: cfg.logicalWidth,
    logicalH: cfg.logicalHeight,
    // Weather blending
    weatherCurrent: cfg.weather as WeatherMode,
    weatherTarget: cfg.weather as WeatherMode,
    weatherBlend: 1, // 0..1 blend towards target
    cloudyFactor: cfg.weather === "cloudy" ? 1 : 0,
    rainFactor: cfg.weather === "rain" ? 1 : 0,
    snowFactor: cfg.weather === "snow" ? 1 : 0,

    // Time blending
    timeOfDay: 0.35, // current 0..1
    timeTarget: 0.35,
    externalTime: false,

    // time
    running: true,
    paused: false,
    lastTs: 0,
    acc: 0,
    step: 1 / Math.max(1, cfg.fps),

    // draw throttling
    drawLastTs: 0,
    drawStep: 1 / maxFps,

    // quality
    quality: initialQuality as SceneQuality,
    dirty: true,

    // world
    seed: 1337,
    windT: 0,
    cloudT: 0,
    birdSpawnCooldown: 2,

    clouds: [] as Cloud[],
    birds: [] as Bird[],
    particles: [] as Particle[],

    // sizing
    scale: 1,
    offsetX: 0,
    offsetY: 0,
  };

  const rnd = rand(state.seed);

  function resize() {
    const rawDpr = window.devicePixelRatio || 1;
    const cap = cfg.dprCap && cfg.dprCap > 0 ? cfg.dprCap : rawDpr;
    const dpr = Math.max(1, Math.floor(Math.min(rawDpr, cap)));
    const cssW = Math.max(1, Math.floor(window.innerWidth));
    const cssH = Math.max(1, Math.floor(window.innerHeight));

    // Keep pixel-perfect scaling: integer scale based on CSS pixels.
    const scale = Math.max(1, Math.floor(Math.min(cssW / state.logicalW, cssH / state.logicalH)));
    state.scale = scale;

    const viewW = state.logicalW * scale;
    const viewH = state.logicalH * scale;

    state.offsetX = Math.floor((cssW - viewW) / 2);
    state.offsetY = Math.floor((cssH - viewH) / 2);

    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;

    // Physical buffer uses DPR but keep integer mapping by scaling logical->screen in draw.
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;

    state.dirty = true;
  }

  function init() {
    resize();

    // spawn some clouds
    const cloudCount = state.quality === "full" ? 6 : state.quality === "reduced" ? 3 : 0;
    for (let i = 0; i < cloudCount; i++) {
      state.clouds.push({
        pos: { x: rnd() * state.logicalW, y: 10 + rnd() * 50 },
        speed: 2 + rnd() * 6,
        w: 26 + rnd() * 42,
        h: 10 + rnd() * 10,
        layer: (rnd() < 0.5 ? 0 : 1) as 0 | 1,
      });
    }

    window.addEventListener("resize", resize, { passive: true });
  }

  function destroy() {
    state.running = false;
    if (rafId) cancelAnimationFrame(rafId);
    window.removeEventListener("resize", resize);
  }

  function spawnBird() {
    const y = 18 + rnd() * 40;
    const fromLeft = rnd() < 0.5;
    const x = fromLeft ? -10 : state.logicalW + 10;
    const vx = (fromLeft ? 1 : -1) * (30 + rnd() * 40);
    const vy = -5 + rnd() * 10;

    state.birds.push({
      pos: { x, y },
      vel: { x: vx, y: vy },
      ttl: 6 + rnd() * 4,
      flapT: rnd() * 10,
    });
  }

  function spawnParticles(dt: number) {
    if (state.quality !== "full") return;
    const rainK = Math.max(0, Math.min(1, state.rainFactor));
    const snowK = Math.max(0, Math.min(1, state.snowFactor));
    if (rainK <= 0.001 && snowK <= 0.001) return;

    const rate = 90 * rainK + 35 * snowK;
    const count = Math.floor(rate * dt);

    for (let i = 0; i < count; i++) {
      const x = rnd() * state.logicalW;
      const y = -4 - rnd() * 10;

      // pick based on dominant factor
      const isRain = rainK >= snowK;
      if (isRain) {
        state.particles.push({
          pos: { x, y },
          vel: { x: -6 + rnd() * 4, y: 140 + rnd() * 60 },
          life: 2,
        });
      } else {
        state.particles.push({
          pos: { x, y },
          vel: { x: -10 + rnd() * 20, y: 30 + rnd() * 30 },
          life: 5,
        });
      }
    }
  }

  function update(dt: number) {
    if (state.quality === "static") return;
    state.windT += dt;
    state.cloudT += dt;

    // Smooth weather transition
    // Move factors towards target over ~6-10 seconds.
    const wSpeed = 0.18; // per second
    if (state.weatherTarget !== state.weatherCurrent) {
      state.weatherBlend = Math.max(0, state.weatherBlend - dt * wSpeed);
      if (state.weatherBlend <= 0) {
        state.weatherCurrent = state.weatherTarget;
        state.weatherBlend = 1;
      }
    }

    // Target factors based on weatherTarget
    const tCloudy = state.weatherTarget === "cloudy" ? 1 : 0;
    const tRain = state.weatherTarget === "rain" ? 1 : 0;
    const tSnow = state.weatherTarget === "snow" ? 1 : 0;

    // Lerp factors smoothly
    const fSpeed = 0.25;
    state.cloudyFactor += (tCloudy - state.cloudyFactor) * (1 - Math.exp(-fSpeed * dt));
    state.rainFactor += (tRain - state.rainFactor) * (1 - Math.exp(-fSpeed * dt));
    state.snowFactor += (tSnow - state.snowFactor) * (1 - Math.exp(-fSpeed * dt));

    // clouds
    for (const c of state.clouds) {
      const layerMul = c.layer === 0 ? 0.6 : 1.0;
      c.pos.x += c.speed * layerMul * dt;
      if (c.pos.x > state.logicalW + 60) {
        c.pos.x = -60;
        c.pos.y = 10 + rnd() * 55;
      }
    }

    // birds
    if (state.quality === "full") {
      state.birdSpawnCooldown -= dt;
      const badWeather = Math.max(0, Math.min(1, state.rainFactor + state.snowFactor));
      const spawnChance = 1 - 0.65 * badWeather;
      if (state.birdSpawnCooldown <= 0 && rnd() < spawnChance) {
        spawnBird();
        state.birdSpawnCooldown = 6 + rnd() * 10;
      }

      for (let i = state.birds.length - 1; i >= 0; i--) {
        const b = state.birds[i];
        b.ttl -= dt;
        b.flapT += dt * 8;
        b.pos.x += b.vel.x * dt;
        b.pos.y += b.vel.y * dt;
        // slight sinusoidal bob
        b.pos.y += Math.sin(b.flapT * 0.7) * 0.15;
        if (b.ttl <= 0) state.birds.splice(i, 1);
      }
    } else {
      // aggressively clear to avoid growth if switching quality
      if (state.birds.length) state.birds.length = 0;
    }

    // weather particles
    if (state.quality === "full") {
      spawnParticles(dt);
      for (let i = state.particles.length - 1; i >= 0; i--) {
        const p = state.particles[i];
        p.life -= dt;
        p.pos.x += p.vel.x * dt;
        p.pos.y += p.vel.y * dt;
        if (p.pos.y > state.logicalH + 10 || p.life <= 0) state.particles.splice(i, 1);
      }
    } else {
      if (state.particles.length) state.particles.length = 0;
    }

    // Time-of-day (smooth) — either external target, or slow auto cycle.
    if (!state.externalTime) {
      state.timeTarget = (state.timeTarget + dt * 0.003) % 1;
    }
    // shortest-path interpolation over circular [0..1)
    let diff = state.timeTarget - state.timeOfDay;
    if (diff > 0.5) diff -= 1;
    if (diff < -0.5) diff += 1;
    const tSpeed = 0.35;
    state.timeOfDay = (state.timeOfDay + diff * (1 - Math.exp(-tSpeed * dt)) + 1) % 1;

    state.dirty = true;
  }

  function drawSky() {
    // palette-like gradients (fake pixel-art by drawing big rects)
    const t = state.timeOfDay;

    // day factor: 0 at night, 1 at noon
    const day = Math.sin(t * Math.PI * 2) * 0.5 + 0.5;
    const k = clamp01(easeInOut(day));

    // base sky
    // night: #071428, day: #79b8ff
    const r = Math.floor(7 + (121 - 7) * k);
    const g = Math.floor(20 + (184 - 20) * k);
    const b = Math.floor(40 + (255 - 40) * k);

    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fillRect(0, 0, state.logicalW, state.logicalH);

    // sun glow at noon-ish
    const sunX = Math.floor(state.logicalW * (0.2 + 0.6 * t));
    const sunY = Math.floor(40 + 30 * Math.sin(t * Math.PI * 2 + Math.PI));
    const glowA = 0.12 * k;
    if (glowA > 0.001) {
      ctx.fillStyle = `rgba(255,240,200,${glowA})`;
      ctx.fillRect(sunX - 26, sunY - 18, 52, 36);
    }
  }

  function drawClouds() {
    if (state.quality === "static") return;
    for (const c of state.clouds) {
      const cloudy = Math.max(0, Math.min(1, state.cloudyFactor));
      const base = c.layer === 0 ? 0.35 : 0.55;
      const alpha = base + 0.35 * cloudy;
      const y = Math.floor(c.pos.y);
      const x = Math.floor(c.pos.x);
      ctx.fillStyle = `rgba(255,255,255,${alpha})`;

      // pixel cloud made from 3-4 blocks
      const w = Math.floor(c.w);
      const h = Math.floor(c.h);
      ctx.fillRect(x, y + 2, w, h);
      ctx.fillRect(x + 6, y, w - 10, h);
      ctx.fillRect(x + 12, y - 2, Math.max(6, w - 22), h);
      ctx.fillRect(x + 3, y + 5, w - 6, h);
    }
  }

  function drawHills() {
    // far hills
    ctx.fillStyle = "rgb(35,92,70)";
    ctx.fillRect(0, 140, state.logicalW, 70);

    // near ground
    ctx.fillStyle = "rgb(48,120,70)";
    ctx.fillRect(0, 170, state.logicalW, 100);
  }

  function drawWheat() {
    // wheat field on right
    const baseY = 190;
    const wind = state.quality === "static" ? 0 : Math.sin(state.windT * 1.2) * 0.9 + Math.sin(state.windT * 0.33) * 0.6;

    for (let x = 0; x < state.logicalW; x += 3) {
      const height = 10 + Math.floor((Math.sin((x + state.windT * 20) * 0.05) * 0.5 + 0.5) * 10);
      const sway = Math.floor(wind * 2 + Math.sin((x + state.windT * 10) * 0.12) * 1.2);

      // stems
      ctx.fillStyle = "rgb(90,160,70)";
      ctx.fillRect(x + sway, baseY - height, 1, height);

      // heads
      ctx.fillStyle = "rgb(220,200,90)";
      ctx.fillRect(x + sway - 1, baseY - height - 2, 3, 2);
    }
  }

  function drawTrees() {
    // a few pixel trees
    const wind = state.quality === "static" ? 0 : Math.sin(state.windT * 1.1) * 1.2 + Math.sin(state.windT * 0.27) * 0.6;

    const trees = [
      { x: 60, y: 165, s: 1.0 },
      { x: 110, y: 170, s: 0.9 },
      { x: 160, y: 168, s: 1.05 },
    ];

    for (const t of trees) {
      const sway = Math.floor(wind * 2 * t.s);

      // trunk
      ctx.fillStyle = "rgb(92,60,40)";
      ctx.fillRect(t.x + 6, t.y + 18, 4, 16);

      // canopy (pixel blobs) shifted by sway
      ctx.fillStyle = "rgb(30,90,50)";
      ctx.fillRect(t.x + sway, t.y, 16, 10);
      ctx.fillRect(t.x + 2 + sway, t.y - 6, 12, 10);
      ctx.fillRect(t.x + 4 + sway, t.y - 10, 8, 8);

      // highlights
      ctx.fillStyle = "rgb(45,120,70)";
      ctx.fillRect(t.x + 3 + sway, t.y - 2, 4, 3);
      ctx.fillRect(t.x + 9 + sway, t.y - 6, 3, 3);
    }
  }

  function drawBirds() {
    if (state.quality !== "full") return;
    ctx.fillStyle = "rgb(20,20,20)";
    for (const b of state.birds) {
      const x = Math.floor(b.pos.x);
      const y = Math.floor(b.pos.y);
      const flap = Math.sin(b.flapT) > 0;

      // tiny 5px bird: \/ or /\ shape
      if (flap) {
        ctx.fillRect(x, y, 1, 1);
        ctx.fillRect(x + 1, y + 1, 1, 1);
        ctx.fillRect(x + 2, y + 2, 1, 1);
        ctx.fillRect(x + 3, y + 1, 1, 1);
        ctx.fillRect(x + 4, y, 1, 1);
      } else {
        ctx.fillRect(x, y + 1, 1, 1);
        ctx.fillRect(x + 1, y, 1, 1);
        ctx.fillRect(x + 2, y + 1, 1, 1);
        ctx.fillRect(x + 3, y, 1, 1);
        ctx.fillRect(x + 4, y + 1, 1, 1);
      }
    }
  }

  function drawParticles() {
    if (state.quality !== "full") return;
    const rainK = Math.max(0, Math.min(1, state.rainFactor));
    const snowK = Math.max(0, Math.min(1, state.snowFactor));
    if (rainK <= 0.001 && snowK <= 0.001) return;

    // We draw stored particles; color slightly depends on dominant mode.
    const isRain = rainK >= snowK;
    if (isRain) {
      ctx.fillStyle = `rgba(180,220,255,${0.35 + 0.5 * rainK})`;
      for (const p of state.particles) {
        const x = Math.floor(p.pos.x);
        const y = Math.floor(p.pos.y);
        ctx.fillRect(x, y, 1, 3);
      }
    } else {
      ctx.fillStyle = `rgba(255,255,255,${0.35 + 0.55 * snowK})`;
      for (const p of state.particles) {
        const x = Math.floor(p.pos.x);
        const y = Math.floor(p.pos.y);
        ctx.fillRect(x, y, 1, 1);
      }
    }
  }

  function drawNightTint() {
    // overlay tint based on time of day
    // day factor
    const t = state.timeOfDay;
    const day = Math.sin(t * Math.PI * 2) * 0.5 + 0.5;
    const k = clamp01(easeInOut(day));
    const nightA = 0.55 * (1 - k);

    if (nightA > 0.001) {
      ctx.fillStyle = `rgba(10,20,40,${nightA})`;
      ctx.fillRect(0, 0, state.logicalW, state.logicalH);
    }
  }

  function draw() {
    // Clear full canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // draw to logical resolution inside letterboxed area
    ctx.save();
    ctx.translate(state.offsetX, state.offsetY);
    ctx.scale(state.scale, state.scale);
    ctx.imageSmoothingEnabled = false;

    drawSky();
    drawClouds();
    drawHills();
    drawTrees();
    drawWheat();
    drawBirds();
    drawParticles();
    drawNightTint();

    ctx.restore();

    // letterbox bars
    const cssW = Math.floor(window.innerWidth);
    const cssH = Math.floor(window.innerHeight);
    const viewW = state.logicalW * state.scale;
    const viewH = state.logicalH * state.scale;

    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    if (state.offsetY > 0) {
      ctx.fillRect(0, 0, cssW, state.offsetY);
      ctx.fillRect(0, state.offsetY + viewH, cssW, cssH - (state.offsetY + viewH));
    }
    if (state.offsetX > 0) {
      ctx.fillRect(0, 0, state.offsetX, cssH);
      ctx.fillRect(state.offsetX + viewW, 0, cssW - (state.offsetX + viewW), cssH);
    }
    ctx.restore();

    state.dirty = false;
  }

  let rafId: number | null = null;

  function schedule() {
    if (!state.running || state.paused) return;
    if (rafId != null) return;
    rafId = requestAnimationFrame(frame);
  }

  function frame(ts: number) {
    rafId = null;
    if (!state.running || state.paused) return;

    // Static mode: only redraw when marked dirty (e.g. resize, setWeather/time).
    if (state.quality === "static") {
      if (state.dirty) draw();
      return;
    }

    if (!state.lastTs) state.lastTs = ts;
    const dt = Math.min(0.1, (ts - state.lastTs) / 1000);
    state.lastTs = ts;
    state.acc += dt;

    while (state.acc >= state.step) {
      update(state.step);
      state.acc -= state.step;
    }

    // Cap draw FPS separately from simulation.
    const drawDt = (ts - state.drawLastTs) / 1000;
    if (!state.drawLastTs || drawDt >= state.drawStep || state.dirty) {
      state.drawLastTs = ts;
      draw();
    }

    schedule();
  }

  init();
  schedule();

  return {
    setWeather: (w: WeatherMode) => {
      state.weatherTarget = w;
      state.dirty = true;
      schedule();
    },
    setTimeOfDay: (t01: number) => {
      state.externalTime = true;
      state.timeTarget = clamp01(t01);
      state.dirty = true;
      schedule();
    },
    setQuality: (q: SceneQuality) => {
      state.quality = q;
      // Re-init clouds based on quality.
      state.clouds.length = 0;
      const cloudCount = state.quality === "full" ? 6 : state.quality === "reduced" ? 3 : 0;
      for (let i = 0; i < cloudCount; i++) {
        state.clouds.push({
          pos: { x: rnd() * state.logicalW, y: 10 + rnd() * 50 },
          speed: 2 + rnd() * 6,
          w: 26 + rnd() * 42,
          h: 10 + rnd() * 10,
          layer: (rnd() < 0.5 ? 0 : 1) as 0 | 1,
        });
      }
      state.dirty = true;
      schedule();
    },
    pause: () => {
      state.paused = true;
      state.lastTs = 0;
      state.acc = 0;
      if (rafId != null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    },
    resume: () => {
      if (!state.running) return;
      state.paused = false;
      state.lastTs = 0;
      state.acc = 0;
      state.dirty = true;
      schedule();
    },
    destroy,
  };
}
