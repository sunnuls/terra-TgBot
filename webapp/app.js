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
  const notificationsBtn = $("notificationsBtn");
  const notificationsBadge = $("notificationsBadge");

  const weatherCard = $("weatherCard");
  const weatherPlace = $("weatherPlace");
  const weatherTemp = $("weatherTemp");
  const weatherDesc = $("weatherDesc");
  const weatherPrecip = $("weatherPrecip");
  const weatherUpdated = $("weatherUpdated");

  const weatherLocList = $("weatherLocList");
  const weatherLocAdd = $("weatherLocAdd");
  const weatherLocName = $("weatherLocName");
  const weatherLocSearch = $("weatherLocSearch");
  const weatherLocSearchResults = $("weatherLocSearchResults");
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

  const toastEl = $("toast");
  const reportViewBody = $("reportViewBody");
  const notificationsResult = $("notificationsResult");
  const notificationsList = $("notificationsList");

  const screens = {
    dashboard: $("screenDashboard"),
    otd: $("screenOtd"),
    admin: $("screenAdmin"),
    stats: $("screenStats"),
    settings: $("screenSettings"),
    brig: $("screenBrig"),
    weatherLocations: $("screenWeatherLocations"),
    weatherLocEdit: $("screenWeatherLocEdit"),
    weatherLocView: $("screenWeatherLocView"),
    reportView: $("screenReportView"),
    avatarCrop: $("screenAvatarCrop"),
    notifications: $("screenNotifications"),
  };
  const backBtn = $("backBtn");

  const otdDate = $("otdDate");
  const otdHours = $("otdHours");
  const otdWorkType = $("otdWorkType");
  const otdMachineKindWrap = $("otdMachineKindWrap");
  const otdMachineKind = $("otdMachineKind");
  const otdMachineNameWrap = $("otdMachineNameWrap");
  const otdMachineName = $("otdMachineName");
  const otdMachineOtherWrap = $("otdMachineOtherWrap");
  const otdMachineOther = $("otdMachineOther");
  const otdActivity = $("otdActivity");
  const otdActivityOtherWrap = $("otdActivityOtherWrap");
  const otdActivityOther = $("otdActivityOther");
  const otdLocation = $("otdLocation");
  const otdLocationOtherWrap = $("otdLocationOtherWrap");
  const otdLocationOther = $("otdLocationOther");
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
  const settingsAvatarFile = $("settingsAvatarFile");
  const settingsAvatarPreview = $("settingsAvatarPreview");
  const settingsAvatarPick = $("settingsAvatarPick");
  const settingsSave = $("settingsSave");
  const settingsResult = $("settingsResult");

  const avatarCropWrap = $("avatarCropWrap");
  const avatarCropCanvas = $("avatarCropCanvas");
  const avatarCropZoom = $("avatarCropZoom");
  const avatarCropCancel = $("avatarCropCancel");
  const avatarCropSave = $("avatarCropSave");
  const avatarCropResult = $("avatarCropResult");

  const brigDate = $("brigDate");
  const brigCrop = $("brigCrop");
  const brigField = $("brigField");
  const brigRows = $("brigRows");
  const brigWorkers = $("brigWorkers");
  const brigBags = $("brigBags");
  const brigSubmit = $("brigSubmit");
  const brigResult = $("brigResult");

  const adminUsername = $("adminUsername");
  const adminUserPick = $("adminUserPick");
  const adminRole = $("adminRole");
  const adminAddRole = $("adminAddRole");
  const adminExport = $("adminExport");
  const adminResult = $("adminResult");
  const adminRolesList = $("adminRolesList");

  const exportModal = $("exportModal");
  const exportModalClose = $("exportModalClose");
  const exportModalBody = $("exportModalBody");
  const exportModalBar = $("exportModalBar");

  const adminTabRoles = $("adminTabRoles");
  const adminTabLocs = $("adminTabLocs");
  const adminTabCrops = $("adminTabCrops");
  const adminTabActs = $("adminTabActs");
  const adminTabMachines = $("adminTabMachines");
  const adminTabNotify = $("adminTabNotify");
  const adminSectionRoles = $("adminSectionRoles");
  const adminSectionLocs = $("adminSectionLocs");
  const adminSectionFields = $("adminSectionFields");
  const adminSectionWare = $("adminSectionWare");
  const adminSectionCrops = $("adminSectionCrops");
  const adminSectionActs = $("adminSectionActs");
  const adminSectionMachines = $("adminSectionMachines");
  const adminSectionNotify = $("adminSectionNotify");

  const adminNotifyTitle = $("adminNotifyTitle");
  const adminNotifyBody = $("adminNotifyBody");
  const adminNotifyRoleUser = $("adminNotifyRoleUser");
  const adminNotifyRoleBrig = $("adminNotifyRoleBrig");
  const adminNotifySendAt = $("adminNotifySendAt");
  const adminNotifyScheduleBtn = $("adminNotifyScheduleBtn");
  const adminNotifySend = $("adminNotifySend");
  const adminNotifyRefresh = $("adminNotifyRefresh");
  const adminNotifyResult = $("adminNotifyResult");
  const adminNotifyScheduled = $("adminNotifyScheduled");

  const adminLocsTabFields = $("adminLocsTabFields");
  const adminLocsTabWare = $("adminLocsTabWare");
  let _adminLocsTab = "fields";

  const adminFieldsNew = $("adminFieldsNew");
  const adminFieldsAdd = $("adminFieldsAdd");
  const adminFieldsSort = $("adminFieldsSort");
  const adminFieldsResult = $("adminFieldsResult");
  const adminFieldsList = $("adminFieldsList");

  const adminWareNew = $("adminWareNew");
  const adminWareAdd = $("adminWareAdd");
  const adminWareSort = $("adminWareSort");
  const adminWareResult = $("adminWareResult");
  const adminWareList = $("adminWareList");

  const adminCropsNew = $("adminCropsNew");
  const adminCropsAdd = $("adminCropsAdd");
  const adminCropsSort = $("adminCropsSort");
  const adminCropsResult = $("adminCropsResult");
  const adminCropsList = $("adminCropsList");

  const adminActsTabTech = $("adminActsTabTech");
  const adminActsTabHand = $("adminActsTabHand");
  const adminActsNew = $("adminActsNew");
  const adminActsAdd = $("adminActsAdd");
  const adminActsSort = $("adminActsSort");
  const adminActsResult = $("adminActsResult");
  const adminActsList = $("adminActsList");

  const adminMachinesTabKinds = $("adminMachinesTabKinds");
  const adminMachinesTabItems = $("adminMachinesTabItems");
  const adminMachineKindPick = $("adminMachineKindPick");
  const adminMachinesNew = $("adminMachinesNew");
  const adminMachinesAdd = $("adminMachinesAdd");
  const adminMachinesSort = $("adminMachinesSort");
  const adminMachinesResult = $("adminMachinesResult");
  const adminMachinesList = $("adminMachinesList");

  let _adminMachinesTab = "kinds"; // kinds | items
  let _adminSelectedKindId = 0;

  let _adminActsGrp = "tech";

  let _adminSortFields = false;
  let _adminSortWare = false;
  let _adminSortCrops = false;
  let _adminSortActs = false;
  let _adminSortMachines = false;

  function _toggleBtnActive(btn, on) {
    if (!btn) return;
    btn.classList.toggle("btn--active", !!on);
    btn.classList.toggle("btn--secondary", !on);
  }

  function _isoFromDatetimeLocal(v) {
    const s = String(v || "").trim();
    if (!s) return "";
    return s.length === 16 ? (s + ":00") : s;
  }

  function _adminNotifyScheduleBtnText() {
    const v = adminNotifySendAt ? String(adminNotifySendAt.value || "").trim() : "";
    if (!v) return "Запланировать уведомление";
    return "Запланировано: " + v.replace("T", " ");
  }

  function _adminNotifySyncScheduleBtn() {
    if (!adminNotifyScheduleBtn) return;
    adminNotifyScheduleBtn.textContent = _adminNotifyScheduleBtnText();
  }

  async function refreshNotificationsBadge() {
    try {
      if (!notificationsBadge) return;
      const d = await apiGet("/api/notifications/unread");
      const n = Number((d && d.count) || 0) || 0;
      if (n > 0) {
        notificationsBadge.hidden = false;
        notificationsBadge.textContent = String(n > 99 ? "99+" : n);
      } else {
        notificationsBadge.hidden = true;
        notificationsBadge.textContent = "";
      }
    } catch (e) {
      // ignore badge errors
    }
  }

  function _renderNotifications(items) {
    if (!notificationsList) return;
    const list = document.createElement("div");
    list.className = "list";
    const arr = items || [];
    if (!arr.length) {
      const empty = document.createElement("div");
      empty.style.fontSize = "13px";
      empty.style.color = "var(--muted)";
      empty.textContent = "Нет уведомлений";
      notificationsList.innerHTML = "";
      notificationsList.appendChild(empty);
      return;
    }
    for (const it of arr) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      const isRead = !!it.is_read;
      const title = String(it.title || "Уведомление");
      const body = String(it.body || "");
      const dt = it.sent_at || it.created_at || "";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(title)}${isRead ? "" : " <span style=\"color:rgba(255,93,93,.95)\">●</span>"}</div>
          <div class="listItem__meta">${escapeHtml(dt ? _fmtDateRu(dt) : "")}</div>
        </div>
        <div class="listItem__meta">${escapeHtml(body.length > 140 ? (body.slice(0, 140) + "…") : body)}</div>
      `;
      btn.addEventListener("click", async () => {
        try {
          hapticTap();
          await apiPost("/api/notifications/read", { id: Number(it.id) });
          toast("Прочитано");
          await openNotifications();
        } catch (e) {
          toast("Ошибка", "error");
        }
      });
      list.appendChild(btn);
    }
    notificationsList.innerHTML = "";
    notificationsList.appendChild(list);
  }

  async function openNotifications() {
    setScreen("notifications");
    if (notificationsResult) notificationsResult.textContent = "Загрузка…";
    try {
      const d = await apiGet("/api/notifications?limit=80");
      if (notificationsResult) notificationsResult.textContent = "";
      _renderNotifications((d && d.items) || []);
      await refreshNotificationsBadge();
    } catch (e) {
      if (notificationsResult) notificationsResult.textContent = _ruApiError(e);
    }
  }

  function _enableListDnD(listEl, onSave) {
    if (!listEl) return;
    let dragEl = null;

    const onDragStart = (e) => {
      const row = e.currentTarget;
      dragEl = row;
      row.classList.add("listRow--dragging");
      try {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", row.getAttribute("data-id") || "");
      } catch (err) {}
    };

    const onDragEnd = (e) => {
      const row = e.currentTarget;
      row.classList.remove("listRow--dragging");
      dragEl = null;
    };

    const onDragOver = (e) => {
      e.preventDefault();
      const target = e.currentTarget;
      if (!dragEl || dragEl === target) return;
      const rect = target.getBoundingClientRect();
      const before = (e.clientY - rect.top) < rect.height / 2;
      const parent = target.parentElement;
      if (!parent) return;
      if (before) parent.insertBefore(dragEl, target);
      else parent.insertBefore(dragEl, target.nextSibling);
    };

    const onDrop = async (e) => {
      e.preventDefault();
      try {
        const rows = Array.from(listEl.querySelectorAll(".listRow--sortable"));
        const ids = rows.map((r) => r.getAttribute("data-id") || "").filter(Boolean);
        await onSave(ids);
      } catch (err) {}
    };

    const rows = Array.from(listEl.querySelectorAll(".listRow--sortable"));
    rows.forEach((row) => {
      row.draggable = true;
      row.addEventListener("dragstart", onDragStart);
      row.addEventListener("dragend", onDragEnd);
      row.addEventListener("dragover", onDragOver);
      row.addEventListener("drop", onDrop);
    });
  }

  function _collectOrderIds(listEl) {
    if (!listEl) return [];
    return Array.from(listEl.querySelectorAll(".listRow--sortable"))
      .map((r) => r.getAttribute("data-id") || "")
      .filter(Boolean);
  }

  function _moveRow(rowEl, dir) {
    if (!rowEl || !rowEl.parentElement) return;
    const parent = rowEl.parentElement;
    if (dir < 0) {
      const prev = rowEl.previousElementSibling;
      if (prev) parent.insertBefore(rowEl, prev);
    } else {
      const next = rowEl.nextElementSibling;
      if (next) parent.insertBefore(next, rowEl);
    }
  }

  function _addSortArrows(rowEl, actionsEl, listEl, onSave) {
    if (!rowEl || !actionsEl || !listEl) return;
    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.className = "btn btn--secondary btn--icon";
    upBtn.textContent = "▲";
    upBtn.title = "Вверх";
    upBtn.setAttribute("aria-label", "Вверх");

    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.className = "btn btn--secondary btn--icon";
    downBtn.textContent = "▼";
    downBtn.title = "Вниз";
    downBtn.setAttribute("aria-label", "Вниз");

    upBtn.addEventListener("click", async () => {
      try {
        _moveRow(rowEl, -1);
        await onSave(_collectOrderIds(listEl));
      } catch (e) {}
    });

    downBtn.addEventListener("click", async () => {
      try {
        _moveRow(rowEl, 1);
        await onSave(_collectOrderIds(listEl));
      } catch (e) {}
    });

    actionsEl.insertBefore(downBtn, actionsEl.firstChild);
    actionsEl.insertBefore(upBtn, actionsEl.firstChild);
  }

  function _adminSetActsGrp(grp) {
    const g = grp === "hand" ? "hand" : "tech";
    _adminActsGrp = g;
    if (adminActsTabTech) {
      adminActsTabTech.classList.toggle("btn--secondary", g !== "tech");
      adminActsTabTech.classList.toggle("btn--active", g === "tech");
    }
    if (adminActsTabHand) {
      adminActsTabHand.classList.toggle("btn--secondary", g !== "hand");
      adminActsTabHand.classList.toggle("btn--active", g === "hand");
    }
    adminRefreshActs().catch((e) => {
      if (adminActsResult) adminActsResult.textContent = _ruApiError(e);
    });
  }

  const otdDateError = $("otdDateError");
  const otdHoursError = $("otdHoursError");
  const otdWorkTypeError = $("otdWorkTypeError");
  const otdActivityError = $("otdActivityError");
  const otdActivityOtherError = $("otdActivityOtherError");
  const otdLocationError = $("otdLocationError");
  const otdLocationOtherError = $("otdLocationOtherError");
  const otdCropError = $("otdCropError");
  const otdMachineOtherError = $("otdMachineOtherError");

  const brigDateError = $("brigDateError");
  const brigCropError = $("brigCropError");
  const brigFieldError = $("brigFieldError");

  function _adminSetTab(tab) {
    const t = String(tab || "roles");
    const isRoles = t === "roles";
    const isLocs = t === "locs";
    const isCrops = t === "crops";
    const isActs = t === "acts";
    const isMachines = t === "machines";
    const isNotify = t === "notify";
    if (adminSectionRoles) adminSectionRoles.hidden = !isRoles;
    if (adminSectionLocs) adminSectionLocs.hidden = !isLocs;
    if (adminSectionCrops) adminSectionCrops.hidden = !isCrops;
    if (adminSectionActs) adminSectionActs.hidden = !isActs;
    if (adminSectionMachines) adminSectionMachines.hidden = !isMachines;
    if (adminSectionNotify) adminSectionNotify.hidden = !isNotify;

    if (adminTabRoles) {
      adminTabRoles.classList.toggle("btn--secondary", !isRoles);
      adminTabRoles.classList.toggle("btn--active", isRoles);
    }
    if (adminTabLocs) {
      adminTabLocs.classList.toggle("btn--secondary", !isLocs);
      adminTabLocs.classList.toggle("btn--active", isLocs);
    }
    if (adminTabCrops) {
      adminTabCrops.classList.toggle("btn--secondary", !isCrops);
      adminTabCrops.classList.toggle("btn--active", isCrops);
    }
    if (adminTabActs) {
      adminTabActs.classList.toggle("btn--secondary", !isActs);
      adminTabActs.classList.toggle("btn--active", isActs);
    }
    if (adminTabMachines) {
      adminTabMachines.classList.toggle("btn--secondary", !isMachines);
      adminTabMachines.classList.toggle("btn--active", isMachines);
    }
    if (adminTabNotify) {
      adminTabNotify.classList.toggle("btn--secondary", !isNotify);
      adminTabNotify.classList.toggle("btn--active", isNotify);
    }

    if (isLocs) {
      _adminSetLocsTab(_adminLocsTab);
    }
    if (isCrops) {
      adminRefreshCrops().catch((e) => {
        if (adminCropsResult) adminCropsResult.textContent = _ruApiError(e);
      });
    }
    if (isActs) {
      _adminSetActsGrp(_adminActsGrp);
    }
    if (isMachines) {
      _adminMachinesSetTab(_adminMachinesTab);
    }
    if (isNotify) {
      adminRefreshScheduledNotifications().catch((e) => {
        if (adminNotifyResult) adminNotifyResult.textContent = _ruApiError(e);
      });
    }
  }

  async function adminRefreshScheduledNotifications() {
    if (adminNotifyResult) adminNotifyResult.textContent = "";
    const d = await apiGet("/api/admin/notifications/scheduled");
    _renderScheduledNotifications((d && d.items) || []);
  }

  function _renderScheduledNotifications(items) {
    if (!adminNotifyScheduled) return;
    const arr = items || [];
    if (!arr.length) {
      adminNotifyScheduled.innerHTML = `<div style="font-size:13px; color:var(--muted)">Нет отложенных</div>`;
      return;
    }

    const list = document.createElement("div");
    list.className = "list";
    for (const it of arr) {
      const wrap = document.createElement("div");
      wrap.className = "listItem";
      wrap.style.cursor = "default";
      const title = String(it.title || "Уведомление");
      const body = String(it.body || "");
      const sendAt = String(it.send_at || "");
      const roles = String(it.target_roles || "");
      wrap.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(title)}</div>
          <div class="listItem__meta">${escapeHtml(sendAt ? _fmtDateRu(sendAt) : "")}</div>
        </div>
        <div class="listItem__meta">${escapeHtml(body.length > 160 ? (body.slice(0, 160) + "…") : body)}</div>
        <div class="listItem__meta">Роли: ${escapeHtml(roles || "—")}</div>
        <div style="display:flex; gap:8px; margin-top:10px;">
          <button class="btn btn--secondary" type="button">Изменить</button>
          <button class="btn btn--secondary" type="button">Удалить</button>
        </div>
      `;

      const btns = wrap.querySelectorAll("button");
      const editBtn = btns && btns[0] ? btns[0] : null;
      const delBtn = btns && btns[1] ? btns[1] : null;

      if (editBtn) {
        editBtn.addEventListener("click", async () => {
          try {
            const nextBody = prompt("Новый текст уведомления", body);
            if (nextBody === null) return;
            const nextSend = prompt("Новая дата ISO (пример: 2025-12-28T16:00:00) или пусто", sendAt);
            if (nextSend === null) return;
            await apiPatch(`/api/admin/notifications/${encodeURIComponent(String(it.id))}`, {
              body: String(nextBody || "").trim(),
              send_at: String(nextSend || "").trim() || null,
            });
            toast("Сохранено");
            hapticTap();
            await adminRefreshScheduledNotifications();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminNotifyResult) adminNotifyResult.textContent = _ruApiError(e);
          }
        });
      }

      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          try {
            const ok = confirm("Удалить отложенное уведомление?");
            if (!ok) return;
            await apiDelete(`/api/admin/notifications/${encodeURIComponent(String(it.id))}`);
            toast("Удалено");
            hapticTap();
            await adminRefreshScheduledNotifications();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminNotifyResult) adminNotifyResult.textContent = _ruApiError(e);
          }
        });
      }

      list.appendChild(wrap);
    }
    adminNotifyScheduled.innerHTML = "";
    adminNotifyScheduled.appendChild(list);
  }

  async function adminRefreshScheduledNotifications() {
    if (adminNotifyResult) adminNotifyResult.textContent = "";
    const d = await apiGet("/api/admin/notifications/scheduled");
    _renderScheduledNotifications((d && d.items) || []);
  }

  function _adminSetLocsTab(tab) {
    const t = tab === "ware" ? "ware" : "fields";
    _adminLocsTab = t;
    if (adminLocsTabFields) {
      adminLocsTabFields.classList.toggle("btn--secondary", t !== "fields");
      adminLocsTabFields.classList.toggle("btn--active", t === "fields");
    }
    if (adminLocsTabWare) {
      adminLocsTabWare.classList.toggle("btn--secondary", t !== "ware");
      adminLocsTabWare.classList.toggle("btn--active", t === "ware");
    }
    if (adminSectionFields) adminSectionFields.hidden = t !== "fields";
    if (adminSectionWare) adminSectionWare.hidden = t !== "ware";
    if (t === "fields") {
      adminRefreshFields().catch((e) => {
        if (adminFieldsResult) adminFieldsResult.textContent = _ruApiError(e);
      });
    } else {
      adminRefreshWare().catch((e) => {
        if (adminWareResult) adminWareResult.textContent = _ruApiError(e);
      });
    }
  }

  function _adminMachinesSetTab(tab) {
    const t = tab === "items" ? "items" : "kinds";
    _adminMachinesTab = t;
    if (adminMachinesTabKinds) {
      adminMachinesTabKinds.classList.toggle("btn--secondary", t !== "kinds");
      adminMachinesTabKinds.classList.toggle("btn--active", t === "kinds");
    }
    if (adminMachinesTabItems) {
      adminMachinesTabItems.classList.toggle("btn--secondary", t !== "items");
      adminMachinesTabItems.classList.toggle("btn--active", t === "items");
    }
    // selector нужен только для вкладки "Единицы"
    if (adminMachineKindPick) adminMachineKindPick.hidden = t !== "items";
    if (adminMachinesNew) adminMachinesNew.placeholder = (t === "kinds") ? "Новый тип" : "Новая единица";
    adminRefreshMachines().catch((e) => {
      if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
    });
  }

  function _adminFillMachineKindPick(items) {
    if (!adminMachineKindPick) return;
    const prev = String(adminMachineKindPick.value || "");
    adminMachineKindPick.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "Выберите тип техники";
    adminMachineKindPick.appendChild(opt0);
    for (const it of (items || [])) {
      const o = document.createElement("option");
      o.value = String(it.id);
      const mode = String(it.mode || "list") === "single" ? "single" : "list";
      o.textContent = `${String(it.title || "—")} (${mode})`;
      adminMachineKindPick.appendChild(o);
    }
    if (prev && Array.from(adminMachineKindPick.options).some((o) => o.value === prev)) {
      adminMachineKindPick.value = prev;
      _adminSelectedKindId = Number(prev || 0);
    }
  }

  function _renderAdminMachineKinds(items) {
    if (!adminMachinesList) return;
    const list = document.createElement("div");
    list.className = "list";
    for (const it of (items || [])) {
      const row = document.createElement("div");
      row.classList.add("listRow--sortable");
      row.setAttribute("data-id", String(it.id));
      row.style.display = "grid";
      row.style.gridTemplateColumns = "1fr auto";
      row.style.gap = "10px";
      row.style.alignItems = "center";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      const mode = String(it.mode || "list") === "single" ? "single" : "list";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(String(it.title || "—"))}</div>
          <div class="listItem__meta">${escapeHtml(mode)}</div>
        </div>
      `;

      const actions = document.createElement("div");
      actions.style.display = "grid";
      actions.style.gridTemplateColumns = (_adminSortMachines && _adminMachinesTab === "kinds") ? "auto auto" : "auto auto auto";
      actions.style.gap = "8px";

      if (_adminSortMachines && _adminMachinesTab === "kinds") {
        _addSortArrows(row, actions, list, async (ids) => {
          await apiPost("/api/admin/machine/kinds/reorder", { ids });
          toast("Порядок сохранён");
          hapticTap();
        });
      } else {
        const renameBtn = document.createElement("button");
        renameBtn.type = "button";
        renameBtn.className = "btn btn--secondary";
        renameBtn.textContent = "✏️";
        renameBtn.title = "Переименовать";
        renameBtn.setAttribute("aria-label", "Переименовать");

        const modeBtn = document.createElement("button");
        modeBtn.type = "button";
        modeBtn.className = "btn btn--secondary";
        modeBtn.textContent = (mode === "single") ? "Сделать list" : "Сделать single";

        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "btn btn--secondary";
        delBtn.textContent = "🗑️";
        delBtn.title = "Удалить";
        delBtn.setAttribute("aria-label", "Удалить");

        renameBtn.addEventListener("click", async () => {
          try {
            const current = String(it.title || "");
            const p = prompt("Новое название типа", current);
            if (p === null) return;
            const next = String(p || "").trim();
            if (!next) return;
            await apiPatch(`/api/admin/machine/kinds/${encodeURIComponent(String(it.id))}`, { title: next });
            toast("Сохранено");
            hapticTap();
            await adminRefreshMachines();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
          }
        });

        modeBtn.addEventListener("click", async () => {
          try {
            const nextMode = (mode === "single") ? "list" : "single";
            await apiPatch(`/api/admin/machine/kinds/${encodeURIComponent(String(it.id))}`, { mode: nextMode });
            toast("Сохранено");
            hapticTap();
            await adminRefreshMachines();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
          }
        });

        delBtn.addEventListener("click", async () => {
          try {
            const name = String(it.title || "");
            const ok = confirm(`Удалить тип «${name}» и все связанные единицы?`);
            if (!ok) return;
            await apiDelete(`/api/admin/machine/kinds/${encodeURIComponent(String(it.id))}`);
            toast("Удалено");
            hapticTap();
            if (_adminSelectedKindId === Number(it.id)) _adminSelectedKindId = 0;
            await adminRefreshMachines();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
          }
        });

        actions.appendChild(renameBtn);
        actions.appendChild(modeBtn);
        actions.appendChild(delBtn);
      }
      row.appendChild(btn);
      row.appendChild(actions);
      list.appendChild(row);
    }
    adminMachinesList.innerHTML = "";
    adminMachinesList.appendChild(list);

    if (_adminSortMachines && _adminMachinesTab === "kinds") {
      _enableListDnD(list, async (ids) => {
        await apiPost("/api/admin/machine/kinds/reorder", { ids });
        toast("Порядок сохранён");
        hapticTap();
      });
    }
  }

  function _renderAdminMachineItems(items) {
    if (!adminMachinesList) return;
    const list = document.createElement("div");
    list.className = "list";
    for (const it of (items || [])) {
      const row = document.createElement("div");
      row.classList.add("listRow--sortable");
      row.setAttribute("data-id", String(it.id));
      row.style.display = "grid";
      row.style.gridTemplateColumns = "1fr auto";
      row.style.gap = "10px";
      row.style.alignItems = "center";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(String(it.name || "—"))}</div>
        </div>
      `;

      const actions = document.createElement("div");
      actions.style.display = "grid";
      actions.style.gridTemplateColumns = (_adminSortMachines && _adminMachinesTab === "items") ? "auto auto" : "auto auto";
      actions.style.gap = "8px";

      if (_adminSortMachines && _adminMachinesTab === "items") {
        const kindId = _adminSelectedKindId || (adminMachineKindPick ? Number(adminMachineKindPick.value || 0) : 0);
        _addSortArrows(row, actions, list, async (ids) => {
          await apiPost("/api/admin/machine/items/reorder", { kind_id: kindId, ids });
          toast("Порядок сохранён");
          hapticTap();
        });
      } else {
        const renameBtn = document.createElement("button");
        renameBtn.type = "button";
        renameBtn.className = "btn btn--secondary";
        renameBtn.textContent = "✏️";
        renameBtn.title = "Переименовать";
        renameBtn.setAttribute("aria-label", "Переименовать");

        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "btn btn--secondary";
        delBtn.textContent = "🗑️";
        delBtn.title = "Удалить";
        delBtn.setAttribute("aria-label", "Удалить");

        renameBtn.addEventListener("click", async () => {
          try {
            const current = String(it.name || "");
            const p = prompt("Новое название единицы", current);
            if (p === null) return;
            const next = String(p || "").trim();
            if (!next) return;
            await apiPatch(`/api/admin/machine/items/${encodeURIComponent(String(it.id))}`, { name: next });
            toast("Сохранено");
            hapticTap();
            await adminRefreshMachines();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
          }
        });

        delBtn.addEventListener("click", async () => {
          try {
            const name = String(it.name || "");
            const ok = confirm(`Удалить «${name}»?`);
            if (!ok) return;
            await apiDelete(`/api/admin/machine/items/${encodeURIComponent(String(it.id))}`);
            toast("Удалено");
            hapticTap();
            await adminRefreshMachines();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
          }
        });

        actions.appendChild(renameBtn);
        actions.appendChild(delBtn);
      }
      row.appendChild(btn);
      row.appendChild(actions);
      list.appendChild(row);
    }
    adminMachinesList.innerHTML = "";
    adminMachinesList.appendChild(list);
  }

  async function adminRefreshMachines() {
    if (adminMachinesResult) adminMachinesResult.textContent = "";
    const kindsUrl = "/api/admin/machine/kinds?limit=300";
    if (_adminMachinesTab === "kinds") {
      const data = await apiGet(kindsUrl);
      const kinds = (data && data.items) || [];
      _adminFillMachineKindPick(kinds);
      _renderAdminMachineKinds(kinds);
      return;
    }

    // items
    const dataKinds = await apiGet("/api/admin/machine/kinds?limit=300");
    const kinds = (dataKinds && dataKinds.items) || [];
    _adminFillMachineKindPick(kinds);

    const kindId = adminMachineKindPick ? Number(adminMachineKindPick.value || 0) : (_adminSelectedKindId || 0);
    _adminSelectedKindId = kindId;
    if (!kindId) {
      if (adminMachinesList) adminMachinesList.innerHTML = "";
      if (adminMachinesResult) adminMachinesResult.textContent = "Выберите тип техники";
      return;
    }
    const itemsUrl = `/api/admin/machine/items?kind_id=${encodeURIComponent(String(kindId))}&limit=300`;
    const dataItems = await apiGet(itemsUrl);
    _renderAdminMachineItems((dataItems && dataItems.items) || []);
  }

  function _setFieldError(el, msg) {
    if (!el) return;
    const m = String(msg || "").trim();
    if (!m) {
      el.hidden = true;
      el.textContent = "";
      return;
    }
    el.textContent = m;
    el.hidden = false;
  }

  function _clearOtdErrors() {
    _setFieldError(otdDateError, "");
    _setFieldError(otdHoursError, "");
    _setFieldError(otdWorkTypeError, "");
    _setFieldError(otdActivityError, "");
    _setFieldError(otdActivityOtherError, "");
    _setFieldError(otdLocationError, "");
    _setFieldError(otdLocationOtherError, "");
    _setFieldError(otdCropError, "");
    _setFieldError(otdMachineOtherError, "");
  }

  function _clearBrigErrors() {
    _setFieldError(brigDateError, "");
    _setFieldError(brigCropError, "");
    _setFieldError(brigFieldError, "");
  }

  function _ruApiError(e) {
    const raw = String((e && e.message) || e || "").trim();
    if (!raw) return "Ошибка";
    if (raw.startsWith("HTTP 404")) return "Не найдено";
    if (raw.startsWith("HTTP 401")) return "Не авторизовано";
    if (raw.startsWith("HTTP 403")) return "Нет доступа";
    if (raw.includes("hours must be 1..24")) return "Часы должны быть от 1 до 24";
    if (raw.includes("missing:")) return "Заполните обязательные поля";
    if (raw.includes("invalid role")) return "Неверная роль";
    if (raw.includes("user not found")) return "Пользователь не найден";
    return raw;
  }

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
    stats: {
      mode: "today",
      selectedMonth: "",
    },
  };

  const _LS_WEATHER_GEO = "terra_weather_geo_v1";
  const _LS_WEATHER_LOCS = "terra_weather_locations_v1";
  const _LS_AVATAR = "terra_avatar_v1";

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

  function _fmtDateRu(iso) {
    try {
      const d = new Date(String(iso || ""));
      if (!Number.isFinite(d.getTime())) return String(iso || "");
      return d.toLocaleDateString("ru-RU", { year: "numeric", month: "2-digit", day: "2-digit" });
    } catch (e) {
      return String(iso || "");
    }
  }

  let _toastTimer = null;
  function toast(text, kind) {
    if (!toastEl) return;
    toastEl.hidden = false;
    toastEl.textContent = String(text || "");
    toastEl.style.borderColor = kind === "error" ? "rgba(255,93,93,.35)" : "rgba(255,255,255,.12)";
    try {
      if (tg && tg.HapticFeedback) {
        if (kind === "error" && tg.HapticFeedback.notificationOccurred) tg.HapticFeedback.notificationOccurred("error");
        else if (tg.HapticFeedback.notificationOccurred) tg.HapticFeedback.notificationOccurred("success");
      }
    } catch (e) {}
    if (_toastTimer) clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => {
      toastEl.hidden = true;
    }, 1600);
  }

  function hapticTap() {
    try {
      if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.impactOccurred === "function") tg.HapticFeedback.impactOccurred("light");
    } catch (e) {}
  }

  let _exportPollTimer = null;
  let _exportLastState = "";
  function _exportModalSet(open) {
    if (!exportModal) return;
    exportModal.hidden = !open;
    try {
      exportModal.style.display = open ? "flex" : "none";
    } catch (e) {}
  }

  function _exportModalRender(st) {
    if (!exportModalBody || !exportModalBar) return;
    const state = String((st && st.state) || "idle");
    const phase = String((st && st.phase) || "");
    const cur = Number((st && st.current) || 0) || 0;
    const total = Number((st && st.total) || 0) || 0;
    const msg = String((st && st.message) || "");
    const err = String((st && st.error) || "");

    let title = "Статус: " + state;
    if (phase) title += `, этап: ${phase}`;
    let line2 = "";
    if (total > 0) line2 = `Прогресс: ${cur}/${total}`;
    else if (cur > 0) line2 = `Выполнено: ${cur}`;
    let line3 = msg ? `Сообщение: ${msg}` : "";
    let line4 = err ? `Ошибка: ${err}` : "";

    exportModalBody.textContent = [title, line2, line3, line4].filter(Boolean).join("\n");

    const pct = total > 0 ? Math.max(0, Math.min(100, Math.round((cur / total) * 100))) : 0;
    exportModalBar.style.width = pct + "%";
  }

  async function _exportPollOnce() {
    try {
      const st = await apiGet("/api/admin/export/status");
      _exportModalRender(st);
      const state = String((st && st.state) || "idle");
      if (_exportLastState !== state) _exportLastState = state;
      if (state === "done") {
        _exportStopPolling();
        toast("Отчёт экспортирован");
        hapticTap();
      } else if (state === "error") {
        _exportStopPolling();
        toast("Ошибка экспорта", "error");
      }
    } catch (e) {
      _exportModalRender({ state: "error", error: _ruApiError(e) });
      _exportStopPolling();
      toast("Ошибка экспорта", "error");
    }
  }

  function _exportStartPolling() {
    _exportStopPolling();
    _exportLastState = "";
    _exportPollTimer = setInterval(_exportPollOnce, 1000);
    _exportPollOnce();
  }

  function _exportStopPolling() {
    if (_exportPollTimer) {
      clearInterval(_exportPollTimer);
      _exportPollTimer = null;
    }
  }

  function _fmtMonthRu(ym) {
    try {
      const parts = String(ym || "").split("-");
      const y = Number(parts[0]);
      const m = Number(parts[1]);
      const d = new Date(y, (m || 1) - 1, 1);
      return d.toLocaleDateString("ru-RU", { year: "numeric", month: "long" });
    } catch (e) {
      return String(ym || "");
    }
  }

  async function openReportView(reportId) {
    setScreen("reportView");
    if (reportViewBody) reportViewBody.textContent = "Загрузка…";
    const data = await apiGet(`/api/reports/${encodeURIComponent(reportId)}`);
    const r = data && data.report ? data.report : null;
    if (!r) {
      if (reportViewBody) reportViewBody.textContent = "Не найдено";
      return;
    }
    const lines = [
      `Дата: ${_fmtDateRu(r.work_date)}`,
      `Часы: ${String(r.hours ?? "—")}`,
      `Вид работы: ${String(r.activity || "—")}`,
      `Локация: ${String(r.location || "—")}`,
      `Техника: ${String(r.machine_type || "—")}`,
      `Название техники: ${String(r.machine_name || "—")}`,
      `Культура: ${String(r.crop || "—")}`,
    ];
    if (r.trips != null) lines.push(`Рейсы: ${String(r.trips)}`);
    if (reportViewBody) {
      reportViewBody.innerHTML = `<div class="list">${lines
        .map((x) => `<div class="listItem" style="cursor:default"><div class="listItem__title">${escapeHtml(x)}</div></div>`)
        .join("")}</div>`;
    }
  }

  async function renderStatsList(period) {
    state.stats.mode = period;
    if (!statsResult) return;
    statsResult.innerHTML = `<div style="font-size:13px; color:var(--muted)">Загрузка…</div>`;

    if (period === "month") {
      let m;
      try {
        m = await apiGet("/api/reports/months");
      } catch (e) {
        // fallback to legacy stats endpoint
        if (String(e.message || e).includes("404")) {
          const s = await apiGet("/api/stats?period=month");
          statsResult.innerHTML = `<div class="list"><div class="listItem" style="cursor:default"><div class="listItem__title">Месяц</div><div class="listItem__meta">${escapeHtml(String(s && s.total_hours != null ? s.total_hours : "—"))} ч</div></div></div>`;
          return;
        }
        throw e;
      }
      const items = (m && m.items) || [];
      if (!items.length) {
        statsResult.innerHTML = `<div style="font-size:13px; color:var(--muted)">Нет данных</div>`;
        return;
      }
      const list = document.createElement("div");
      list.className = "list";
      for (const it of items) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "listItem";
        btn.innerHTML = `
          <div class="listItem__top">
            <div class="listItem__title">${escapeHtml(_fmtMonthRu(it.month))}</div>
            <div class="listItem__title">${escapeHtml(String(it.total_hours || 0))} ч</div>
          </div>
          <div class="listItem__meta">Нажми чтобы открыть записи</div>
        `;
        btn.addEventListener("click", () => renderStatsMonthRecords(String(it.month || "")));
        list.appendChild(btn);
      }
      statsResult.innerHTML = "";
      statsResult.appendChild(list);
      return;
    }

    let data;
    try {
      data = await apiGet(`/api/reports?period=${encodeURIComponent(period)}`);
    } catch (e) {
      if (String(e.message || e).includes("404")) {
        const s = await apiGet(`/api/stats?period=${encodeURIComponent(period)}`);
        const title = period === "today" ? "Сегодня" : period === "week" ? "Неделя" : "Период";
        statsResult.innerHTML = `<div class="list"><div class="listItem" style="cursor:default"><div class="listItem__title">${escapeHtml(title)}</div><div class="listItem__meta">${escapeHtml(String(s && s.total_hours != null ? s.total_hours : "—"))} ч</div></div></div>`;
        return;
      }
      throw e;
    }
    const items = (data && data.items) || [];
    if (!items.length) {
      statsResult.innerHTML = `<div style="font-size:13px; color:var(--muted)">Нет записей</div>`;
      return;
    }
    const list = document.createElement("div");
    list.className = "list";
    for (const r of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(_fmtDateRu(r.work_date))} · ${escapeHtml(String(r.hours || 0))} ч</div>
          <div class="listItem__title">→</div>
        </div>
        <div class="listItem__meta">${escapeHtml(String(r.activity || "—"))}</div>
      `;
      btn.addEventListener("click", () => openReportView(r.id));
      list.appendChild(btn);
    }
    statsResult.innerHTML = "";
    statsResult.appendChild(list);
  }

  async function renderStatsMonthRecords(month) {
    state.stats.selectedMonth = String(month || "");
    if (!statsResult) return;
    statsResult.innerHTML = `<div style="font-size:13px; color:var(--muted)">Загрузка…</div>`;
    const data = await apiGet(`/api/reports?period=month&month=${encodeURIComponent(month)}`);
    const items = (data && data.items) || [];
    const list = document.createElement("div");
    list.className = "list";

    const head = document.createElement("button");
    head.type = "button";
    head.className = "listItem";
    head.innerHTML = `<div class="listItem__top"><div class="listItem__title">← Назад к месяцам</div><div class="listItem__title"></div></div>`;
    head.addEventListener("click", () => renderStatsList("month"));
    list.appendChild(head);

    if (!items.length) {
      statsResult.innerHTML = "";
      statsResult.appendChild(list);
      const empty = document.createElement("div");
      empty.style.fontSize = "13px";
      empty.style.color = "var(--muted)";
      empty.style.marginTop = "10px";
      empty.textContent = "Нет записей";
      statsResult.appendChild(empty);
      return;
    }

    for (const r of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(_fmtDateRu(r.work_date))} · ${escapeHtml(String(r.hours || 0))} ч</div>
          <div class="listItem__title">→</div>
        </div>
        <div class="listItem__meta">${escapeHtml(String(r.activity || "—"))}</div>
      `;
      btn.addEventListener("click", () => openReportView(r.id));
      list.appendChild(btn);
    }

    statsResult.innerHTML = "";
    statsResult.appendChild(list);
  }

  async function renderWeatherLocations() {
    if (!weatherLocList) return;
    const locs = loadWeatherLocations();
    weatherLocList.innerHTML = "";

    const now = new Date();
    const season = _seasonByMonth(now.getMonth() + 1);
    const timeOfDay = _timeBucket(now);

    for (const loc of locs) {
      const { lat, lon } = _centroid(loc.polygon);
      let t = null;
      let meta = "";
      let wc = null;
      let weatherKind = "clear";
      try {
        const cur = await _fetchWeatherCurrent(lat, lon);
        t = cur.t;
        wc = cur.wc;
        weatherKind = _weatherKindFromCurrent(cur);
        meta = cur.p != null ? `Осадки: ${cur.p.toFixed(1)} мм` : "";
      } catch (e) {
        meta = "Погода недоступна";
      }

      const sceneKey = `${season}_${timeOfDay}_${weatherKind}`;
      const tempBand = _tempBand(t);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "locCard";
      btn.classList.add("locCard--px");
      btn.innerHTML = `
        <div class="pxScene" data-locid="${escapeHtml(String(loc.id || ""))}" data-scene="${escapeHtml(sceneKey)}" data-season="${escapeHtml(season)}" data-time="${escapeHtml(timeOfDay)}" data-weather="${escapeHtml(weatherKind)}" data-tempband="${escapeHtml(tempBand)}">
          <div class="pxLayer pxLayer--sky"></div>
          <div class="pxLayer pxLayer--horizon"></div>
          <div class="pxLayer pxLayer--ground"></div>
          <div class="pxLayer pxLayer--clouds"></div>
          <div class="pxLayer pxLayer--precip"></div>
          <div class="pxLayer pxLayer--fog"></div>
          <div class="pxLayer pxLayer--birds"></div>
          <canvas class="pxCanvas" aria-hidden="true"></canvas>
          <div class="pxTint"></div>
        </div>
        <div class="locCard__topLabel">
          <div class="locCard__topRight">
            <div class="locCard__topTemp">${t == null ? "—" : `${t}°`}</div>
            <div class="locCard__topName">${escapeHtml(loc.name || "Локация")}</div>
          </div>
        </div>
        <div class="locCard__meta">${escapeHtml(meta || "")}</div>
      `;
      btn.addEventListener("click", () => openWeatherLocView(loc.id));
      weatherLocList.appendChild(btn);
    }

    _pxSceneScanAndInit();
  }

  const _pxSceneStates = new WeakMap();
  let _pxRaf = 0;
  let _pxLastFrameTs = 0;
  const _PX_FPS = 12;
  const _PX_DT = 1000 / _PX_FPS;

  function _hash32(str) {
    const s = String(str || "");
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0);
  }

  function _rng(seed) {
    let x = seed >>> 0;
    return function () {
      // xorshift32
      x ^= x << 13;
      x ^= x >>> 17;
      x ^= x << 5;
      return ((x >>> 0) / 4294967296);
    };
  }

  function _pxSceneScanAndInit() {
    try {
      const scenes = document.querySelectorAll(".pxScene .pxCanvas");
      for (const c of scenes) {
        const sceneEl = c.closest(".pxScene");
        if (!sceneEl) continue;
        sceneEl.classList.add("hasCanvas");
        if (_pxSceneStates.has(c)) continue;

        const locId = sceneEl.getAttribute("data-locid") || "";
        const seed = _hash32(locId || sceneEl.getAttribute("data-scene") || "");
        const rand = _rng(seed);
        _pxSceneStates.set(c, {
          seed,
          rand,
          clouds: _mkClouds(rand),
          rain: _mkRain(rand),
          snow: _mkSnow(rand),
          fog: _mkFog(rand),
          birds: _mkBirds(rand),
          lastResizeW: 0,
          lastResizeH: 0,
        });
      }
    } catch (e) {}

    _pxEnsureAnim();
  }

  function _mkClouds(rand) {
    const out = [];
    const n = 5;
    for (let i = 0; i < n; i++) {
      out.push({ x: rand() * 1, y: rand() * 0.35, r: 0.12 + rand() * 0.18, v: 0.002 + rand() * 0.004 });
    }
    return out;
  }

  function _mkRain(rand) {
    const out = [];
    const n = 120;
    for (let i = 0; i < n; i++) {
      out.push({ x: rand(), y: rand(), v: 0.8 + rand() * 1.1, l: 0.03 + rand() * 0.04, a: 0.35 + rand() * 0.35 });
    }
    return out;
  }

  function _mkSnow(rand) {
    const out = [];
    const n = 55;
    for (let i = 0; i < n; i++) {
      out.push({ x: rand(), y: rand(), v: 0.18 + rand() * 0.45, s: 1 + Math.floor(rand() * 2), drift: (rand() - 0.5) * 0.2, a: 0.45 + rand() * 0.35 });
    }
    return out;
  }

  function _mkFog(rand) {
    const out = [];
    const n = 4;
    for (let i = 0; i < n; i++) {
      out.push({ x: rand(), y: 0.1 + rand() * 0.55, w: 0.35 + rand() * 0.55, h: 0.08 + rand() * 0.16, v: 0.002 + rand() * 0.003, a: 0.08 + rand() * 0.08 });
    }
    return out;
  }

  function _mkBirds(rand) {
    return {
      t: rand() * 6,
      active: false,
      x: 1.1,
      y: 0.18 + rand() * 0.22,
      v: 0.02 + rand() * 0.02,
      cooldown: 1.5 + rand() * 4,
    };
  }

  function _pxEnsureAnim() {
    if (_pxRaf) return;
    _pxLastFrameTs = 0;
    _pxRaf = requestAnimationFrame(_pxAnimTick);
  }

  function _pxStopAnim() {
    if (_pxRaf) cancelAnimationFrame(_pxRaf);
    _pxRaf = 0;
  }

  function _pxAnimTick(ts) {
    _pxRaf = requestAnimationFrame(_pxAnimTick);
    if (state.screen !== "weatherLocations") {
      _pxStopAnim();
      return;
    }
    if (_pxLastFrameTs && ts - _pxLastFrameTs < _PX_DT) return;
    _pxLastFrameTs = ts;
    _pxRenderAll(ts);
  }

  function _pxRenderAll(ts) {
    const canvases = document.querySelectorAll(".pxScene .pxCanvas");
    for (const canvas of canvases) {
      const sceneEl = canvas.closest(".pxScene");
      if (!sceneEl) continue;
      const st = _pxSceneStates.get(canvas);
      if (!st) continue;

      // resize to element
      const w = Math.max(1, Math.floor(sceneEl.clientWidth));
      const h = Math.max(1, Math.floor(sceneEl.clientHeight));
      const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      if (st.lastResizeW !== w || st.lastResizeH !== h || canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
        canvas.style.width = w + "px";
        canvas.style.height = h + "px";
        st.lastResizeW = w;
        st.lastResizeH = h;
      }

      const ctx = canvas.getContext("2d", { alpha: true });
      if (!ctx) continue;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, w, h);

      const weather = sceneEl.getAttribute("data-weather") || "clear";
      const time = sceneEl.getAttribute("data-time") || "day";

      // Subtle clouds always
      _pxDrawClouds(ctx, w, h, st, ts, time);

      if (weather === "fog") _pxDrawFog(ctx, w, h, st, ts);
      if (weather === "rain" || weather === "storm") _pxDrawRain(ctx, w, h, st, ts, weather === "storm");
      if (weather === "snow") _pxDrawSnow(ctx, w, h, st, ts);
      if (weather === "clear" && (time === "day" || time === "morning")) _pxDrawBirds(ctx, w, h, st, ts);
    }
  }

  function _pxDrawClouds(ctx, w, h, st, ts, time) {
    const baseA = time === "night" ? 0.10 : time === "evening" ? 0.08 : 0.06;
    ctx.fillStyle = `rgba(255,255,255,${baseA})`;
    const t = ts / 1000;
    for (const c of st.clouds) {
      const x = ((c.x + t * c.v) % 1) * w;
      const y = c.y * h;
      const r = c.r * w;
      // pixelated blob built from rects
      const px = Math.max(1, Math.floor(r / 10));
      for (let i = -3; i <= 3; i++) {
        const ww = (4 - Math.abs(i)) * px * 2;
        const xx = Math.round(x + i * px * 3);
        const yy = Math.round(y + i * px);
        ctx.fillRect(xx, yy, ww, px * 2);
      }
    }
  }

  function _pxDrawRain(ctx, w, h, st, ts, isStorm) {
    const t = ts / 1000;
    const dx = isStorm ? -0.18 : -0.14;
    const dy = isStorm ? 0.42 : 0.34;
    for (const d of st.rain) {
      const a = Math.max(0.10, Math.min(0.85, (isStorm ? 0.55 : 0.40) * (d.a || 0.6)));
      ctx.fillStyle = `rgba(210,230,255,${a})`;
      let x = (d.x + t * dx * d.v) % 1;
      let y = (d.y + t * dy * d.v) % 1;
      if (x < 0) x += 1;
      if (y < 0) y += 1;
      const x0 = Math.round(x * w);
      const y0 = Math.round(y * h);
      const len = Math.max(5, Math.round(d.l * h * (isStorm ? 1.35 : 1.15)));
      // draw as stepped diagonal pixels
      const steps = Math.max(2, Math.floor(len / 3));
      for (let i = 0; i < steps; i++) {
        const xx = x0 + i;
        const yy = y0 + i * 2;
        ctx.fillRect(xx, yy, 1, 2);
      }
    }
  }

  function _pxDrawSnow(ctx, w, h, st, ts) {
    const t = ts / 1000;
    ctx.fillStyle = "rgba(255,255,255,.6)";
    for (const s of st.snow) {
      let x = (s.x + t * (0.03 + s.drift)) % 1;
      let y = (s.y + t * s.v) % 1;
      if (x < 0) x += 1;
      if (y < 0) y += 1;
      const x0 = Math.round(x * w);
      const y0 = Math.round(y * h);
      const sz = s.s;
      ctx.fillRect(x0, y0, sz, sz);
    }

    // light ground drift
    ctx.fillStyle = "rgba(255,255,255,.05)";
    const bandY = Math.round(h * 0.74);
    const offset = Math.round(((t * 10) % 40));
    for (let x = -40; x < w + 40; x += 14) {
      ctx.fillRect(x + offset, bandY, 10, 2);
    }
  }

  function _pxDrawFog(ctx, w, h, st, ts) {
    const t = ts / 1000;
    ctx.fillStyle = "rgba(255,255,255,.06)";
    for (const f of st.fog) {
      const x = ((f.x + t * f.v) % 1) * w;
      const y = f.y * h;
      const ww = f.w * w;
      const hh = f.h * h;
      const step = 6;
      for (let i = 0; i < hh; i += step) {
        const alpha = 0.02 + ((i / hh) * 0.04);
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        ctx.fillRect(Math.round(x), Math.round(y + i), Math.round(ww), Math.max(2, step - 2));
      }
    }
  }

  function _pxDrawBirds(ctx, w, h, st, ts) {
    const t = ts / 1000;
    const b = st.birds;
    b.t += 1 / _PX_FPS;

    if (!b.active) {
      b.cooldown -= 1 / _PX_FPS;
      if (b.cooldown <= 0) {
        // 35% chance to spawn
        if (st.rand() < 0.35) {
          b.active = true;
          b.x = 1.08;
          b.y = 0.16 + st.rand() * 0.22;
          b.v = 0.022 + st.rand() * 0.02;
        }
        b.cooldown = 2 + st.rand() * 5;
      }
      return;
    }

    b.x -= b.v;
    if (b.x < -0.1) {
      b.active = false;
      return;
    }

    const x = Math.round(b.x * w);
    const y = Math.round(b.y * h);
    ctx.fillStyle = "rgba(20,24,30,.55)";
    // simple V-shape, pixel perfect
    ctx.fillRect(x, y, 1, 1);
    ctx.fillRect(x + 2, y, 1, 1);
    ctx.fillRect(x + 1, y + 1, 1, 1);
  }

  function _timeBucket(d) {
    const h = d.getHours();
    const m = d.getMinutes();
    const t = h * 60 + m;
    // NIGHT: >=22:00 or <05:00
    if (t >= 22 * 60 || t < 5 * 60) return "night";
    // MORNING: 05:00–09:00
    if (t >= 5 * 60 && t < 9 * 60) return "morning";
    // DAY: 09:00–18:00
    if (t >= 9 * 60 && t < 18 * 60) return "day";
    // EVENING: 18:00–22:00
    return "evening";
  }

  function _seasonByMonth(month) {
    const m = Number(month);
    if (m === 12 || m === 1 || m === 2) return "winter";
    if (m === 3 || m === 4 || m === 5) return "spring";
    if (m === 6 || m === 7 || m === 8) return "summer";
    return "autumn";
  }

  function _tempBand(t) {
    const x = Number(t);
    if (!isFinite(x)) return "mild";
    if (x <= 0) return "cold";
    if (x <= 10) return "cool";
    if (x <= 22) return "mild";
    return "warm";
  }

  function _weatherKindFromCurrent(cur) {
    const wc = cur && cur.wc != null ? Number(cur.wc) : null;
    const p = cur && cur.p != null ? Number(cur.p) : 0;
    // Priority: STORM > SNOW > RAIN > FOG > CLEAR
    // Open-Meteo weather codes: https://open-meteo.com/en/docs
    // Thunderstorm: 95,96,99
    if (wc === 95 || wc === 96 || wc === 99) return "storm";
    // Snow: 71-77 (snow), 85-86 (snow showers)
    if ((wc != null && wc >= 71 && wc <= 77) || wc === 85 || wc === 86) return "snow";
    // Rain/Drizzle: 51-67 (drizzle/rain), 80-82 (rain showers)
    if ((wc != null && wc >= 51 && wc <= 67) || (wc != null && wc >= 80 && wc <= 82) || p > 0) return "rain";
    // Fog: 45,48
    if (wc === 45 || wc === 48) return "fog";
    return "clear";
  }

  async function openWeatherLocations() {
    setScreen("weatherLocations");
    await renderWeatherLocations();

    try {
      if (state._weatherLocsTimer) clearInterval(state._weatherLocsTimer);
    } catch (e) {}
    state._weatherLocsTimer = setInterval(() => {
      if (state.screen !== "weatherLocations") return;
      renderWeatherLocations().catch(() => {});
    }, 10 * 60 * 1000);
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
    if (weatherLocSearch) weatherLocSearch.value = "";
    if (weatherLocSearchResults) weatherLocSearchResults.innerHTML = "";
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

  async function _geoSearch(q) {
    const query = String(q || "").trim();
    if (!query) return [];
    const url = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=7&language=ru&format=json`;
    const res = await fetch(url, { method: "GET" });
    const data = await res.json().catch(() => null);
    const items = (data && data.results) || [];
    return (items || []).map((r) => ({
      name: [r.name, r.admin1, r.country].filter(Boolean).join(", "),
      lat: Number(r.latitude),
      lon: Number(r.longitude),
    })).filter((x) => isFinite(x.lat) && isFinite(x.lon));
  }

  function _renderGeoResults(items) {
    if (!weatherLocSearchResults) return;
    weatherLocSearchResults.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "searchResults";
    for (const it of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "searchItem";
      btn.textContent = it.name;
      btn.addEventListener("click", () => {
        try {
          if (state.weatherLoc.map) state.weatherLoc.map.setView([it.lat, it.lon], 14);
        } catch (e) {}
        toast("Переход к месту");
        weatherLocSearchResults.innerHTML = "";
      });
      wrap.appendChild(btn);
    }
    weatherLocSearchResults.appendChild(wrap);
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
    let img = "";
    try {
      img = String(localStorage.getItem(_LS_AVATAR) || "");
    } catch (e) {
      img = "";
    }

    const wrap = elAvatar ? elAvatar.closest(".avatar") : null;
    if (img && wrap) {
      wrap.style.backgroundImage = `url(${img})`;
      wrap.style.backgroundSize = "cover";
      wrap.style.backgroundPosition = "center";
      wrap.style.backgroundRepeat = "no-repeat";
      elAvatar.textContent = "";
    } else {
      if (wrap) {
        wrap.style.backgroundImage = "";
        wrap.style.backgroundSize = "";
        wrap.style.backgroundPosition = "";
        wrap.style.backgroundRepeat = "";
      }
      if (elAvatar) elAvatar.textContent = letter;
    }

    if (settingsAvatarPreview) settingsAvatarPreview.textContent = img ? "" : letter;
    const sWrap = settingsAvatarPreview ? settingsAvatarPreview.closest(".avatar") : null;
    if (img && sWrap) {
      sWrap.style.backgroundImage = `url(${img})`;
      sWrap.style.backgroundSize = "cover";
      sWrap.style.backgroundPosition = "center";
      sWrap.style.backgroundRepeat = "no-repeat";
    } else if (sWrap) {
      sWrap.style.backgroundImage = "";
      sWrap.style.backgroundSize = "";
      sWrap.style.backgroundPosition = "";
      sWrap.style.backgroundRepeat = "";
    }
  }

  function _readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(String(fr.result || ""));
      fr.onerror = () => reject(new Error("read failed"));
      fr.readAsDataURL(file);
    });
  }

  async function onAvatarFileSelected() {
    try {
      const f = settingsAvatarFile && settingsAvatarFile.files ? settingsAvatarFile.files[0] : null;
      if (!f) return;
      if (!String(f.type || "").startsWith("image/")) {
        toast("Выберите изображение", "error");
        return;
      }
      await openAvatarCrop(f);
    } catch (e) {
      toast("Ошибка", "error");
    }
  }

  const _avatarCropState = {
    img: null,
    file: null,
    scale: 1,
    ox: 0,
    oy: 0,
    dragging: false,
    lastX: 0,
    lastY: 0,
  };

  async function openAvatarCrop(file) {
    if (!avatarCropCanvas || !avatarCropWrap) {
      toast("Кроп недоступен", "error");
      return;
    }
    if (avatarCropResult) avatarCropResult.textContent = "";
    const dataUrl = await _readFileAsDataUrl(file);
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("image load failed"));
      img.src = dataUrl;
    });

    _avatarCropState.img = img;
    _avatarCropState.file = file;
    _avatarCropState.scale = 1;
    _avatarCropState.ox = 0;
    _avatarCropState.oy = 0;
    if (avatarCropZoom) avatarCropZoom.value = "1";

    setScreen("avatarCrop");
    setTimeout(() => {
      try {
        _avatarCropFit();
        _avatarCropDraw();
      } catch (e) {}
    }, 0);
  }

  function _avatarCropFit() {
    const img = _avatarCropState.img;
    if (!img || !avatarCropWrap || !avatarCropCanvas) return;
    const r = avatarCropWrap.getBoundingClientRect();
    const size = Math.max(1, Math.floor(Math.min(r.width, r.height)));
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    avatarCropCanvas.width = Math.floor(size * dpr);
    avatarCropCanvas.height = Math.floor(size * dpr);
    avatarCropCanvas.style.width = size + "px";
    avatarCropCanvas.style.height = size + "px";

    const scaleToCover = Math.max(size / img.width, size / img.height);
    _avatarCropState.baseScale = scaleToCover;
    _avatarCropState.scale = 1;
    _avatarCropState.ox = 0;
    _avatarCropState.oy = 0;
  }

  function _avatarCropDraw() {
    const img = _avatarCropState.img;
    if (!img || !avatarCropCanvas) return;
    const ctx = avatarCropCanvas.getContext("2d");
    if (!ctx) return;
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    const size = Math.floor(avatarCropCanvas.width / dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.clearRect(0, 0, size, size);

    const base = _avatarCropState.baseScale || 1;
    const z = Math.max(1, Math.min(3, _avatarCropState.scale || 1));
    const s = base * z;
    const dw = img.width * s;
    const dh = img.height * s;
    const cx = size / 2;
    const cy = size / 2;
    const x = Math.round(cx - dw / 2 + (_avatarCropState.ox || 0));
    const y = Math.round(cy - dh / 2 + (_avatarCropState.oy || 0));
    ctx.drawImage(img, x, y, dw, dh);
  }

  function _avatarCropPointerXY(ev) {
    const rect = avatarCropCanvas.getBoundingClientRect();
    return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
  }

  function _avatarCropBindEvents() {
    if (!avatarCropCanvas) return;

    const onDown = (ev) => {
      ev.preventDefault();
      const p = _avatarCropPointerXY(ev);
      _avatarCropState.dragging = true;
      _avatarCropState.lastX = p.x;
      _avatarCropState.lastY = p.y;
    };
    const onMove = (ev) => {
      if (!_avatarCropState.dragging) return;
      ev.preventDefault();
      const p = _avatarCropPointerXY(ev);
      const dx = p.x - _avatarCropState.lastX;
      const dy = p.y - _avatarCropState.lastY;
      _avatarCropState.lastX = p.x;
      _avatarCropState.lastY = p.y;
      _avatarCropState.ox += dx;
      _avatarCropState.oy += dy;
      _avatarCropDraw();
    };
    const onUp = () => {
      _avatarCropState.dragging = false;
    };

    avatarCropCanvas.addEventListener("pointerdown", onDown);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  }

  async function _avatarCropSaveNow() {
    try {
      const img = _avatarCropState.img;
      if (!img || !avatarCropCanvas) return;
      const out = document.createElement("canvas");
      const outSize = 256;
      out.width = outSize;
      out.height = outSize;
      const ctx = out.getContext("2d");
      if (!ctx) return;
      ctx.imageSmoothingEnabled = true;

      const previewSize = Math.max(1, Math.floor(avatarCropCanvas.getBoundingClientRect().width));
      const inset = 10; // must match .cropFrame{inset:10px}
      const cropSize = Math.max(1, previewSize - inset * 2);
      const base = _avatarCropState.baseScale || 1;
      const z = Math.max(1, Math.min(3, _avatarCropState.scale || 1));
      const s = base * z;
      const dw = img.width * s;
      const dh = img.height * s;
      const cx = previewSize / 2;
      const cy = previewSize / 2;
      const x = cx - dw / 2 + (_avatarCropState.ox || 0);
      const y = cy - dh / 2 + (_avatarCropState.oy || 0);

      // map frame (inset..inset+cropSize) -> source crop rect
      const frameX = inset;
      const frameY = inset;
      const sx = (frameX - x) / s;
      const sy = (frameY - y) / s;
      const sw = cropSize / s;
      const sh = cropSize / s;

      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, outSize, outSize);
      const dataUrl = out.toDataURL("image/jpeg", 0.9);

      try {
        localStorage.setItem(_LS_AVATAR, dataUrl);
      } catch (e) {
        toast("Не удалось сохранить аватар", "error");
        return;
      }
      setAvatar((elFullName && elFullName.textContent) || "");
      toast("Аватар сохранён");
      hapticTap();
      try { if (settingsAvatarFile) settingsAvatarFile.value = ""; } catch (e) {}
      setScreen("settings");
    } catch (e) {
      toast("Ошибка", "error");
    }
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
    if (name === "admin") setSubtitle("");
    if (name === "stats") setSubtitle("");
    if (name === "settings") setSubtitle("");
    if (name === "brig") setSubtitle("");
    if (name === "weatherLocations") setSubtitle("");
    if (name === "weatherLocEdit") setSubtitle("");
    if (name === "weatherLocView") setSubtitle("");
    if (name === "avatarCrop") setSubtitle("");

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
    let url = String(path || "");
    // Telegram WebView may aggressively cache GET responses; bust cache for our API.
    if (url.startsWith("/api/")) {
      const ts = Date.now();
      url += (url.includes("?") ? "&" : "?") + "ts=" + encodeURIComponent(String(ts));
    }
    const headers = Object.assign({}, apiHeaders(), {
      "Cache-Control": "no-cache, no-store, must-revalidate",
      "Pragma": "no-cache",
    });
    const res = await fetch(url, { method: "GET", headers, cache: "no-store" });
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

  async function apiPatch(path, body) {
    const payload = Object.assign({}, body || {});
    if (state.initData && !payload.initData) payload.initData = state.initData;
    const res = await fetch(path, { method: "PATCH", headers: apiHeaders(), body: JSON.stringify(payload) });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data) throw new Error((data && data.error) || `HTTP ${res.status}`);
    return data;
  }

  async function apiDelete(path) {
    const res = await fetch(path, { method: "DELETE", headers: apiHeaders() });
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
    if (otdMachineOther) otdMachineOther.value = "";
    _setHidden(otdMachineOtherWrap, true);
    if (otdActivity) otdActivity.value = "";
    if (otdActivityOther) otdActivityOther.value = "";
    _setHidden(otdActivityOtherWrap, true);
    if (otdCrop) otdCrop.value = "";
    if (otdLocation) otdLocation.value = "";
    if (otdLocationOther) otdLocationOther.value = "";
    _setHidden(otdLocationOtherWrap, true);
    if (otdTrips) otdTrips.value = "";
  }

  function _isOtherGeneric(val) {
    const v = String(val || "").trim().toLowerCase();
    return v === "прочее" || v === "другое" || v === "прочие";
  }

  function _withOther(values) {
    const out = Array.isArray(values) ? values.slice() : [];
    const has = out.some((x) => {
      if (x && typeof x === "object") return _isOtherGeneric(x.value) || _isOtherGeneric(x.label) || _isOtherGeneric(x.title) || _isOtherGeneric(x.name);
      return _isOtherGeneric(x);
    });
    if (!has) out.push({ value: "Прочее", label: "Прочее" });
    return out;
  }

  function _applyOtdLocationOther() {
    if (!otdLocation) return;
    const isOther = _isOtherGeneric(otdLocation.value);
    _setHidden(otdLocationOtherWrap, !isOther);
    if (!isOther && otdLocationOther) otdLocationOther.value = "";
  }

  function _applyOtdMachineOther() {
    if (!otdMachineName) return;
    const isOther = _isOtherGeneric(otdMachineName.value);
    _setHidden(otdMachineOtherWrap, !isOther);
    if (!isOther && otdMachineOther) otdMachineOther.value = "";
  }

  function _otdSetupDateLimits() {
    if (!otdDate) return;
    try {
      const now = new Date();
      const max = new Date(now);
      const min = new Date(now);
      min.setDate(now.getDate() - 6);
      const maxStr = `${max.getFullYear()}-${String(max.getMonth() + 1).padStart(2, "0")}-${String(max.getDate()).padStart(2, "0")}`;
      const minStr = `${min.getFullYear()}-${String(min.getMonth() + 1).padStart(2, "0")}-${String(min.getDate()).padStart(2, "0")}`;
      otdDate.min = minStr;
      otdDate.max = maxStr;
      if (!otdDate.value) otdDate.value = maxStr;

      const clamp = () => {
        const v = (otdDate.value || "").trim();
        if (!v) {
          otdDate.value = maxStr;
          return;
        }
        if (v < minStr) otdDate.value = minStr;
        if (v > maxStr) otdDate.value = maxStr;
      };
      otdDate.onchange = clamp;
      otdDate.oninput = clamp;
      clamp();
    } catch (e) {}
  }

  function _isOtherActivity(val) {
    const v = String(val || "").trim().toLowerCase();
    return v === "прочее" || v === "другое" || v === "прочие";
  }

  function _applyOtdActivityOther() {
    if (!otdActivity) return;
    const isOther = _isOtherActivity(otdActivity.value);
    _setHidden(otdActivityOtherWrap, !isOther);
    if (!isOther && otdActivityOther) otdActivityOther.value = "";
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
      _fillSelect(otdLocation, _withOther((d.locations && d.locations.fields) || []), "Выберите поле");
      _fillSelect(otdCrop, (d.crops) || [], "Выберите культуру");
      _applyOtdLocationOther();
      _applyOtdMachineOther();
      return;
    }

    if (wt === "hand") {
      _setHidden(otdMachineKindWrap, true);
      _setHidden(otdMachineNameWrap, true);
      _setHidden(otdTripsWrap, true);

      _fillSelect(otdActivity, (d.otd && d.otd.hand_works) || [], "Выберите вид работы");
      _fillSelect(otdLocation, _withOther((d.locations && d.locations.fields) || []), "Выберите локацию");
      _fillSelect(otdCrop, (d.crops) || [], "Выберите культуру");
      _applyOtdLocationOther();
      _applyOtdMachineOther();
      return;
    }

    // not selected
    _setHidden(otdMachineKindWrap, true);
    _setHidden(otdMachineNameWrap, true);
    _setHidden(otdTripsWrap, true);
    _fillSelect(otdActivity, [], "Сначала выберите тип работы");
    _fillSelect(otdLocation, [], "Сначала выберите тип работы");
    _fillSelect(otdCrop, [], "Сначала выберите тип работы");
    _applyOtdLocationOther();
    _applyOtdMachineOther();
  }

  async function onOtdMachineKindChange() {
    const d = await ensureDictionaries();
    const raw = (otdMachineKind && otdMachineKind.value) || "";
    const kindId = raw ? Number(raw) : 0;
    const kind = (d.machine_kinds || []).find((k) => String(k.id) === String(raw)) || null;
    state.otd.machineKind = kind;
    state.otd.machineMode = (kind && (kind.mode || "list")) || "list";

    if (state.otd.machineMode === "single") {
      // КамАЗ: machine_name = title, trips required
      _setHidden(otdMachineNameWrap, true);
      _setHidden(otdTripsWrap, false);
      _fillSelect(otdActivity, ["КамАЗ"], "КамАЗ");
      if (otdActivity) otdActivity.value = "КамАЗ";
      _fillSelect(otdCrop, (d.otd && d.otd.kamaz_cargo) || [], "Выберите груз");
      _fillSelect(otdLocation, _withOther((d.otd && d.otd.fields) || []), "Где погружались?");
      _applyOtdLocationOther();
      _applyOtdMachineOther();
      return;
    }

    _setHidden(otdMachineNameWrap, false);
    _setHidden(otdTripsWrap, true);
    const items = kindId ? await loadMachineItems(kindId) : [];
    _fillSelect(otdMachineName, _withOther(items), "Выберите технику");
    _applyOtdMachineOther();
    // normal tractor work
    _fillSelect(otdActivity, (d.otd && d.otd.tractor_works) || [], "Выберите работу техники");
    _fillSelect(otdCrop, (d.otd && d.otd.crops) || [], "Выберите культуру");
    _fillSelect(otdLocation, _withOther((d.otd && d.otd.fields) || []), "Выберите поле");
    _applyOtdLocationOther();
    _applyOtdMachineOther();
  }

  async function openOtd() {
    setScreen("otd");
    otdResult.textContent = "";
    _otdSetupDateLimits();
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

      if (otdMachineName) {
        otdMachineName.onchange = () => {
          _applyOtdMachineOther();
        };
      }

      if (otdLocation) {
        otdLocation.onchange = () => {
          _applyOtdLocationOther();
        };
      }

      // start with current selection
      await applyOtdWorkType();

      if (otdActivity) {
        otdActivity.onchange = () => {
          _applyOtdActivityOther();
        };
      }
      _applyOtdActivityOther();
      _applyOtdLocationOther();
      _applyOtdMachineOther();
    } catch (e) {
      otdResult.textContent = "Не удалось загрузить справочники: " + String(e.message || e);
    }
  }

  async function submitOtd() {
    if (!otdResult) return;
    otdResult.textContent = "";
    _clearOtdErrors();
    const work_date = (otdDate && otdDate.value) || "";
    const hours = (otdHours && otdHours.value) || "";
    let activity = (otdActivity && otdActivity.value) || "";
    if (_isOtherActivity(activity)) {
      const other = (otdActivityOther && otdActivityOther.value) ? String(otdActivityOther.value).trim() : "";
      if (other) activity = other;
    }
    const crop = (otdCrop && otdCrop.value) || "";
    let location = (otdLocation && otdLocation.value) || "";
    if (_isOtherGeneric(location)) {
      const other = (otdLocationOther && otdLocationOther.value) ? String(otdLocationOther.value).trim() : "";
      if (other) location = other;
    }
    const trips = (otdTrips && otdTrips.value) || "";
    const wt = (otdWorkType && otdWorkType.value) || "";
    const kind = state.otd.machineKind;
    const machine_mode = state.otd.machineMode || "list";
    const machine_type = wt === "hand" ? "Ручная" : (kind && kind.title ? String(kind.title) : "");
    let machine_name = (otdMachineName && otdMachineName.value) || "";
    if (_isOtherGeneric(machine_name)) {
      const other = (otdMachineOther && otdMachineOther.value) ? String(otdMachineOther.value).trim() : "";
      if (other) machine_name = other;
    }

    // фронтовая валидация (русские ошибки рядом с полем)
    let hasErr = false;
    if (!work_date) {
      _setFieldError(otdDateError, "Выберите дату");
      hasErr = true;
    }
    const hNum = hours ? Number(hours) : 0;
    if (!hours || !isFinite(hNum) || hNum <= 0) {
      _setFieldError(otdHoursError, "Заполните часы");
      hasErr = true;
    }
    if (hours && (hNum < 1 || hNum > 24)) {
      _setFieldError(otdHoursError, "Часы должны быть от 1 до 24");
      hasErr = true;
    }
    if (!wt) {
      _setFieldError(otdWorkTypeError, "Выберите тип работы");
      hasErr = true;
    }
    if (!activity) {
      _setFieldError(otdActivityError, "Выберите вид работы");
      hasErr = true;
    }
    if (_isOtherActivity((otdActivity && otdActivity.value) || "") && !(otdActivityOther && String(otdActivityOther.value || "").trim())) {
      _setFieldError(otdActivityOtherError, "Введите вид работы");
      hasErr = true;
    }
    if (!location) {
      _setFieldError(otdLocationError, "Выберите локацию / поле");
      hasErr = true;
    }
    if (_isOtherGeneric((otdLocation && otdLocation.value) || "") && !(otdLocationOther && String(otdLocationOther.value || "").trim())) {
      _setFieldError(otdLocationOtherError, "Введите локацию");
      hasErr = true;
    }
    if (!crop) {
      _setFieldError(otdCropError, "Выберите культуру");
      hasErr = true;
    }
    if (wt === "tech" && _isOtherGeneric((otdMachineName && otdMachineName.value) || "") && !(otdMachineOther && String(otdMachineOther.value || "").trim())) {
      _setFieldError(otdMachineOtherError, "Введите технику");
      hasErr = true;
    }
    if (hasErr) {
      toast("Проверьте заполнение формы", "error");
      return;
    }

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
      toast("Отчёт сохранён");
      try {
        if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.notificationOccurred === "function") {
          tg.HapticFeedback.notificationOccurred("success");
        }
      } catch (e) {}
      // обновим дашборд статистики
      try {
        await refreshDashboardStats();
      } catch (e) {}

      try {
        await refreshNotificationsBadge();
      } catch (e) {}
      return data;
    } catch (e) {
      otdResult.textContent = _ruApiError(e);
      toast("Ошибка сохранения", "error");
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
    _clearBrigErrors();
    const work_date = (brigDate && brigDate.value) || "";
    const crop = (brigCrop && brigCrop.value) || "";
    const field = (brigField && brigField.value) || "";
    const rows = (brigRows && brigRows.value) || "";
    const workers = (brigWorkers && brigWorkers.value) || "";
    const bags = (brigBags && brigBags.value) || "";
    let hasErr = false;
    if (!work_date) {
      _setFieldError(brigDateError, "Выберите дату");
      hasErr = true;
    }
    if (!crop) {
      _setFieldError(brigCropError, "Выберите культуру");
      hasErr = true;
    }
    if (!field) {
      _setFieldError(brigFieldError, "Выберите поле");
      hasErr = true;
    }
    if (hasErr) {
      toast("Проверьте заполнение формы", "error");
      return;
    }
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
      toast("Отчёт сохранён");
      try {
        if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.notificationOccurred === "function") {
          tg.HapticFeedback.notificationOccurred("success");
        }
      } catch (e2) {}
    } catch (e) {
      brigResult.textContent = _ruApiError(e);
      toast("Ошибка сохранения", "error");
      try {
        if (tg && tg.HapticFeedback && typeof tg.HapticFeedback.notificationOccurred === "function") {
          tg.HapticFeedback.notificationOccurred("error");
        }
      } catch (e2) {}
    }
  }

  async function loadStats(period) {
    try {
      await renderStatsList(period);
    } catch (e) {
      if (statsResult) statsResult.innerHTML = `<div style="font-size:13px; color:var(--muted)">Ошибка: ${escapeHtml(String(e.message || e))}</div>`;
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
    elWeekHint.textContent = "";
    elMonthValue.textContent = m ? `${m.total_hours} ч` : "—";
    elMonthHint.textContent = "";
  }

  function renderActions(actions) {
    elActions.innerHTML = "";
    (actions || []).forEach((a) => {
      if (a && (a.action === "stats" || a.action === "settings")) return;
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
        hapticTap();
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
          openAdmin().catch((e) => {
            if (tg && typeof tg.showAlert === "function") tg.showAlert(String(e.message || e));
            else alert(String(e.message || e));
          });
          return;
        }
        if (action === "notifications") {
          openNotifications().catch(() => setScreen("notifications"));
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
      elWeekHint.textContent = "";

      elMonthValue.textContent = m ? `${m.total_hours} ч` : "—";
      elMonthHint.textContent = "";

      renderActions(data.actions || []);

      setScreen("dashboard");

      try {
        await refreshDashboardStats();
      } catch (e) {}

      try {
        await refreshNotificationsBadge();
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
          if (state.screen === "notifications") {
            setScreen("dashboard");
            return;
          }
          if (state.screen === "reportView") {
            setScreen("stats");
            return;
          }
          setScreen("dashboard");
        });
      }

      if (notificationsBtn) {
        notificationsBtn.addEventListener("click", () => {
          hapticTap();
          openNotifications().catch(() => setScreen("notifications"));
        });
      }

      if (settingsBtn) {
        settingsBtn.addEventListener("click", () => {
          hapticTap();
          setScreen("settings");
        });
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
      if (settingsAvatarFile) settingsAvatarFile.addEventListener("change", onAvatarFileSelected);
      if (settingsAvatarPick && settingsAvatarFile) settingsAvatarPick.addEventListener("click", () => {
        try { settingsAvatarFile.value = ""; } catch (e) {}
        settingsAvatarFile.click();
      });

      if (adminAddRole) {
        adminAddRole.addEventListener("click", async () => {
          try {
            if (adminResult) adminResult.textContent = "";
            const uid = adminUserPick && adminUserPick.value ? Number(adminUserPick.value) : 0;
            const role = adminRole ? String(adminRole.value || "") : "";
            const username = adminUsername ? String(adminUsername.value || "").trim() : "";
            const payload = { role };
            if (uid) payload.user_id = uid;
            if (username) payload.username = username;
            await apiPost("/api/admin/roles", payload);
            toast("Сохранено");
            hapticTap();
            await adminRefreshRoles();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminResult) adminResult.textContent = _ruApiError(e);
          }
        });
      }

      if (adminCropsSort) {
        adminCropsSort.addEventListener("click", () => {
          _adminSortCrops = !_adminSortCrops;
          _toggleBtnActive(adminCropsSort, _adminSortCrops);
          adminRefreshCrops().catch((e) => {
            if (adminCropsResult) adminCropsResult.textContent = _ruApiError(e);
          });
        });
      }
      if (adminCropsAdd) {
        adminCropsAdd.addEventListener("click", async () => {
          try {
            if (adminCropsResult) adminCropsResult.textContent = "";
            const name = adminCropsNew ? String(adminCropsNew.value || "").trim() : "";
            if (!name) {
              if (adminCropsResult) adminCropsResult.textContent = "Введите название культуры";
              return;
            }
            await apiPost("/api/admin/crops", { name });
            if (adminCropsNew) adminCropsNew.value = "";
            toast("Добавлено");
            hapticTap();
            await adminRefreshCrops();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminCropsResult) adminCropsResult.textContent = _ruApiError(e);
          }
        });
      }

      if (adminWareSort) {
        adminWareSort.addEventListener("click", () => {
          _adminSortWare = !_adminSortWare;
          _toggleBtnActive(adminWareSort, _adminSortWare);
          adminRefreshWare().catch((e) => {
            if (adminWareResult) adminWareResult.textContent = _ruApiError(e);
          });
        });
      }
      if (adminWareAdd) {
        adminWareAdd.addEventListener("click", async () => {
          try {
            if (adminWareResult) adminWareResult.textContent = "";
            const name = adminWareNew ? String(adminWareNew.value || "").trim() : "";
            if (!name) {
              if (adminWareResult) adminWareResult.textContent = "Введите название";
              return;
            }
            await apiPost("/api/admin/ware", { name });
            if (adminWareNew) adminWareNew.value = "";
            toast("Добавлено");
            hapticTap();
            await adminRefreshWare();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminWareResult) adminWareResult.textContent = _ruApiError(e);
          }
        });
      }
      if (adminUserPick) {
        adminUserPick.addEventListener("change", async () => {
          try {
            const uid = adminUserPick.value ? Number(adminUserPick.value) : 0;
            if (uid && adminUsername) {
              // try to resolve username by refetching small list (cheap) and matching id
              const data = await apiGet("/api/admin/users?limit=300");
              const u = ((data && data.items) || []).find((x) => String(x.user_id) === String(uid)) || null;
              const uname = u && u.username ? String(u.username) : "";
              adminUsername.value = uname ? (uname.startsWith("@") ? uname : `@${uname}`) : "";
            }
          } catch (e) {}
        });
      }
      if (adminExport) {
        adminExport.addEventListener("click", async () => {
          try {
            if (adminResult) adminResult.textContent = "";
            const r = await apiPost("/api/admin/export", {});
            toast("Экспорт запланирован");
            hapticTap();
            if (adminResult) adminResult.textContent = (r && r.status) ? `Статус: ${r.status}` : "";
            _exportModalSet(true);
            _exportModalRender({ state: "queued", message: "Ожидайте..." });
            _exportStartPolling();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminResult) adminResult.textContent = String(e.message || e);
          }
        });
      }

      if (exportModalClose) {
        exportModalClose.addEventListener("click", () => {
          _exportStopPolling();
          _exportModalSet(false);
        });
      }

      if (adminTabRoles) {
        adminTabRoles.addEventListener("click", () => {
          hapticTap();
          _adminSetTab("roles");
        });
      }
      if (adminTabLocs) {
        adminTabLocs.addEventListener("click", () => {
          hapticTap();
          _adminSetTab("locs");
        });
      }
      if (adminTabCrops) {
        adminTabCrops.addEventListener("click", () => {
          hapticTap();
          _adminSetTab("crops");
        });
      }
      if (adminTabActs) {
        adminTabActs.addEventListener("click", () => {
          hapticTap();
          _adminSetTab("acts");
        });
      }

      if (adminTabMachines) {
        adminTabMachines.addEventListener("click", () => {
          hapticTap();
          _adminSetTab("machines");
        });
      }
      if (adminTabNotify) {
        adminTabNotify.addEventListener("click", () => {
          hapticTap();
          _adminSetTab("notify");
          _adminNotifySyncScheduleBtn();
        });
      }

      if (adminNotifyScheduleBtn && adminNotifySendAt) {
        adminNotifyScheduleBtn.addEventListener("click", () => {
          try {
            hapticTap();
          } catch (e) {}
          try {
            if (typeof adminNotifySendAt.showPicker === "function") {
              adminNotifySendAt.showPicker();
            } else {
              adminNotifySendAt.click();
              adminNotifySendAt.focus();
            }
          } catch (e) {
            try {
              adminNotifySendAt.focus();
            } catch (e2) {}
          }
        });

        adminNotifySendAt.addEventListener("change", () => {
          _adminNotifySyncScheduleBtn();
        });
        adminNotifySendAt.addEventListener("input", () => {
          _adminNotifySyncScheduleBtn();
        });

        _adminNotifySyncScheduleBtn();
      }

      if (adminNotifyRefresh) {
        adminNotifyRefresh.addEventListener("click", () => {
          hapticTap();
          adminRefreshScheduledNotifications().catch((e) => {
            if (adminNotifyResult) adminNotifyResult.textContent = _ruApiError(e);
          });
        });
      }

      if (adminNotifySend) {
        adminNotifySend.addEventListener("click", async () => {
          try {
            if (adminNotifyResult) adminNotifyResult.textContent = "";
            const title = adminNotifyTitle ? String(adminNotifyTitle.value || "").trim() : "";
            const body = adminNotifyBody ? String(adminNotifyBody.value || "").trim() : "";
            const roles = [];
            if (adminNotifyRoleUser && adminNotifyRoleUser.checked) roles.push("user");
            if (adminNotifyRoleBrig && adminNotifyRoleBrig.checked) roles.push("brigadier");
            const sendAtIso = adminNotifySendAt ? _isoFromDatetimeLocal(adminNotifySendAt.value) : "";
            if (!body) {
              if (adminNotifyResult) adminNotifyResult.textContent = "Введите текст";
              return;
            }
            if (!roles.length) {
              if (adminNotifyResult) adminNotifyResult.textContent = "Выберите роли";
              return;
            }
            await apiPost("/api/admin/notifications", {
              title,
              body,
              roles,
              send_at: sendAtIso || null,
            });
            toast(sendAtIso ? "Отложено" : "Отправлено");
            hapticTap();
            if (adminNotifyBody) adminNotifyBody.value = "";
            if (adminNotifyTitle) adminNotifyTitle.value = "";
            if (adminNotifySendAt) adminNotifySendAt.value = "";
            _adminNotifySyncScheduleBtn();
            await adminRefreshScheduledNotifications();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminNotifyResult) adminNotifyResult.textContent = _ruApiError(e);
          }
        });
      }

      if (adminActsTabTech) {
        adminActsTabTech.addEventListener("click", () => {
          hapticTap();
          _adminSetActsGrp("tech");
        });
      }
      if (adminActsTabHand) {
        adminActsTabHand.addEventListener("click", () => {
          hapticTap();
          _adminSetActsGrp("hand");
        });
      }

      if (adminActsSort) {
        adminActsSort.addEventListener("click", () => {
          _adminSortActs = !_adminSortActs;
          _toggleBtnActive(adminActsSort, _adminSortActs);
          adminRefreshActs().catch((e) => {
            if (adminActsResult) adminActsResult.textContent = _ruApiError(e);
          });
        });
      }
      if (adminActsAdd) {
        adminActsAdd.addEventListener("click", async () => {
          try {
            if (adminActsResult) adminActsResult.textContent = "";
            const name = adminActsNew ? String(adminActsNew.value || "").trim() : "";
            if (!name) {
              if (adminActsResult) adminActsResult.textContent = "Введите название работы";
              return;
            }
            await apiPost("/api/admin/activities", { grp: _adminActsGrp, name });
            if (adminActsNew) adminActsNew.value = "";
            toast("Добавлено");
            hapticTap();
            await adminRefreshActs();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminActsResult) adminActsResult.textContent = _ruApiError(e);
          }
        });
      }

      if (adminLocsTabFields) {
        adminLocsTabFields.addEventListener("click", () => {
          hapticTap();
          _adminSetLocsTab("fields");
        });
      }
      if (adminLocsTabWare) {
        adminLocsTabWare.addEventListener("click", () => {
          hapticTap();
          _adminSetLocsTab("ware");
        });
      }

      if (adminMachinesTabKinds) {
        adminMachinesTabKinds.addEventListener("click", () => {
          hapticTap();
          _adminMachinesSetTab("kinds");
        });
      }
      if (adminMachinesTabItems) {
        adminMachinesTabItems.addEventListener("click", () => {
          hapticTap();
          _adminMachinesSetTab("items");
        });
      }
      if (adminMachineKindPick) {
        adminMachineKindPick.addEventListener("change", () => {
          _adminSelectedKindId = adminMachineKindPick.value ? Number(adminMachineKindPick.value) : 0;
          adminRefreshMachines().catch((e) => {
            if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
          });
        });
      }

      if (adminMachinesSort) {
        adminMachinesSort.addEventListener("click", () => {
          _adminSortMachines = !_adminSortMachines;
          _toggleBtnActive(adminMachinesSort, _adminSortMachines);
          adminRefreshMachines().catch((e) => {
            if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
          });
        });
      }
      if (adminMachinesAdd) {
        adminMachinesAdd.addEventListener("click", async () => {
          try {
            if (adminMachinesResult) adminMachinesResult.textContent = "";
            const value = adminMachinesNew ? String(adminMachinesNew.value || "").trim() : "";
            if (!value) {
              if (adminMachinesResult) adminMachinesResult.textContent = "Введите значение";
              return;
            }

            if (_adminMachinesTab === "kinds") {
              await apiPost("/api/admin/machine/kinds", { title: value, mode: "list" });
              if (adminMachinesNew) adminMachinesNew.value = "";
              toast("Добавлено");
              hapticTap();
              await adminRefreshMachines();
              return;
            }

            const kindId = adminMachineKindPick ? Number(adminMachineKindPick.value || 0) : (_adminSelectedKindId || 0);
            if (!kindId) {
              if (adminMachinesResult) adminMachinesResult.textContent = "Выберите тип техники";
              return;
            }
            await apiPost("/api/admin/machine/items", { kind_id: kindId, name: value });
            if (adminMachinesNew) adminMachinesNew.value = "";
            toast("Добавлено");
            hapticTap();
            await adminRefreshMachines();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminMachinesResult) adminMachinesResult.textContent = _ruApiError(e);
          }
        });
      }

      if (adminFieldsSort) {
        adminFieldsSort.addEventListener("click", () => {
          _adminSortFields = !_adminSortFields;
          _toggleBtnActive(adminFieldsSort, _adminSortFields);
          adminRefreshFields().catch((e) => {
            if (adminFieldsResult) adminFieldsResult.textContent = _ruApiError(e);
          });
        });
      }
      if (adminFieldsAdd) {
        adminFieldsAdd.addEventListener("click", async () => {
          try {
            if (adminFieldsResult) adminFieldsResult.textContent = "";
            const name = adminFieldsNew ? String(adminFieldsNew.value || "").trim() : "";
            if (!name) {
              if (adminFieldsResult) adminFieldsResult.textContent = "Введите название поля";
              return;
            }
            await apiPost("/api/admin/fields", { name });
            if (adminFieldsNew) adminFieldsNew.value = "";
            toast("Добавлено");
            hapticTap();
            await adminRefreshFields();
          } catch (e) {
            toast("Ошибка", "error");
            if (adminFieldsResult) adminFieldsResult.textContent = _ruApiError(e);
          }
        });
      }

      if (avatarCropZoom) {
        avatarCropZoom.addEventListener("input", () => {
          _avatarCropState.scale = Number(avatarCropZoom.value || 1);
          _avatarCropDraw();
        });
      }
      if (avatarCropCancel) avatarCropCancel.addEventListener("click", () => setScreen("settings"));
      if (avatarCropSave) avatarCropSave.addEventListener("click", _avatarCropSaveNow);
      _avatarCropBindEvents();

      if (weatherLocSearch) {
        let t = null;
        weatherLocSearch.addEventListener("input", () => {
          if (t) clearTimeout(t);
          t = setTimeout(async () => {
            try {
              const q = weatherLocSearch.value;
              if (!q || q.trim().length < 2) {
                if (weatherLocSearchResults) weatherLocSearchResults.innerHTML = "";
                return;
              }
              const items = await _geoSearch(q);
              _renderGeoResults(items);
            } catch (e) {
              if (weatherLocSearchResults) weatherLocSearchResults.innerHTML = "";
            }
          }, 250);
        });
      }

      // кликабельные карточки недели/месяца
      try {
        const cards = document.querySelectorAll(".miniStat");
        if (cards && cards.length) {
          if (cards[0]) cards[0].addEventListener("click", () => { setScreen("stats"); loadStats("week"); });
          if (cards[1]) cards[1].addEventListener("click", () => { setScreen("stats"); loadStats("month"); });
        }
      } catch (e) {}

      // Telegram BackButton
      try {
        if (tg && tg.BackButton) {
          tg.BackButton.onClick(() => {
            if (state.screen === "reportView") {
              setScreen("stats");
              loadStats(state.stats.mode || "week");
              return;
            }
            if (state.screen === "admin") {
              setScreen("dashboard");
              return;
            }
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
      } catch (e) {}

    } catch (e) {
      showError(e);
    }
  }

  function _renderAdminRoles(items) {
    if (!adminRolesList) return;
    const list = document.createElement("div");
    list.className = "list";
    for (const it of (items || [])) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      const uname = it && it.username ? String(it.username) : "";
      const unameText = uname ? (uname.startsWith("@") ? uname : `@${uname}`) : "";
      const fn = it && it.full_name ? String(it.full_name) : "";
      const who = fn || unameText;
      const roleText = roleLabel(String(it.role || ""));
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(roleText)} · ${escapeHtml(who || "—")}</div>
          <div class="listItem__title">Удалить</div>
        </div>
      `;
      btn.addEventListener("click", async () => {
        try {
          await apiDelete(`/api/admin/roles/${encodeURIComponent(String(it.user_id))}?role=${encodeURIComponent(String(it.role || ""))}`);
          toast("Удалено");
          hapticTap();
          await adminRefreshRoles();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminResult) adminResult.textContent = String(e.message || e);
        }
      });
      list.appendChild(btn);
    }
    adminRolesList.innerHTML = "";
    adminRolesList.appendChild(list);
  }

  async function adminRefreshRoles() {
    const data = await apiGet("/api/admin/roles");
    _renderAdminRoles((data && data.items) || []);
  }

  async function adminRefreshUsers() {
    if (!adminUserPick) return;
    const data = await apiGet("/api/admin/users?limit=300");
    const items = (data && data.items) || [];
    const values = items.map((u) => {
      const uname = u && u.username ? String(u.username) : "";
      const unameText = uname ? (uname.startsWith("@") ? uname : `@${uname}`) : "";
      const fn = u && u.full_name ? String(u.full_name) : "";
      const label = fn || unameText || "—";
      return { value: String(u.user_id), label };
    });
    _fillSelect(adminUserPick, values, "Выберите сотрудника");
  }

  function _renderAdminFields(items) {
    if (!adminFieldsList) return;
    const list = document.createElement("div");
    list.className = "list";
    for (const it of (items || [])) {
      const row = document.createElement("div");
      row.classList.add("listRow--sortable");
      row.setAttribute("data-id", String(it.id));
      row.style.display = "grid";
      row.style.gridTemplateColumns = "1fr auto";
      row.style.gap = "10px";
      row.style.alignItems = "center";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(String(it.name || "—"))}</div>
        </div>
      `;

      const actions = document.createElement("div");
      actions.style.display = "grid";
      actions.style.gridTemplateColumns = "auto auto";
      actions.style.gap = "8px";

      const renameBtn = document.createElement("button");
      renameBtn.type = "button";
      renameBtn.className = "btn btn--secondary";
      renameBtn.textContent = "✏️";
      renameBtn.title = "Переименовать";
      renameBtn.setAttribute("aria-label", "Переименовать");

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn--secondary";
      delBtn.textContent = "🗑️";
      delBtn.title = "Удалить";
      delBtn.setAttribute("aria-label", "Удалить");

      renameBtn.addEventListener("click", async () => {
        try {
          const current = String(it.name || "");
          const p = prompt("Новое название поля", current);
          if (p === null) return;
          const next = String(p || "").trim();
          if (!next) return;
          await apiPatch(`/api/admin/fields/${encodeURIComponent(String(it.id))}`, { name: next });
          toast("Сохранено");
          hapticTap();
          await adminRefreshFields();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminFieldsResult) adminFieldsResult.textContent = _ruApiError(e);
        }
      });

      delBtn.addEventListener("click", async () => {
        try {
          const name = String(it.name || "");
          const ok = confirm(`Удалить «${name}»?`);
          if (!ok) return;
          await apiDelete(`/api/admin/fields/${encodeURIComponent(String(it.id))}`);
          toast("Удалено");
          hapticTap();
          await adminRefreshFields();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminFieldsResult) adminFieldsResult.textContent = _ruApiError(e);
        }
      });

      if (_adminSortFields) {
        _addSortArrows(row, actions, list, async (ids) => {
          await apiPost("/api/admin/fields/reorder", { ids });
          toast("Порядок сохранён");
          hapticTap();
        });
      } else {
        actions.appendChild(renameBtn);
        actions.appendChild(delBtn);
      }

      row.appendChild(btn);
      row.appendChild(actions);
      list.appendChild(row);
    }
    adminFieldsList.innerHTML = "";
    adminFieldsList.appendChild(list);

    if (_adminSortFields) {
      _enableListDnD(list, async (ids) => {
        await apiPost("/api/admin/fields/reorder", { ids });
        toast("Порядок сохранён");
        hapticTap();
      });
    }
  }

  function _renderAdminWare(items) {
    if (!adminWareList) return;
    const list = document.createElement("div");
    list.className = "list";
    for (const it of (items || [])) {
      const row = document.createElement("div");
      row.classList.add("listRow--sortable");
      row.setAttribute("data-id", String(it.id));
      row.style.display = "grid";
      row.style.gridTemplateColumns = "1fr auto";
      row.style.gap = "10px";
      row.style.alignItems = "center";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(String(it.name || "—"))}</div>
        </div>
      `;

      const actions = document.createElement("div");
      actions.style.display = "grid";
      actions.style.gridTemplateColumns = "auto auto";
      actions.style.gap = "8px";

      const renameBtn = document.createElement("button");
      renameBtn.type = "button";
      renameBtn.className = "btn btn--secondary";
      renameBtn.textContent = "✏️";
      renameBtn.title = "Переименовать";
      renameBtn.setAttribute("aria-label", "Переименовать");

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn--secondary";
      delBtn.textContent = "🗑️";
      delBtn.title = "Удалить";
      delBtn.setAttribute("aria-label", "Удалить");

      renameBtn.addEventListener("click", async () => {
        try {
          const current = String(it.name || "");
          const p = prompt("Новое название", current);
          if (p === null) return;
          const next = String(p || "").trim();
          if (!next) return;
          await apiPatch(`/api/admin/ware/${encodeURIComponent(String(it.id))}`, { name: next });
          toast("Сохранено");
          hapticTap();
          await adminRefreshWare();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminWareResult) adminWareResult.textContent = _ruApiError(e);
        }
      });

      delBtn.addEventListener("click", async () => {
        try {
          const name = String(it.name || "");
          const ok = confirm(`Удалить «${name}»?`);
          if (!ok) return;
          await apiDelete(`/api/admin/ware/${encodeURIComponent(String(it.id))}`);
          toast("Удалено");
          hapticTap();
          await adminRefreshWare();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminWareResult) adminWareResult.textContent = _ruApiError(e);
        }
      });

      if (_adminSortWare) {
        _addSortArrows(row, actions, list, async (ids) => {
          await apiPost("/api/admin/ware/reorder", { ids });
          toast("Порядок сохранён");
          hapticTap();
        });
      } else {
        actions.appendChild(renameBtn);
        actions.appendChild(delBtn);
      }

      row.appendChild(btn);
      row.appendChild(actions);
      list.appendChild(row);
    }
    adminWareList.innerHTML = "";
    adminWareList.appendChild(list);

    if (_adminSortWare) {
      _enableListDnD(list, async (ids) => {
        await apiPost("/api/admin/ware/reorder", { ids });
        toast("Порядок сохранён");
        hapticTap();
      });
    }
  }

  async function adminRefreshFields() {
    if (adminFieldsResult) adminFieldsResult.textContent = "";
    const data = await apiGet("/api/admin/fields?limit=300");
    _renderAdminFields((data && data.items) || []);
  }

  async function adminRefreshWare() {
    if (adminWareResult) adminWareResult.textContent = "";
    const data = await apiGet("/api/admin/ware?limit=300");
    _renderAdminWare((data && data.items) || []);
  }

  function _renderAdminActs(items) {
    if (!adminActsList) return;
    const list = document.createElement("div");
    list.className = "list";
    for (const it of (items || [])) {
      const row = document.createElement("div");
      row.classList.add("listRow--sortable");
      row.setAttribute("data-id", String(it.id));
      row.style.display = "grid";
      row.style.gridTemplateColumns = "1fr auto";
      row.style.gap = "10px";
      row.style.alignItems = "center";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(String(it.name || "—"))}</div>
        </div>
      `;

      const actions = document.createElement("div");
      actions.style.display = "grid";
      actions.style.gridTemplateColumns = "auto auto";
      actions.style.gap = "8px";

      const renameBtn = document.createElement("button");
      renameBtn.type = "button";
      renameBtn.className = "btn btn--secondary";
      renameBtn.textContent = "✏️";
      renameBtn.title = "Переименовать";
      renameBtn.setAttribute("aria-label", "Переименовать");

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn--secondary";
      delBtn.textContent = "🗑️";
      delBtn.title = "Удалить";
      delBtn.setAttribute("aria-label", "Удалить");

      renameBtn.addEventListener("click", async () => {
        try {
          const current = String(it.name || "");
          const p = prompt("Новое название работы", current);
          if (p === null) return;
          const next = String(p || "").trim();
          if (!next) return;
          await apiPatch(`/api/admin/activities/${encodeURIComponent(String(it.id))}`, { name: next });
          toast("Сохранено");
          hapticTap();
          await adminRefreshActs();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminActsResult) adminActsResult.textContent = _ruApiError(e);
        }
      });

      delBtn.addEventListener("click", async () => {
        try {
          const name = String(it.name || "");
          const ok = confirm(`Удалить «${name}»?`);
          if (!ok) return;
          await apiDelete(`/api/admin/activities/${encodeURIComponent(String(it.id))}`);
          toast("Удалено");
          hapticTap();
          await adminRefreshActs();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminActsResult) adminActsResult.textContent = _ruApiError(e);
        }
      });

      if (_adminSortActs) {
        const grp = _adminActsGrp === "hand" ? "hand" : "tech";
        _addSortArrows(row, actions, list, async (ids) => {
          await apiPost("/api/admin/activities/reorder", { grp, ids });
          toast("Порядок сохранён");
          hapticTap();
        });
      } else {
        actions.appendChild(renameBtn);
        actions.appendChild(delBtn);
      }
      row.appendChild(btn);
      row.appendChild(actions);
      list.appendChild(row);
    }
    adminActsList.innerHTML = "";
    adminActsList.appendChild(list);

    if (_adminSortActs) {
      const grp = _adminActsGrp === "hand" ? "hand" : "tech";
      _enableListDnD(list, async (ids) => {
        await apiPost("/api/admin/activities/reorder", { grp, ids });
        toast("Порядок сохранён");
        hapticTap();
      });
    }
  }

  async function adminRefreshActs() {
    if (adminActsResult) adminActsResult.textContent = "";
    const grp = _adminActsGrp === "hand" ? "hand" : "tech";
    const data = await apiGet(`/api/admin/activities?limit=300&grp=${encodeURIComponent(grp)}`);
    _renderAdminActs((data && data.items) || []);
  }

  function _renderAdminCrops(items) {
    if (!adminCropsList) return;
    const list = document.createElement("div");
    list.className = "list";
    for (const it of (items || [])) {
      const row = document.createElement("div");
      row.classList.add("listRow--sortable");
      row.setAttribute("data-id", String(it.id));
      row.style.display = "grid";
      row.style.gridTemplateColumns = "1fr auto";
      row.style.gap = "10px";
      row.style.alignItems = "center";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "listItem";
      btn.innerHTML = `
        <div class="listItem__top">
          <div class="listItem__title">${escapeHtml(String(it.name || "—"))}</div>
        </div>
      `;

      const actions = document.createElement("div");
      actions.style.display = "grid";
      actions.style.gridTemplateColumns = "auto auto";
      actions.style.gap = "8px";

      const renameBtn = document.createElement("button");
      renameBtn.type = "button";
      renameBtn.className = "btn btn--secondary";
      renameBtn.textContent = "✏️";
      renameBtn.title = "Переименовать";
      renameBtn.setAttribute("aria-label", "Переименовать");

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn--secondary";
      delBtn.textContent = "🗑️";
      delBtn.title = "Удалить";
      delBtn.setAttribute("aria-label", "Удалить");

      renameBtn.addEventListener("click", async () => {
        try {
          const current = String(it.name || "");
          const p = prompt("Новое название культуры", current);
          if (p === null) return;
          const next = String(p || "").trim();
          if (!next) return;
          await apiPatch(`/api/admin/crops/${encodeURIComponent(String(it.id))}`, { name: next });
          toast("Сохранено");
          hapticTap();
          await adminRefreshCrops();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminCropsResult) adminCropsResult.textContent = _ruApiError(e);
        }
      });

      delBtn.addEventListener("click", async () => {
        try {
          const name = String(it.name || "");
          const ok = confirm(`Удалить «${name}»?`);
          if (!ok) return;
          await apiDelete(`/api/admin/crops/${encodeURIComponent(String(it.id))}`);
          toast("Удалено");
          hapticTap();
          await adminRefreshCrops();
        } catch (e) {
          toast("Ошибка", "error");
          if (adminCropsResult) adminCropsResult.textContent = _ruApiError(e);
        }
      });

      if (_adminSortCrops) {
        _addSortArrows(row, actions, list, async (ids) => {
          await apiPost("/api/admin/crops/reorder", { ids });
          toast("Порядок сохранён");
          hapticTap();
        });
      } else {
        actions.appendChild(renameBtn);
        actions.appendChild(delBtn);
      }
      row.appendChild(btn);
      row.appendChild(actions);
      list.appendChild(row);
    }
    adminCropsList.innerHTML = "";
    adminCropsList.appendChild(list);

    if (_adminSortCrops) {
      _enableListDnD(list, async (ids) => {
        await apiPost("/api/admin/crops/reorder", { ids });
        toast("Порядок сохранён");
        hapticTap();
      });
    }
  }

  async function adminRefreshCrops() {
    if (adminCropsResult) adminCropsResult.textContent = "";
    const data = await apiGet("/api/admin/crops?limit=300");
    _renderAdminCrops((data && data.items) || []);
  }

  async function openAdmin() {
    setScreen("admin");
    if (adminResult) adminResult.textContent = "";
    try {
      await adminRefreshUsers();
      await adminRefreshRoles();
      _adminSetTab("roles");
    } catch (e) {
      if (adminResult) adminResult.textContent = String(e.message || e);
      throw e;
    }
  }

  load();
})();
