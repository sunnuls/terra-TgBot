(function () {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

  const $ = (id) => document.getElementById(id);
  const elSubtitle = $("subtitle");
  const elFullName = $("fullName");
  const elRole = $("role");
  const elAvatar = $("avatar");
  const elWeekValue = $("weekValue");
  const elMonthValue = $("monthValue");
  const elWeekHint = $("weekHint");
  const elMonthHint = $("monthHint");
  const elActions = $("actions");
  const elErrorBox = $("errorBox");
  const elErrorText = $("errorText");

  const settingsBtn = $("settingsBtn");

  const weatherCard = $("weatherCard");
  const weatherPlace = $("weatherPlace");
  const weatherTemp = $("weatherTemp");
  const weatherDesc = $("weatherDesc");
  const weatherPrecip = $("weatherPrecip");
  const weatherUpdated = $("weatherUpdated");

  const weatherLocList = $("weatherLocList");
  const weatherLocAdd = $("weatherLocAdd");
  const weatherLocName = $("weatherLocName");
  const weatherMapEl = $("weatherMap");
  const weatherPinAdd = $("weatherPinAdd");
  const weatherPinsReset = $("weatherPinsReset");
  const weatherLocSave = $("weatherLocSave");
  const weatherLocEditResult = $("weatherLocEditResult");

  const weatherViewTitle = $("weatherViewTitle");
  const weatherViewCard = $("weatherViewCard");
  const weatherViewPlace = $("weatherViewPlace");
  const weatherViewTemp = $("weatherViewTemp");
  const weatherViewDesc = $("weatherViewDesc");
  const weatherViewPrecip = $("weatherViewPrecip");
  const weatherViewUpdated = $("weatherViewUpdated");
  const weatherViewForecast = $("weatherViewForecast");
  const weatherLocDelete = $("weatherLocDelete");

  const screens = {
    dashboard: $("screenDashboard"),
    otd: $("screenOtd"),
    stats: $("screenStats"),
    settings: $("screenSettings"),
    brig: $("screenBrig"),
    weatherLocations: $("screenWeatherLocations"),
    weatherLocEdit: $("screenWeatherLocEdit"),
    weatherLocView: $("screenWeatherLocView"),
  };
  const backBtn = $("backBtn");

  const otdDate = $("otdDate");
  const otdHours = $("otdHours");
  const otdWorkType = $("otdWorkType");
  const otdMachineKindWrap = $("otdMachineKindWrap");
  const otdMachineKind = $("otdMachineKind");
  const otdMachineNameWrap = $("otdMachineNameWrap");
  const otdMachineName = $("otdMachineName");
  const otdActivity = $("otdActivity");
  const otdLocation = $("otdLocation");
  const otdCrop = $("otdCrop");
  const otdTripsWrap = $("otdTripsWrap");
  const otdTrips = $("otdTrips");
  const otdSubmit = $("otdSubmit");
  const otdResult = $("otdResult");

  const statsResult = $("statsResult");
  const statsToday = $("statsToday");
  const statsWeek = $("statsWeek");
  const statsMonth = $("statsMonth");

  const settingsFullName = $("settingsFullName");
  const settingsSave = $("settingsSave");
  const settingsResult = $("settingsResult");

  const brigDate = $("brigDate");
  const brigCrop = $("brigCrop");
  const brigField = $("brigField");
  const brigRows = $("brigRows");
  const brigWorkers = $("brigWorkers");
  const brigBags = $("brigBags");
  const brigSubmit = $("brigSubmit");
  const brigResult = $("brigResult");

  const state = {
    role: "user",
    initData: "",
    dictionaries: null,
    screen: "dashboard",
    otd: {
      workType: "",
      machineKind: null,
      machineMode: "list",
    },
    weather: {
      lat: null,
      lon: null,
      place: "",
      lastTs: 0,
    },
    weatherLoc: {
      editingId: null,
      viewingId: null,
      map: null,
      markers: [],
    },
  };

  const _LS_WEATHER_GEO = "terra_weather_geo_v1";
  const _LS_WEATHER_LOCS = "terra_weather_locations_v1";

  function _fmtTime(tsMs) {
    try {
      const d = new Date(tsMs);
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      return `${hh}:${mm}`;
    } catch (e) {
      return "";
    }
  }

  async function renderWeatherLocations() {
    if (!weatherLocList) return;
    const locs = loadWeatherLocations();
    weatherLocList.innerHTML = "";

    for (const loc of locs) {
      const { lat, lon } = _centroid(loc.polygon);
      let t = null;
      let meta = "";
      try {
        const cur = await _fetchWeatherCurrent(lat, lon);
        t = cur.t;
        meta = cur.p != null ? `Осадки: ${cur.p.toFixed(1)} мм` : "";
      } catch (e) {
        meta = "Погода недоступна";
      }

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "locCard";
      btn.innerHTML = `
        <div class="locCard__row">
          <div class="locCard__name">${escapeHtml(loc.name || "Локация")}</div>
          <div class="locCard__temp">${t == null ? "—" : `${t}°`}</div>
        </div>
        <div class="locCard__meta">${escapeHtml(meta || "")}</div>
      `;
      btn.addEventListener("click", () => openWeatherLocView(loc.id));
      weatherLocList.appendChild(btn);
    }
  }

  async function openWeatherLocations() {
    setScreen("weatherLocations");
    await renderWeatherLocations();
  }

  function _ensureLeaflet() {
    const L = window.L;
    if (!L) throw new Error("Leaflet не загрузился");
    return L;
  }

  function _clearMap() {
    try {
      if (state.weatherLoc.map) {
        state.weatherLoc.map.off();
        state.weatherLoc.map.remove();
      }
    } catch (e) {}
    state.weatherLoc.map = null;
    state.weatherLoc.markers = [];
  }

  function _renderPolygonLine() {
    const L = window.L;
    if (!L || !state.weatherLoc.map) return;
    if (state.weatherLoc.polyLine) {
      try {
        state.weatherLoc.map.removeLayer(state.weatherLoc.polyLine);
      } catch (e) {}
    }
    const pts = state.weatherLoc.markers.map((m) => m.getLatLng());
    state.weatherLoc.polyLine = L.polygon(pts, { color: "#4f8cff", weight: 2, opacity: 0.9, fillOpacity: 0.08 });
    state.weatherLoc.polyLine.addTo(state.weatherLoc.map);
  }

  function _addMarker(lat, lon) {
    const L = _ensureLeaflet();
    if (!state.weatherLoc.map) return;
    const m = L.marker([lat, lon], { draggable: true });
    m.addTo(state.weatherLoc.map);
    m.on("drag", _renderPolygonLine);
    m.on("dragend", _renderPolygonLine);
    m.on("click", () => {
      const canDelete = state.weatherLoc.markers.length > 3;
      const html = canDelete ? `<button type=\"button\" id=\"_delPin\" style=\"width:100%; padding:8px 10px; border-radius:10px; border:1px solid rgba(0,0,0,.15); background:#fff\">Удалить пин</button>` : `<div style=\"font-size:12px\">Нужно минимум 3 пина</div>`;
      m.bindPopup(html).openPopup();
      setTimeout(() => {
        const el = document.getElementById("_delPin");
        if (el) {
          el.onclick = () => {
            try {
              state.weatherLoc.map.removeLayer(m);
            } catch (e) {}
            state.weatherLoc.markers = state.weatherLoc.markers.filter((x) => x !== m);
            _renderPolygonLine();
            try {
              m.closePopup();
            } catch (e) {}
          };
        }
      }, 0);
    });
    state.weatherLoc.markers.push(m);
    _renderPolygonLine();
  }

  async function openWeatherLocEdit(id) {
    state.weatherLoc.editingId = id || null;
    if (weatherLocEditResult) weatherLocEditResult.textContent = "";
    setScreen("weatherLocEdit");

    const locs = loadWeatherLocations();
    const existing = id ? locs.find((x) => x.id === id) : null;
    if (weatherLocName) weatherLocName.value = existing ? (existing.name || "") : "";

    await _ensureWeatherLocation();
    const base = existing ? _centroid(existing.polygon) : { lat: state.weather.lat, lon: state.weather.lon };
    const poly = existing && Array.isArray(existing.polygon) && existing.polygon.length >= 3 ? existing.polygon : _defaultSquare(base);

    _clearMap();
    const L = _ensureLeaflet();
    if (!weatherMapEl) throw new Error("Нет контейнера карты");

    state.weatherLoc.map = L.map(weatherMapEl, { zoomControl: false }).setView([base.lat, base.lon], 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(state.weatherLoc.map);

    for (const p of poly) {
      _addMarker(Number(p.lat), Number(p.lon));
    }

    const bb = _bbox(poly);
    if (bb) {
      try {
        state.weatherLoc.map.fitBounds(
          [
            [bb.minLat, bb.minLon],
            [bb.maxLat, bb.maxLon],
          ],
          { padding: [18, 18] }
        );
      } catch (e) {}
    }

    setTimeout(() => {
      try {
        state.weatherLoc.map.invalidateSize();
      } catch (e) {}
    }, 120);
  }

  function _getEditingPolygon() {
    return state.weatherLoc.markers.map((m) => {
      const ll = m.getLatLng();
      return { lat: ll.lat, lon: ll.lng };
    });
  }

  async function saveWeatherLocFromEditor() {
    const name = String((weatherLocName && weatherLocName.value) || "").trim();
    if (!name) {
      if (weatherLocEditResult) weatherLocEditResult.textContent = "Введите название";
      return;
    }
    const poly = _getEditingPolygon();
    if (!poly || poly.length < 3) {
      if (weatherLocEditResult) weatherLocEditResult.textContent = "Нужно минимум 3 пина";
      return;
    }

    const locs = loadWeatherLocations();
    const id = state.weatherLoc.editingId || _uid();
    const item = { id, name, polygon: poly, updatedAt: Date.now() };
    const next = locs.filter((x) => x.id !== id);
    next.unshift(item);
    saveWeatherLocations(next);

    if (weatherLocEditResult) weatherLocEditResult.textContent = "Сохранено";
    await openWeatherLocations();
  }

  async function openWeatherLocView(id) {
    state.weatherLoc.viewingId = id;
    setScreen("weatherLocView");
    if (weatherViewForecast) weatherViewForecast.innerHTML = "";

    const locs = loadWeatherLocations();
    const loc = locs.find((x) => x.id === id);
    if (!loc) {
      if (weatherViewTitle) weatherViewTitle.textContent = "Локация не найдена";
      return;
    }

    if (weatherViewTitle) weatherViewTitle.textContent = escapeHtml(loc.name || "Погода");
    if (weatherViewPlace) weatherViewPlace.textContent = loc.name || "Локация";
    if (weatherViewTemp) weatherViewTemp.textContent = "—";
    if (weatherViewDesc) weatherViewDesc.textContent = "Загрузка…";
    if (weatherViewPrecip) weatherViewPrecip.textContent = "—";
    if (weatherViewUpdated) weatherViewUpdated.textContent = "";

    const { lat, lon } = _centroid(loc.polygon);
    try {
      const cur = await _fetchWeatherCurrent(lat, lon);
      if (weatherViewCard) {
        weatherViewCard.classList.remove("weather--rain", "weather--snow", "weather--clouds");
        weatherViewCard.classList.add("weather--clouds");
        const kind = _weatherKind(cur.wc);
        const hasPrecip = cur.p != null && cur.p > 0.05;
        if (kind === "snow" || (hasPrecip && cur.t != null && cur.t <= 0)) weatherViewCard.classList.add("weather--snow");
        else if (kind === "rain" || hasPrecip) weatherViewCard.classList.add("weather--rain");
      }
      if (weatherViewTemp) weatherViewTemp.textContent = cur.t == null ? "—" : `${cur.t}°`;
      if (weatherViewDesc) weatherViewDesc.textContent = _weatherCodeText(cur.wc);
      if (weatherViewPrecip) weatherViewPrecip.textContent = cur.p == null ? "Осадки: —" : `Осадки: ${cur.p.toFixed(1)} мм`;
      if (weatherViewUpdated) weatherViewUpdated.textContent = `Обновлено: ${_fmtTime(Date.now())}`;
    } catch (e) {
      if (weatherViewDesc) weatherViewDesc.textContent = "Погода недоступна";
    }

    try {
      const rows = await _fetchWeather24h(lat, lon);
      if (weatherViewForecast) {
        weatherViewForecast.innerHTML = "";
        for (const r of rows) {
          const d = new Date(r.ts);
          const hh = String(d.getHours()).padStart(2, "0");
          const mm = String(d.getMinutes()).padStart(2, "0");
          const time = `${hh}:${mm}`;
          const pr = r.precip != null ? `${r.precip.toFixed(1)} мм` : "—";
          const pp = r.prob != null ? `${Math.round(r.prob)}%` : "—";
          const t = r.t == null ? "—" : `${r.t}°`;
          const el = document.createElement("div");
          el.className = "forecastRow";
          el.innerHTML = `
            <div class="forecastRow__left">
              <div class="forecastRow__t">${escapeHtml(time)} · ${escapeHtml(t)}</div>
              <div class="forecastRow__d">${escapeHtml(_weatherCodeText(r.wc))}</div>
            </div>
            <div class="forecastRow__right">
              <div>Осадки: ${escapeHtml(pr)}</div>
              <div>Вероятн.: ${escapeHtml(pp)}</div>
            </div>
          `;
          weatherViewForecast.appendChild(el);
        }
      }
    } catch (e) {
      if (weatherViewForecast) weatherViewForecast.textContent = "Прогноз недоступен";
    }
  }

  function deleteWeatherLoc(id) {
    const locs = loadWeatherLocations();
    saveWeatherLocations(locs.filter((x) => x.id !== id));
  }

  function _weatherCodeText(code) {
    const c = Number(code);
    if (c === 0) return "Ясно";
    if (c === 1 || c === 2) return "Малооблачно";
    if (c === 3) return "Облачно";
    if (c === 45 || c === 48) return "Туман";
    if (c === 51 || c === 53 || c === 55) return "Морось";
    if (c === 56 || c === 57) return "Морось (замерз.)";
    if (c === 61 || c === 63 || c === 65) return "Дождь";
    if (c === 66 || c === 67) return "Ледяной дождь";
    if (c === 71 || c === 73 || c === 75) return "Снег";
    if (c === 77) return "Снег";
    if (c === 80 || c === 81 || c === 82) return "Ливень";
    if (c === 85 || c === 86) return "Снегопад";
    if (c === 95) return "Гроза";
    if (c === 96 || c === 99) return "Гроза";
    return "Погода";
  }

  function _weatherKind(code) {
    const c = Number(code);
    // Open-Meteo WMO codes
    if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99].includes(c)) return "rain";
    if ([71, 73, 75, 77, 85, 86].includes(c)) return "snow";
    return "none";
  }

  async function _reverseGeocode(lat, lon) {
    try {
      const url = `https://geocoding-api.open-meteo.com/v1/reverse?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lon)}&language=ru&count=1`;
      const res = await fetch(url, { method: "GET" });
      const data = await res.json().catch(() => null);
      const r = data && data.results && data.results[0] ? data.results[0] : null;
      const name = r ? (r.city || r.name || r.admin1 || "") : "";
      return String(name || "");
    } catch (e) {
      return "";
    }
  }

  async function _ensureWeatherLocation() {
    if (state.weather.lat != null && state.weather.lon != null) return;

    try {
      const cached = localStorage.getItem(_LS_WEATHER_GEO);
      if (cached) {
        const obj = JSON.parse(cached);
        if (obj && obj.status === "denied") {
          state.weather.lat = 55.7558;
          state.weather.lon = 37.6173;
          return;
        }
        if (obj && obj.status === "granted" && obj.lat != null && obj.lon != null) {
          state.weather.lat = Number(obj.lat);
          state.weather.lon = Number(obj.lon);
          return;
        }
      }
    } catch (e) {}

    try {
      if (navigator.geolocation) {
        await new Promise((resolve) => {
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              state.weather.lat = Number(pos.coords.latitude);
              state.weather.lon = Number(pos.coords.longitude);
              try {
                localStorage.setItem(_LS_WEATHER_GEO, JSON.stringify({ status: "granted", lat: state.weather.lat, lon: state.weather.lon, ts: Date.now() }));
              } catch (e) {}
              resolve();
            },
            () => {
              try {
                localStorage.setItem(_LS_WEATHER_GEO, JSON.stringify({ status: "denied", ts: Date.now() }));
              } catch (e) {}
              resolve();
            },
            { enableHighAccuracy: false, timeout: 2500, maximumAge: 10 * 60 * 1000 }
          );
        });
      }
    } catch (e) {}

    if (state.weather.lat == null || state.weather.lon == null) {
      state.weather.lat = 55.7558;
      state.weather.lon = 37.6173;
    }
  }

  function _setWeatherLoading() {
    if (weatherPlace) weatherPlace.textContent = state.weather.place || "—";
    if (weatherTemp) weatherTemp.textContent = "—";
    if (weatherDesc) weatherDesc.textContent = "Загрузка…";
    if (weatherPrecip) weatherPrecip.textContent = "—";
    if (weatherUpdated) weatherUpdated.textContent = "";
  }

  async function refreshWeather() {
    if (!weatherTemp || !weatherDesc) return;
    try {
      if (weatherCard && !weatherCard.classList.contains("weather--clouds")) {
        weatherCard.classList.add("weather--clouds");
      }
    } catch (e) {}
    const now = Date.now();
    if (state.weather.lastTs && now - state.weather.lastTs < 30 * 1000) return;
    state.weather.lastTs = now;
    _setWeatherLoading();

    await _ensureWeatherLocation();
    const lat = state.weather.lat;
    const lon = state.weather.lon;
    if (!state.weather.place) {
      const place = await _reverseGeocode(lat, lon);
      state.weather.place = place || "Текущее место";
      if (weatherPlace) weatherPlace.textContent = state.weather.place;
    }

    try {
      const url = `https://api.open-meteo.com/v1/forecast?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lon)}&current=temperature_2m,precipitation,weather_code&timezone=auto`;
      const res = await fetch(url, { method: "GET" });
      const data = await res.json().catch(() => null);
      const cur = data && data.current ? data.current : null;
      const t = cur && cur.temperature_2m != null ? Math.round(Number(cur.temperature_2m)) : null;
      const p = cur && cur.precipitation != null ? Number(cur.precipitation) : null;
      const wc = cur && cur.weather_code != null ? Number(cur.weather_code) : null;

      if (weatherCard) {
        weatherCard.classList.remove("weather--rain", "weather--snow", "weather--clouds");
        weatherCard.classList.add("weather--clouds");

        const kind = _weatherKind(wc);
        const hasPrecip = p != null && p > 0.05;
        if (kind === "snow" || (hasPrecip && t != null && t <= 0)) weatherCard.classList.add("weather--snow");
        else if (kind === "rain" || hasPrecip) weatherCard.classList.add("weather--rain");
      }

      if (weatherPlace) weatherPlace.textContent = state.weather.place || "—";
      if (weatherTemp) weatherTemp.textContent = t == null ? "—" : `${t}°`;
      if (weatherDesc) weatherDesc.textContent = _weatherCodeText(wc);
      if (weatherPrecip) weatherPrecip.textContent = p == null ? "Осадки: —" : `Осадки: ${p.toFixed(1)} мм`;
      if (weatherUpdated) weatherUpdated.textContent = `Обновлено: ${_fmtTime(Date.now())}`;
    } catch (e) {
      if (weatherCard) weatherCard.classList.remove("weather--rain", "weather--snow");
      if (weatherDesc) weatherDesc.textContent = "Погода недоступна";
      if (weatherUpdated) weatherUpdated.textContent = "";
    }
  }

  function escapeHtml(s) {
    return (s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function _uid() {
    return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  }

  function loadWeatherLocations() {
    try {
      const raw = localStorage.getItem(_LS_WEATHER_LOCS);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) {
      return [];
    }
  }

  function saveWeatherLocations(list) {
    try {
      localStorage.setItem(_LS_WEATHER_LOCS, JSON.stringify(list || []));
    } catch (e) {}
  }

  function _centroid(points) {
    const pts = Array.isArray(points) ? points : [];
    if (!pts.length) return { lat: 55.7558, lon: 37.6173 };
    let lat = 0;
    let lon = 0;
    for (const p of pts) {
      lat += Number(p.lat) || 0;
      lon += Number(p.lon) || 0;
    }
    return { lat: lat / pts.length, lon: lon / pts.length };
  }

  function _bbox(points) {
    const pts = Array.isArray(points) ? points : [];
    let minLat = 90,
      maxLat = -90,
      minLon = 180,
      maxLon = -180;
    for (const p of pts) {
      const la = Number(p.lat);
      const lo = Number(p.lon);
      if (!isFinite(la) || !isFinite(lo)) continue;
      minLat = Math.min(minLat, la);
      maxLat = Math.max(maxLat, la);
      minLon = Math.min(minLon, lo);
      maxLon = Math.max(maxLon, lo);
    }
    if (!isFinite(minLat) || !isFinite(maxLat) || !isFinite(minLon) || !isFinite(maxLon)) return null;
    return { minLat, maxLat, minLon, maxLon };
  }

  function _defaultSquare(center) {
    const cLat = Number(center.lat) || 55.7558;
    const cLon = Number(center.lon) || 37.6173;
    const d = 0.0045;
    return [
      { lat: cLat + d, lon: cLon - d },
      { lat: cLat + d, lon: cLon + d },
      { lat: cLat - d, lon: cLon + d },
      { lat: cLat - d, lon: cLon - d },
    ];
  }

  async function _fetchWeatherCurrent(lat, lon) {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lon)}&current=temperature_2m,precipitation,weather_code&timezone=auto`;
    const res = await fetch(url, { method: "GET" });
    const data = await res.json().catch(() => null);
    const cur = data && data.current ? data.current : null;
    const t = cur && cur.temperature_2m != null ? Math.round(Number(cur.temperature_2m)) : null;
    const p = cur && cur.precipitation != null ? Number(cur.precipitation) : null;
    const wc = cur && cur.weather_code != null ? Number(cur.weather_code) : null;
    return { t, p, wc };
  }

  async function _fetchWeather24h(lat, lon) {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lon)}&hourly=temperature_2m,precipitation,precipitation_probability,weather_code&forecast_days=2&timezone=auto`;
    const res = await fetch(url, { method: "GET" });
    const data = await res.json().catch(() => null);
    const h = data && data.hourly ? data.hourly : null;
    const times = (h && h.time) || [];
    const t2 = (h && h.temperature_2m) || [];
    const pr = (h && h.precipitation) || [];
    const pp = (h && h.precipitation_probability) || [];
    const wc = (h && h.weather_code) || [];
    const out = [];
    const now = Date.now();
    for (let i = 0; i < times.length; i++) {
      const ts = Date.parse(times[i]);
      if (!isFinite(ts)) continue;
      if (ts < now - 30 * 60 * 1000) continue;
      out.push({
        ts,
        time: times[i],
        t: t2[i] != null ? Math.round(Number(t2[i])) : null,
        precip: pr[i] != null ? Number(pr[i]) : null,
        prob: pp[i] != null ? Number(pp[i]) : null,
        wc: wc[i] != null ? Number(wc[i]) : null,
      });
      if (out.length >= 24) break;
    }
    return out;
  }

  function showError(err) {
    elErrorBox.hidden = false;
    elErrorText.textContent = String(err && err.message ? err.message : err);
  }

  function roleLabel(role) {
    const r = (role || "").toLowerCase();
    if (r === "admin") return "Администратор";
    if (r === "brigadier") return "Бригадир";
    if (r === "it") return "IT";
    if (r === "tim") return "TIM";
    return "Сотрудник";
  }

  function setAvatar(name) {
    const n = (name || "").trim();
    const letter = n ? n[0].toUpperCase() : "T";
    elAvatar.textContent = letter;
  }

  function setSubtitle(text) {
    if (elSubtitle) elSubtitle.textContent = text || "";
  }

  function setScreen(name) {
    state.screen = name;
    Object.keys(screens).forEach((k) => {
      if (!screens[k]) return;
      screens[k].hidden = k !== name;
    });
    if (backBtn) backBtn.hidden = name === "dashboard";
    if (name === "dashboard") setSubtitle("");
    if (name === "otd") setSubtitle("");
    if (name === "stats") setSubtitle("");
    if (name === "settings") setSubtitle("");
    if (name === "brig") setSubtitle("");
    if (name === "weatherLocations") setSubtitle("");
    if (name === "weatherLocEdit") setSubtitle("");
    if (name === "weatherLocView") setSubtitle("");

    // если выходим из редактора карты — чистим Leaflet, чтобы не было утечек
    try {
      if (name !== "weatherLocEdit") {
        _clearMap();
      }
    } catch (e) {}
  }

  function apiHeaders() {
    const h = { "Content-Type": "application/json" };
    if (state.initData) {
      h["X-Telegram-InitData"] = state.initData;
      h["Authorization"] = "tma " + state.initData;
    }
    return h;
  }

  async function apiGet(path) {
    const res = await fetch(path, { method: "GET", headers: apiHeaders() });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data) throw new Error((data && data.error) || `HTTP ${res.status}`);
    return data;
  }

  async function apiPost(path, body) {
    const payload = Object.assign({}, body || {});
    if (state.initData && !payload.initData) payload.initData = state.initData;
    const res = await fetch(path, { method: "POST", headers: apiHeaders(), body: JSON.stringify(payload) });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data) throw new Error((data && data.error) || `HTTP ${res.status}`);
    return data;
  }

  function _fillSelect(selectEl, values, placeholder) {
    if (!selectEl) return;
    selectEl.innerHTML = "";
    const p = document.createElement("option");
    p.value = "";
    p.textContent = placeholder || "Выберите";
    selectEl.appendChild(p);
    (values || []).forEach((v) => {
      const opt = document.createElement("option");
      if (v && typeof v === "object") {
        opt.value = String(v.value != null ? v.value : (v.id != null ? v.id : ""));
        opt.textContent = String(v.label != null ? v.label : (v.title != null ? v.title : (v.name != null ? v.name : opt.value)));
      } else {
        opt.value = String(v);
        opt.textContent = String(v);
      }
      selectEl.appendChild(opt);
    });
  }

  async function ensureDictionaries() {
    if (state.dictionaries) return state.dictionaries;
    const d = await apiGet("/api/dictionaries");
    state.dictionaries = d;
    return d;
  }

  async function loadMachineItems(kindId) {
    const data = await apiGet(`/api/machine/items?kind_id=${encodeURIComponent(kindId)}`);
    const items = (data && data.items) || [];
    return items.map((it) => ({ value: String(it.id), label: String(it.name || "—") }));
  }

  function _setHidden(el, hidden) {
    if (!el) return;
    el.hidden = !!hidden;
  }

  function _resetOtdDynamic() {
    state.otd.machineKind = null;
    state.otd.machineMode = "list";
    if (otdMachineKind) otdMachineKind.value = "";
    if (otdMachineName) otdMachineName.value = "";
    if (otdActivity) otdActivity.value = "";
    if (otdCrop) otdCrop.value = "";
    if (otdLocation) otdLocation.value = "";
    if (otdTrips) otdTrips.value = "";
  }

  async function applyOtdWorkType() {
    const d = await ensureDictionaries();
    const wt = (otdWorkType && otdWorkType.value) || "";
    state.otd.workType = wt;

    _resetOtdDynamic();

    if (wt === "tech") {
      _setHidden(otdMachineKindWrap, false);
      _setHidden(otdMachineNameWrap, false);
      _setHidden(otdTripsWrap, true);

      const kinds = (d.machine_kinds || []).map((k) => ({ value: String(k.id), label: String(k.title || "—"), mode: k.mode || "list" }));
      _fillSelect(otdMachineKind, kinds, "Выберите технику");

      // activity will be filled after machine kind/name selection
      _fillSelect(otdActivity, (d.otd && d.otd.tractor_works) || [], "Выберите работу техники");
      _fillSelect(otdLocation, (d.otd && d.otd.fields) || [], "Выберите поле");
      _fillSelect(otdCrop, (d.otd && d.otd.crops) || [], "Выберите культуру");
      return;
    }

    if (wt === "hand") {
      _setHidden(otdMachineKindWrap, true);
      _setHidden(otdMachineNameWrap, true);
      _setHidden(otdTripsWrap, true);

      _fillSelect(otdActivity, (d.otd && d.otd.hand_works) || [], "Выберите вид работы");
      _fillSelect(otdLocation, (d.otd && d.otd.fields) || [], "Выберите локацию");
      _fillSelect(otdCrop, (d.otd && d.otd.crops) || [], "Выберите культуру");
      return;
    }

    // not selected
    _setHidden(otdMachineKindWrap, true);
    _setHidden(otdMachineNameWrap, true);
    _setHidden(otdTripsWrap, true);
    _fillSelect(otdActivity, [], "Сначала выберите тип работы");
    _fillSelect(otdLocation, [], "Сначала выберите тип работы");
    _fillSelect(otdCrop, [], "Сначала выберите тип работы");
  }

  async function onOtdMachineKindChange() {
    const d = await ensureDictionaries();
    const raw = (otdMachineKind && otdMachineKind.value) || "";
    const kindId = raw ? Number(raw) : 0;
    const kind = (d.machine_kinds || []).find((k) => String(k.id) === String(raw)) || null;
    state.otd.machineKind = kind;
    state.otd.machineMode = (kind && (kind.mode || "list")) || "list";

    if (state.otd.machineMode === "single") {
      // KamAZ-style: no machine name picker, show trips and use kamaz cargo list
      _setHidden(otdMachineNameWrap, true);
      _setHidden(otdTripsWrap, false);
      _fillSelect(otdActivity, ["КамАЗ"], "КамАЗ");
      if (otdActivity) otdActivity.value = "КамАЗ";
      _fillSelect(otdCrop, (d.otd && d.otd.kamaz_cargo) || [], "Выберите груз");
      _fillSelect(otdLocation, (d.otd && d.otd.fields) || [], "Где погружались?");
      return;
    }

    _setHidden(otdMachineNameWrap, false);
    _setHidden(otdTripsWrap, true);
    const items = kindId ? await loadMachineItems(kindId) : [];
    _fillSelect(otdMachineName, items, "Выберите технику");
    // normal tractor work
    _fillSelect(otdActivity, (d.otd && d.otd.tractor_works) || [], "Выберите работу техники");
    _fillSelect(otdCrop, (d.otd && d.otd.crops) || [], "Выберите культуру");
    _fillSelect(otdLocation, (d.otd && d.otd.fields) || [], "Выберите поле");
  }

  async function openOtd() {
    setScreen("otd");
    otdResult.textContent = "";
    // default date = today
    try {
      const now = new Date();
      const yyyy = now.getFullYear();
      const mm = String(now.getMonth() + 1).padStart(2, "0");
      const dd = String(now.getDate()).padStart(2, "0");
      if (otdDate && !otdDate.value) otdDate.value = `${yyyy}-${mm}-${dd}`;
    } catch (e) {}
    try {
      const d = await ensureDictionaries();
      // setup defaults for OTD
      if (otdWorkType && !otdWorkType.value) otdWorkType.value = "";
      _fillSelect(otdMachineKind, (d.machine_kinds || []).map((k) => ({ value: String(k.id), label: String(k.title || "—") })), "Выберите технику");
      _fillSelect(otdMachineName, [], "Сначала выберите тип техники");
      _fillSelect(otdActivity, [], "Сначала выберите тип работы");
      _fillSelect(otdCrop, [], "Сначала выберите тип работы");
      _fillSelect(otdLocation, [], "Сначала выберите тип работы");
      _setHidden(otdMachineKindWrap, true);
      _setHidden(otdMachineNameWrap, true);
      _setHidden(otdTripsWrap, true);

      if (otdWorkType) {
        otdWorkType.onchange = () => {
          applyOtdWorkType().catch(() => {});
        };
      }
      if (otdMachineKind) {
        otdMachineKind.onchange = () => {
          onOtdMachineKindChange().catch(() => {});
        };
      }

      // start with current selection
      await applyOtdWorkType();
    } catch (e) {
      otdResult.textContent = "Не удалось загрузить справочники: " + String(e.message || e);
    }
  }

  async function submitOtd() {
    if (!otdResult) return;
    otdResult.textContent = "";
    const work_date = (otdDate && otdDate.value) || "";
    const hours = (otdHours && otdHours.value) || "";
    const activity = (otdActivity && otdActivity.value) || "";
    const crop = (otdCrop && otdCrop.value) || "";
    const location = (otdLocation && otdLocation.value) || "";
    const trips = (otdTrips && otdTrips.value) || "";
    const wt = (otdWorkType && otdWorkType.value) || "";
    const kind = state.otd.machineKind;
    const machine_mode = state.otd.machineMode || "list";
    const machine_type = wt === "hand" ? "Ручная" : (kind && kind.title ? String(kind.title) : "");
    let machine_name = (otdMachineName && otdMachineName.value) || "";

    try {
      // Determine machine name / mode
      if (wt === "tech" && kind && (kind.mode || "list") === "single") {
        // КамАЗ: machine_name = title, trips required
        machine_name = kind.title || "КамАЗ";
      }

      const data = await apiPost("/api/report", {
        work_date,
        hours: hours ? Number(hours) : hours,
        activity,
        crop,
        machine_mode,
        machine_type,
        machine_name: machine_name || null,
        location: location || "—",
        location_grp: location ? "поля" : "—",
        activity_grp: wt === "hand" ? "ручная" : "техника",
        trips: trips ? Number(trips) : (machine_mode === "single" ? 0 : null),
      });
      otdResult.textContent = "Сохранено";
      try {
        if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.notificationOccurred === "function") {
          tg.HapticFeedback.notificationOccurred("success");
        }
      } catch (e) {}
      // обновим дашборд статистики
      try {
        await refreshDashboardStats();
      } catch (e) {}
      return data;
    } catch (e) {
      otdResult.textContent = "Ошибка: " + String(e.message || e);
      try {
        if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.notificationOccurred === "function") {
          tg.HapticFeedback.notificationOccurred("error");
        }
      } catch (e2) {}
    }
  }

  async function openBrigOb() {
    setScreen("brig");
    if (brigResult) brigResult.textContent = "";
    try {
      const d = await ensureDictionaries();
      _fillSelect(brigCrop, (d.brig && d.brig.crops) || [], "Выберите культуру");
      _fillSelect(brigField, (d.brig && d.brig.fields) || [], "Выберите поле");
      // default date = today
      try {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, "0");
        const dd = String(now.getDate()).padStart(2, "0");
        if (brigDate && !brigDate.value) brigDate.value = `${yyyy}-${mm}-${dd}`;
      } catch (e) {}
    } catch (e) {
      if (brigResult) brigResult.textContent = "Не удалось загрузить справочники: " + String(e.message || e);
    }
  }

  async function submitBrigOb() {
    if (!brigResult) return;
    brigResult.textContent = "";
    const work_date = (brigDate && brigDate.value) || "";
    const crop = (brigCrop && brigCrop.value) || "";
    const field = (brigField && brigField.value) || "";
    const rows = (brigRows && brigRows.value) || "";
    const workers = (brigWorkers && brigWorkers.value) || "";
    const bags = (brigBags && brigBags.value) || "";
    try {
      await apiPost("/api/brig/ob", {
        work_date,
        crop,
        field,
        rows: rows ? Number(rows) : rows,
        workers: workers ? Number(workers) : workers,
        bags: bags ? Number(bags) : bags,
      });
      brigResult.textContent = "Сохранено";
      try {
        if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.notificationOccurred === "function") {
          tg.HapticFeedback.notificationOccurred("success");
        }
      } catch (e) {}
    } catch (e) {
      brigResult.textContent = "Ошибка: " + String(e.message || e);
      try {
        if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.notificationOccurred === "function") {
          tg.HapticFeedback.notificationOccurred("error");
        }
      } catch (e2) {}
    }
  }

  async function loadStats(period) {
    if (!statsResult) return;
    statsResult.textContent = "";
    try {
      const data = await apiGet(`/api/stats?period=${encodeURIComponent(period)}`);
      statsResult.textContent = `${data.period}: ${data.total_hours} ч (${data.range.start} — ${data.range.end})`;
    } catch (e) {
      statsResult.textContent = "Ошибка: " + String(e.message || e);
    }
  }

  async function saveProfileName() {
    if (!settingsResult) return;
    settingsResult.textContent = "";
    const full_name = (settingsFullName && settingsFullName.value) || "";
    try {
      const data = await apiPost("/api/profile/name", { full_name });
      settingsResult.textContent = "Сохранено";
      if (data && data.profile && data.profile.full_name) {
        elFullName.textContent = data.profile.full_name;
        setAvatar(data.profile.full_name);
      }
      return data;
    } catch (e) {
      settingsResult.textContent = "Ошибка: " + String(e.message || e);
    }
  }

  async function refreshDashboardStats() {
    const w = await apiGet("/api/stats?period=week");
    const m = await apiGet("/api/stats?period=month");
    elWeekValue.textContent = w ? `${w.total_hours} ч` : "—";
    elWeekHint.textContent = w ? `${w.range.start} — ${w.range.end}` : "—";
    elMonthValue.textContent = m ? `${m.total_hours} ч` : "—";
    elMonthHint.textContent = m ? `${m.range.start} — ${m.range.end}` : "—";
  }

  function renderActions(actions) {
    elActions.innerHTML = "";
    (actions || []).forEach((a) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "actionBtn";

      const left = document.createElement("div");
      const label = document.createElement("div");
      label.className = "actionBtn__label";
      label.innerHTML = escapeHtml(a.title || "Действие");

      const meta = document.createElement("div");
      meta.className = "actionBtn__meta";
      meta.textContent = a.hint || "";

      left.appendChild(label);
      if (a.hint) left.appendChild(meta);

      const right = document.createElement("div");
      right.className = "actionBtn__meta";
      right.textContent = "→";

      btn.appendChild(left);
      btn.appendChild(right);

      btn.addEventListener("click", () => {
        const action = a.action;
        if (action === "otd") {
          openOtd();
          return;
        }
        if (action === "stats") {
          setScreen("stats");
          loadStats("week");
          return;
        }
        if (action === "settings") {
          setScreen("settings");
          return;
        }
        if (action === "brig_report") {
          openBrigOb();
          return;
        }
        if (action === "admin") {
          // пока нет admin UI во фронте
          if (tg && typeof tg.showAlert === "function") tg.showAlert("Админ-экран в Mini App пока не реализован");
          else alert("Админ-экран в Mini App пока не реализован");
          return;
        }
      });

      elActions.appendChild(btn);
    });
  }

  async function load() {
    try {
      if (tg) {
        tg.ready();
        // минимальная настройка цветов
        tg.expand();
      }

      state.initData = tg ? (tg.initData || "") : "";
      const data = await apiGet("/api/me");

      const fullName = data.profile && data.profile.full_name ? data.profile.full_name : "—";
      const role = data.profile && data.profile.role ? data.profile.role : "user";

      state.role = role;

      elFullName.textContent = fullName;
      elRole.textContent = roleLabel(role);
      setAvatar(fullName);

      const w = data.stats && data.stats.week ? data.stats.week : null;
      const m = data.stats && data.stats.month ? data.stats.month : null;

      elWeekValue.textContent = w ? `${w.total_hours} ч` : "—";
      elWeekHint.textContent = w ? `${w.start} — ${w.end}` : "—";

      elMonthValue.textContent = m ? `${m.total_hours} ч` : "—";
      elMonthHint.textContent = m ? `${m.start} — ${m.end}` : "—";

      renderActions(data.actions || []);

      setScreen("dashboard");

      try {
        await refreshDashboardStats();
      } catch (e) {}

      try {
        await refreshWeather();
        setInterval(() => {
          refreshWeather().catch(() => {});
        }, 5 * 60 * 1000);
      } catch (e) {}

      if (backBtn) {
        backBtn.addEventListener("click", () => {
          // простая навигация назад для новых экранов
          if (state.screen === "weatherLocEdit" || state.screen === "weatherLocView") {
            openWeatherLocations().catch(() => setScreen("weatherLocations"));
            return;
          }
          if (state.screen === "weatherLocations") {
            setScreen("dashboard");
            return;
          }
          setScreen("dashboard");
        });
      }

      if (settingsBtn) {
        settingsBtn.addEventListener("click", () => setScreen("settings"));
      }

      if (weatherCard) {
        weatherCard.addEventListener("click", () => {
          openWeatherLocations().catch(() => setScreen("weatherLocations"));
        });
      }

      if (weatherLocAdd) {
        weatherLocAdd.addEventListener("click", () => {
          openWeatherLocEdit(null).catch((e) => {
            if (weatherLocEditResult) weatherLocEditResult.textContent = String(e.message || e);
          });
        });
      }

      if (weatherPinAdd) {
        weatherPinAdd.addEventListener("click", () => {
          try {
            if (!state.weatherLoc.map) return;
            const c = state.weatherLoc.map.getCenter();
            _addMarker(Number(c.lat), Number(c.lng));
          } catch (e) {}
        });
      }

      if (weatherPinsReset) {
        weatherPinsReset.addEventListener("click", async () => {
          try {
            await _ensureWeatherLocation();
            const center = state.weatherLoc.map ? state.weatherLoc.map.getCenter() : { lat: state.weather.lat, lng: state.weather.lon };
            const base = { lat: Number(center.lat), lon: Number(center.lng) };
            const pts = _defaultSquare(base);
            // очистка слоёв и маркеров
            if (state.weatherLoc.map) {
              for (const m of state.weatherLoc.markers) {
                try {
                  state.weatherLoc.map.removeLayer(m);
                } catch (e) {}
              }
            }
            state.weatherLoc.markers = [];
            for (const p of pts) {
              _addMarker(Number(p.lat), Number(p.lon));
            }
          } catch (e) {}
        });
      }

      if (weatherLocSave) {
        weatherLocSave.addEventListener("click", () => {
          saveWeatherLocFromEditor().catch((e) => {
            if (weatherLocEditResult) weatherLocEditResult.textContent = String(e.message || e);
          });
        });
      }

      if (weatherLocDelete) {
        weatherLocDelete.addEventListener("click", () => {
          const id = state.weatherLoc.viewingId;
          if (!id) return;
          deleteWeatherLoc(id);
          openWeatherLocations().catch(() => setScreen("weatherLocations"));
        });
      }

      if (otdSubmit) {
        otdSubmit.addEventListener("click", submitOtd);
      }

      if (brigSubmit) {
        brigSubmit.addEventListener("click", submitBrigOb);
      }

      if (statsToday) statsToday.addEventListener("click", () => loadStats("today"));
      if (statsWeek) statsWeek.addEventListener("click", () => loadStats("week"));
      if (statsMonth) statsMonth.addEventListener("click", () => loadStats("month"));

      if (settingsSave) settingsSave.addEventListener("click", saveProfileName);
      if (settingsFullName && fullName && fullName !== "—") settingsFullName.value = fullName;

      const closeBtn = $("closeBtn");
      closeBtn.addEventListener("click", () => {
        if (tg) tg.close();
        else window.close();
      });

    } catch (e) {
      showError(e);
    }
  }

  load();
})();
