/* SolarBridge print-view report (/report?days=N or ?from=&to=).
   Standalone from app.js: fetches finance/health/current/history/master and
   renders a print-optimised page; the browser's Ctrl+P produces the PDF. */
(() => {
  "use strict";

  const translations = {
    ru: {
      "page.title": "Отчёт · HIDEN",
      "page.description": "Отчёт SolarBridge: энергия и деньги за период",
      "report.custom_from": "с",
      "report.custom_to": "по",
      "report.print": "Печать / PDF",
      "report.device": "HS-20-5548 PRO",
      "report.heading": "Отчёт за период",
      "report.master": "master_id",
      "report.model": "Модель",
      "report.serial": "Serial",
      "report.firmware": "Firmware",
      "report.printed": "Печатано",
      "report.period": "Период",
      "report.summary_title": "Сводка за период",
      "report.chart_title_days": "Энергия по дням",
      "report.chart_title_months": "Энергия по месяцам",
      "report.table_days": "По суткам",
      "report.table_months": "По месяцам",
      "report.leg_pv": "PV генерация",
      "report.leg_load": "Нагрузка",
      "report.leg_buy": "Из сети",
      "report.records_title": "Рекорды периода",
      "report.rec_pv_day": "Рекорд PV за день",
      "report.rec_load_day": "Рекорд нагрузки за день",
      "report.rec_buy_day": "Максимум покупки за день",
      "report.rec_best_day": "Лучший день по итогу",
      "report.rec_peak_load": "Пик нагрузки",
      "report.rec_peak_pv": "Пик PV",
      "report.rec_avg_note": "среднее за час",
      "report.rec_instant_note": "мгновенный максимум",
      "report.batteries_title": "Батареи · снимок на момент отчёта",
      "report.events_title": "События мастера",
      "report.footer_note": "Read-only данные из БД SolarBridge · тарифы применяются на дату · Ctrl+P → сохранить как PDF",
      "report.kpi_pv": "PV генерация",
      "report.kpi_load": "Нагрузка",
      "report.kpi_buy": "Куплено из сети",
      "report.kpi_sell": "PV в сеть дома",
      "report.kpi_charge": "Заряд батареи",
      "report.kpi_discharge": "Разряд батареи",
      "report.kpi_savings": "Экономия PV",
      "report.kpi_costs": "Расходы",
      "report.kpi_net": "Итог (экономия − расходы)",
      "report.charge_pv_short": "из PV",
      "report.charge_grid_short": "из сети",
      "report.th_date": "Дата",
      "report.th_pv": "PV, kWh",
      "report.th_load": "Нагрузка, kWh",
      "report.th_buy": "Из сети, kWh",
      "report.th_sell": "PV в сеть, kWh",
      "report.th_charge": "Заряд (PV/сеть), kWh",
      "report.th_discharge": "Разряд, kWh",
      "report.th_tariff": "Тариф, ₽/кВт·ч",
      "report.th_savings": "Экономия, ₽",
      "report.th_costs": "Расходы, ₽",
      "report.th_net": "Итог, ₽",
      "report.th_total": "Итого",
      "report.b_module": "Модуль",
      "report.b_soc": "SOC, %",
      "report.b_voltage": "Напряжение, V",
      "report.b_current": "Ток, A",
      "report.b_soh": "SOH, %",
      "report.b_cycles": "Циклы",
      "report.b_delta": "Δ ячеек, mV",
      "report.b_temp": "T, °C",
      "report.ev_at": "Время",
      "report.ev_event": "Событие",
      "report.ev_detail": "Детали",
      "report.no_tariff": "тариф не задан",
      "report.incl_short": "в т.ч.",
      "report.auth_required": "Требуется вход — авторизуйтесь на главной странице (/)",
      "report.coverage": "Данных за {n} ч",
      "report.month": "{month} {year}",
      "report.no_data": "Нет данных за период",
    },
    en: {
      "page.title": "Report · HIDEN",
      "page.description": "SolarBridge report: energy and money for a period",
      "report.custom_from": "from",
      "report.custom_to": "to",
      "report.print": "Print / PDF",
      "report.device": "HS-20-5548 PRO",
      "report.heading": "Period report",
      "report.master": "master_id",
      "report.model": "Model",
      "report.serial": "Serial",
      "report.firmware": "Firmware",
      "report.printed": "Printed",
      "report.period": "Period",
      "report.summary_title": "Period summary",
      "report.chart_title_days": "Energy by day",
      "report.chart_title_months": "Energy by month",
      "report.table_days": "By day",
      "report.table_months": "By month",
      "report.leg_pv": "PV generation",
      "report.leg_load": "Load",
      "report.leg_buy": "From grid",
      "report.records_title": "Period records",
      "report.rec_pv_day": "Best PV day",
      "report.rec_load_day": "Best load day",
      "report.rec_buy_day": "Highest purchase day",
      "report.rec_best_day": "Best day by net result",
      "report.rec_peak_load": "Load peak",
      "report.rec_peak_pv": "PV peak",
      "report.rec_avg_note": "hourly average",
      "report.rec_instant_note": "instant maximum",
      "report.batteries_title": "Batteries · snapshot at report time",
      "report.events_title": "Master events",
      "report.footer_note": "Read-only data from the SolarBridge DB · tariffs applied per date · Ctrl+P → save as PDF",
      "report.kpi_pv": "PV generation",
      "report.kpi_load": "Load",
      "report.kpi_buy": "Bought from grid",
      "report.kpi_sell": "PV into house grid",
      "report.kpi_charge": "Battery charge",
      "report.kpi_discharge": "Battery discharge",
      "report.kpi_savings": "PV savings",
      "report.kpi_costs": "Costs",
      "report.kpi_net": "Net (savings − costs)",
      "report.charge_pv_short": "from PV",
      "report.charge_grid_short": "from grid",
      "report.th_date": "Date",
      "report.th_pv": "PV, kWh",
      "report.th_load": "Load, kWh",
      "report.th_buy": "From grid, kWh",
      "report.th_sell": "PV into house grid, kWh",
      "report.th_charge": "Charge (PV/grid), kWh",
      "report.th_discharge": "Discharge, kWh",
      "report.th_tariff": "Tariff, ₽/kWh",
      "report.th_savings": "Savings, ₽",
      "report.th_costs": "Costs, ₽",
      "report.th_net": "Net, ₽",
      "report.th_total": "Total",
      "report.b_module": "Module",
      "report.b_soc": "SOC, %",
      "report.b_voltage": "Voltage, V",
      "report.b_current": "Current, A",
      "report.b_soh": "SOH, %",
      "report.b_cycles": "Cycles",
      "report.b_delta": "Cell Δ, mV",
      "report.b_temp": "T, °C",
      "report.ev_at": "Time",
      "report.ev_event": "Event",
      "report.ev_detail": "Details",
      "report.no_tariff": "no tariff set",
      "report.incl_short": "incl.",
      "report.auth_required": "Sign-in required — log in on the main page (/)",
      "report.coverage": "Data for {n} h",
      "report.month": "{month} {year}",
      "report.no_data": "No data for the period",
    },
  };

  const MONTHS = {
    ru: ["январь", "февраль", "март", "апрель", "май", "июнь",
         "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"],
    en: ["January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"],
  };

  const state = {
    language: readLanguage(),
    days: 30,
    from: null,
    to: null,
    finance: null,
    health: null,
    current: null,
    history: null,
    events: null,
  };

  const $ = (id) => document.getElementById(id);
  const setText = (id, value) => { const node = $(id); if (node) node.textContent = value; };
  const safeNumber = (value) => typeof value === "number" && Number.isFinite(value);
  const SUM_FIELDS = ["pv_kwh", "load_kwh", "grid_buy_kwh", "grid_sell_kwh",
    "batt_charge_kwh", "batt_charge_from_pv_kwh", "batt_charge_from_grid_kwh",
    "batt_discharge_kwh", "pv_savings", "grid_buy_cost", "charge_grid_cost", "net"];

  function readLanguage() {
    try {
      return localStorage.getItem("hiden-control-language") === "en" ? "en" : "ru";
    } catch (error) {
      return "ru";
    }
  }

  function t(key) {
    return translations[state.language][key] || translations.ru[key] || key;
  }

  function locale() { return state.language === "en" ? "en-GB" : "ru-RU"; }

  function number(value, decimals = 0) {
    if (!safeNumber(value)) return "--";
    return new Intl.NumberFormat(locale(), { maximumFractionDigits: decimals, minimumFractionDigits: decimals }).format(value);
  }

  function money(rub) {
    return safeNumber(rub) ? `${number(rub, 2)} ₽` : "--";
  }

  function kwh(value) { return safeNumber(value) ? `${number(value, 2)}` : "--"; }

  function localDateKey(offsetDays = 0) {
    const date = new Date(Date.now() - offsetDays * 86400000);
    const pad = (part) => String(part).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  function dayLabel(dateStr) {
    const date = new Date(`${dateStr}T00:00:00`);
    if (Number.isNaN(date.getTime())) return dateStr;
    return new Intl.DateTimeFormat(locale(), { day: "numeric", month: "long" }).format(date);
  }

  function timestampLabel(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "--";
    return new Intl.DateTimeFormat(locale(), { dateStyle: "short", timeStyle: "short" }).format(date);
  }

  function printStamp() {
    return new Intl.DateTimeFormat(locale(), { dateStyle: "medium", timeStyle: "medium" }).format(new Date());
  }

  async function getJson(url) {
    const headers = { Accept: "application/json" };
    let token = "";
    try { token = localStorage.getItem("sbridge-auth-token") || ""; } catch (error) { /* private mode */ }
    if (token) headers["X-Auth-Token"] = token;
    const response = await fetch(url, { headers });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  // ------------------------------------------------------------------ data

  async function loadData() {
    const tz = new Date().getTimezoneOffset();
    const days = effectiveDays();
    const financeUrl = state.to
      ? `/api/finance?days=${days}&tz=${tz}&to=${encodeURIComponent(state.to)}`
      : `/api/finance?days=${days}&tz=${tz}`;
    const historyUrl = historyQuery();
    const [finance, health, current, history, events] = await Promise.all([
      getJson(financeUrl),
      getJson("/api/health").catch(() => null),
      getJson("/api/current").catch(() => null),
      getJson(historyUrl).catch(() => null),
      getJson("/api/master").catch(() => null),
    ]);
    state.finance = finance;
    state.health = health || (current && current.health) || null;
    state.current = current;
    state.history = history;
    state.events = events && events.events ? events : null;
    renderAll();
  }

  function effectiveDays() {
    if (!state.from || !state.to) return state.days;
    const fromTs = new Date(`${state.from}T00:00:00`).getTime();
    const toTs = new Date(`${state.to}T00:00:00`).getTime();
    return Math.max(1, Math.min(400, Math.round((toTs - fromTs) / 86400000) + 1));
  }

  function historyQuery() {
    if (state.from && state.to) {
      const fromTs = Math.floor(new Date(`${state.from}T00:00:00`).getTime() / 1000);
      const toTs = Math.floor(new Date(`${state.to}T23:59:59`).getTime() / 1000);
      return `/api/history?from=${fromTs}&to=${toTs}&period=${effectiveDays() > 90 ? "day" : "hour"}`;
    }
    const range = state.days > 90 ? "1y" : state.days > 30 ? "90d" : state.days >= 7 ? "7d" : "24h";
    const period = state.days > 90 ? "day" : "hour";
    return `/api/history?range=${range}&period=${period}`;
  }

  function periodBounds() {
    // [startTsMs, endTsMs] of the requested window in ms, for history slicing.
    if (state.from && state.to) {
      return [new Date(`${state.from}T00:00:00`).getTime(), new Date(`${state.to}T23:59:59`).getTime()];
    }
    const now = Date.now();
    return [now - effectiveDays() * 86400000, now];
  }

  // ------------------------------------------------------------------ render

  function renderAll() {
    applyStaticTexts();
    renderTitle();
    renderSummary();
    renderChart();
    renderTable();
    renderRecords();
    renderBatteries();
    renderEvents();
    setText("footerVersionReport", state.health && state.health.version ? `v${state.health.version}` : "--");
  }

  function applyStaticTexts() {
    document.documentElement.lang = state.language;
    document.title = t("page.title");
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = t("page.description");
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
    document.querySelectorAll("[data-lang]").forEach((button) => {
      const active = button.dataset.lang === state.language;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  function renderTitle() {
    const subParts = [];
    if (state.from && state.to) {
      subParts.push(`${t("report.period")}: ${dayLabel(state.from)} — ${dayLabel(state.to)}`);
    } else {
      subParts.push(`${t("report.period")}: ${t("report.custom_from")} ${dayLabel(localDateKey(state.days - 1))} ${t("report.custom_to")} ${dayLabel(localDateKey(0))}`);
    }
    const health = state.health || {};
    setText("reportSub", subParts.join(" · "));
    setText("metaMaster", health.master_id || (state.current && state.current.host && state.current.host.master_id) || "--");
    const data = state.current && state.current.data;
    const identity = data && data.identity;
    setText("metaModel", identity && identity.model ? identity.model : "--");
    setText("metaSerial", identity && identity.serial_number ? identity.serial_number : "--");
    setText("metaFirmware", identity && identity.software_version ? identity.software_version : "--");
    setText("metaPrinted", printStamp());
    setText("metaVersion", health.version ? `v${health.version}` : "--");
  }

  function summarise(rows) {
    const totals = Object.fromEntries(SUM_FIELDS.map((key) => [key, 0.0]));
    const tariffs = new Set();
    let hours = 0.0;
    rows.forEach((row) => {
      SUM_FIELDS.forEach((key) => { totals[key] += safeNumber(row[key]) ? row[key] : 0; });
      if (safeNumber(row.tariff)) tariffs.add(row.tariff);
      hours += safeNumber(row.hours) ? row.hours : 0;
    });
    return { totals, tariffs: [...tariffs].sort((a, b) => a - b), hours, rows };
  }

  function renderSummary() {
    const section = $("reportSummary");
    if (!section) return;
    const { totals, tariffs, hours } = summarise(financeRows());
    const hasData = financeRows().length > 0;
    section.hidden = !hasData;
    if (!hasData) return;
    const grid = $("summaryGrid");
    grid.textContent = "";
    const items = [
      ["report.kpi_pv", `${kwh(totals.pv_kwh)} kWh`, "is-pv"],
      ["report.kpi_load", `${kwh(totals.load_kwh)} kWh`, "is-load"],
      ["report.kpi_buy", `${kwh(totals.grid_buy_kwh)} kWh · ${money(totals.grid_buy_cost)}`, "is-buy"],
      ["report.kpi_sell", `${kwh(totals.grid_sell_kwh)} kWh`, "is-sell"],
      ["report.kpi_charge", `${kwh(totals.batt_charge_kwh)} kWh (${kwh(totals.batt_charge_from_pv_kwh)}/${kwh(totals.batt_charge_from_grid_kwh)})`, "is-batt"],
      ["report.kpi_discharge", `${kwh(totals.batt_discharge_kwh)} kWh`, "is-batt"],
      ["report.kpi_savings", money(totals.pv_savings), "is-good"],
      ["report.kpi_costs", `${money(totals.grid_buy_cost)} ${safeNumber(totals.charge_grid_cost) && totals.charge_grid_cost > 0 ? `(${t("report.incl_short")} ${money(totals.charge_grid_cost)})` : ""}`, "is-cost"],
      ["report.kpi_net", money(totals.net), totals.net >= 0 ? "is-good" : "is-cost"],
    ];
    items.forEach(([labelKey, value, cls]) => {
      const cell = document.createElement("div");
      cell.className = `report-kpi ${cls}`;
      const label = document.createElement("span");
      label.textContent = t(labelKey);
      const strong = document.createElement("strong");
      strong.textContent = value;
      cell.append(label, strong);
      grid.append(cell);
    });
    const tariffText = tariffs.length
      ? tariffs.map((price) => `${number(price, 2)} ₽/кВт·ч`).join(" · ")
      : t("report.no_tariff");
    setText("summaryNote", `${t("report.th_tariff")}: ${tariffText} · ${t("report.coverage").replace("{n}", number(hours, 0))}`);
  }

  function financeRows() {
    return (state.finance && state.finance.rows) || [];
  }

  function renderChart() {
    const block = $("chartBlock");
    if (!block) return;
    const rows = financeRows().filter((row) => row.hours > 0);
    block.hidden = rows.length === 0;
    if (!rows.length) return;
    const monthly = rows.length > 90;
    const heading = block.querySelector("h2");
    if (heading) heading.textContent = t(monthly ? "report.chart_title_months" : "report.chart_title_days");
    const buckets = monthly ? groupByMonth(rows) : rows.map((row) => ({
      label: monthly ? "" : dayLabel(row.date),
      short: monthly ? "" : row.date.slice(8),
      pv: row.pv_kwh, load: row.load_kwh, buy: row.grid_buy_kwh,
    }));
    if (monthly) headingSet(monthly);
    const holder = $("reportChart");
    holder.textContent = "";
    holder.append(chartSvg(buckets, monthly));
  }

  function headingSet(monthly) { /* title already switched in renderChart */ }

  function groupByMonth(rows) {
    const map = new Map();
    rows.forEach((row) => {
      const key = row.date.slice(0, 7);
      const bucket = map.get(key) || { key, pv: 0, load: 0, buy: 0 };
      bucket.pv += safeNumber(row.pv_kwh) ? row.pv_kwh : 0;
      bucket.load += safeNumber(row.load_kwh) ? row.load_kwh : 0;
      bucket.buy += safeNumber(row.grid_buy_kwh) ? row.grid_buy_kwh : 0;
      map.set(key, bucket);
    });
    return [...map.values()].map((bucket) => {
      const [year, month] = bucket.key.split("-");
      return {
        label: t("report.month").replace("{month}", MONTHS[state.language][Number(month) - 1]).replace("{year}", year),
        short: MONTHS[state.language][Number(month) - 1].slice(0, 3),
        pv: bucket.pv, load: bucket.load, buy: bucket.buy,
      };
    });
  }

  function chartSvg(buckets, monthly) {
    const width = Math.max(760, buckets.length * (monthly ? 90 : 16) + 90);
    const height = 240;
    const padding = { top: 16, right: 12, bottom: 30, left: 48 };
    const innerW = width - padding.left - padding.right;
    const innerH = height - padding.top - padding.bottom;
    const max = Math.max(0.5, ...buckets.map((b) => Math.max(b.pv, b.load, b.buy)));
    const barGroup = innerW / buckets.length;
    const barW = monthly ? Math.min(30, barGroup * 0.72) : Math.max(2.5, Math.min(8, barGroup * 0.78));
    const y = (value) => padding.top + innerH - (value / max) * innerH;
    let out = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" role="img">`;
    for (let i = 0; i <= 4; i += 1) {
      const lineY = padding.top + innerH * i / 4;
      out += `<line x1="${padding.left}" y1="${lineY}" x2="${width - padding.right}" y2="${lineY}" class="rc-grid"/>`;
      out += `<text x="${padding.left - 6}" y="${lineY + 3}" class="rc-axis" text-anchor="end">${number(max - max * i / 4, 0)}</text>`;
    }
    buckets.forEach((bucket, index) => {
      const x0 = padding.left + index * barGroup + (barGroup - barW * 3 - 4) / 2;
      out += `<rect x="${x0}" y="${y(bucket.pv)}" width="${barW}" height="${Math.max(0.5, padding.top + innerH - y(bucket.pv))}" class="rc-pv"/>`;
      out += `<rect x="${x0 + barW + 2}" y="${y(bucket.load)}" width="${barW}" height="${Math.max(0.5, padding.top + innerH - y(bucket.load))}" class="rc-load"/>`;
      out += `<rect x="${x0 + barW * 2 + 4}" y="${y(bucket.buy)}" width="${barW}" height="${Math.max(0.5, padding.top + innerH - y(bucket.buy))}" class="rc-buy"/>`;
      const step = Math.ceil(buckets.length / 14);
      if (index % step === 0) {
        const label = monthly ? bucket.short : bucket.short;
        out += `<text x="${x0 + barW * 1.5 + 2}" y="${height - 8}" class="rc-axis" text-anchor="middle">${label}</text>`;
      }
    });
    out += "</svg>";
    const template = document.createElement("template");
    template.innerHTML = out.trim();
    return template.content.firstElementChild;
  }

  function renderTable() {
    const block = $("tableBlock");
    if (!block) return;
    const rows = financeRows();
    block.hidden = rows.length === 0;
    if (!rows.length) return;
    const monthly = rows.length > 62;
    setText("tableTitle", t(monthly ? "report.table_months" : "report.table_days"));
    const tableRows = monthly ? groupByMonthFull(rows) : rows;
    const head = $("tableHead");
    const body = $("tableBody");
    const foot = $("tableFoot");
    head.textContent = "";
    body.textContent = "";
    foot.textContent = "";
    const headRow = document.createElement("tr");
    ["report.th_date", "report.th_pv", "report.th_load", "report.th_buy", "report.th_sell",
     "report.th_charge", "report.th_discharge", "report.th_tariff", "report.th_savings",
     "report.th_costs", "report.th_net"].forEach((key) => {
      const th = document.createElement("th");
      th.textContent = t(key);
      headRow.append(th);
    });
    head.append(headRow);
    const { totals } = summarise(rows);
    tableRows.forEach((row) => {
      const tr = document.createElement("tr");
      const cells = [
        row.date ? (monthly ? row.date : dayLabel(row.date)) : "",
        kwh(row.pv_kwh),
        kwh(row.load_kwh),
        kwh(row.grid_buy_kwh),
        kwh(row.grid_sell_kwh),
        safeNumber(row.batt_charge_kwh)
          ? `${kwh(row.batt_charge_kwh)} (${kwh(row.batt_charge_from_pv_kwh)}/${kwh(row.batt_charge_from_grid_kwh)})`
          : "--",
        kwh(row.batt_discharge_kwh),
        safeNumber(row.tariff) ? number(row.tariff, 2) : t("report.no_tariff"),
        money(row.pv_savings),
        money(row.grid_buy_cost),
        money(row.net),
      ];
      cells.forEach((value, index) => {
        const td = document.createElement("td");
        td.textContent = value;
        if (index > 0) td.classList.add("num");
        if (index === 10 && safeNumber(row.net)) td.classList.add(row.net >= 0 ? "good" : "bad");
        tr.append(td);
      });
      body.append(tr);
    });
    const footRow = document.createElement("tr");
    const footCells = [
      t("report.th_total"),
      kwh(totals.pv_kwh),
      kwh(totals.load_kwh),
      kwh(totals.grid_buy_kwh),
      kwh(totals.grid_sell_kwh),
      safeNumber(totals.batt_charge_kwh)
        ? `${kwh(totals.batt_charge_kwh)} (${kwh(totals.batt_charge_from_pv_kwh)}/${kwh(totals.batt_charge_from_grid_kwh)})`
        : "--",
      kwh(totals.batt_discharge_kwh),
      "",
      money(totals.pv_savings),
      money(totals.grid_buy_cost),
      money(totals.net),
    ];
    footCells.forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index > 0) td.classList.add("num");
      footRow.append(td);
    });
    foot.append(footRow);
  }

  function groupByMonthFull(rows) {
    const map = new Map();
    rows.forEach((row) => {
      const key = row.date.slice(0, 7) + "-01";
      const bucket = map.get(key) || { date: key, hours: 0 };
      SUM_FIELDS.forEach((fieldKey) => {
        bucket[fieldKey] = (bucket[fieldKey] || 0) + (safeNumber(row[fieldKey]) ? row[fieldKey] : 0);
      });
      bucket.hours += safeNumber(row.hours) ? row.hours : 0;
      if (safeNumber(row.tariff)) bucket.tariff = row.tariff;
      map.set(key, bucket);
    });
    return [...map.values()];
  }

  function renderRecords() {
    const block = $("recordsBlock");
    if (!block) return;
    const rows = financeRows();
    const history = (state.history && state.history.points) || [];
    if (!rows.length && !history.length) { block.hidden = true; return; }
    block.hidden = false;
    const grid = $("recordsGrid");
    grid.textContent = "";
    const withData = rows.filter((row) => row.hours > 0);
    const maxBy = (key) => withData.reduce((best, row) => ((safeNumber(row[key]) ? row[key] : 0) > (safeNumber(best[key]) ? best[key] : 0) ? row : best), withData[0]);
    const items = [];
    if (withData.length) {
      const pv = maxBy("pv_kwh");
      items.push(["report.rec_pv_day", `${kwh(pv.pv_kwh)} kWh`, dayLabel(pv.date)]);
      const load = maxBy("load_kwh");
      items.push(["report.rec_load_day", `${kwh(load.load_kwh)} kWh`, dayLabel(load.date)]);
      const buy = maxBy("grid_buy_kwh");
      items.push(["report.rec_buy_day", `${kwh(buy.grid_buy_kwh)} kWh · ${money(buy.grid_buy_cost)}`, dayLabel(buy.date)]);
      const best = withData.reduce((acc, row) => ((safeNumber(row.net) ? row.net : -Infinity) > (safeNumber(acc.net) ? acc.net : -Infinity) ? row : acc), withData[0]);
      items.push(["report.rec_best_day", money(best.net), dayLabel(best.date)]);
    }
    if (history.length) {
      const dayPeriod = (state.history && state.history.period) === "day";
      const loadKey = dayPeriod ? "load_power_max_w" : "load_power_w";
      const peakLoad = history.reduce((best, point) => ((safeNumber(point[loadKey]) ? point[loadKey] : 0) > (safeNumber(best[loadKey]) ? best[loadKey] : 0) ? point : best), history[0]);
      if (safeNumber(peakLoad[loadKey])) {
        items.push(["report.rec_peak_load",
          `${number(peakLoad[loadKey], 0)} W`,
          `${timestampLabel(peakLoad.captured_at)} · ${t(dayPeriod ? "report.rec_instant_note" : "report.rec_avg_note")}`]);
      }
      const peakPv = history.reduce((best, point) => ((safeNumber(point.pv_power_w) ? point.pv_power_w : 0) > (safeNumber(best.pv_power_w) ? best.pv_power_w : 0) ? point : best), history[0]);
      if (safeNumber(peakPv.pv_power_w)) {
        items.push(["report.rec_peak_pv",
          `${number(peakPv.pv_power_w, 0)} W`,
          `${timestampLabel(peakPv.captured_at)} · ${t("report.rec_avg_note")}`]);
      }
    }
    items.forEach(([labelKey, value, note]) => {
      const cell = document.createElement("div");
      cell.className = "report-record";
      const label = document.createElement("span");
      label.textContent = t(labelKey);
      const strong = document.createElement("strong");
      strong.textContent = value;
      const small = document.createElement("small");
      small.textContent = note;
      cell.append(label, strong, small);
      grid.append(cell);
    });
  }

  function renderBatteries() {
    const block = $("batteriesBlock");
    if (!block) return;
    const frame = state.current && state.current.battery;
    const modules = frame && frame.modules ? frame.modules : [];
    block.hidden = modules.length === 0;
    if (!modules.length) return;
    const table = $("batteryTable");
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    thead.textContent = "";
    tbody.textContent = "";
    const headRow = document.createElement("tr");
    ["report.b_module", "report.b_soc", "report.b_voltage", "report.b_current",
     "report.b_soh", "report.b_cycles", "report.b_delta", "report.b_temp"].forEach((key) => {
      const th = document.createElement("th");
      th.textContent = t(key);
      headRow.append(th);
    });
    thead.append(headRow);
    modules.forEach((module) => {
      const metrics = module.metrics || {};
      const tr = document.createElement("tr");
      const cells = [
        `MODULE ${String(module.module_index != null ? module.module_index : 0).padStart(2, "0")}`,
        safeNumber(metrics.soc_percent) ? number(metrics.soc_percent, 0) : "--",
        safeNumber(metrics.voltage_v) ? number(metrics.voltage_v, 2) : "--",
        safeNumber(metrics.current_a) ? number(metrics.current_a, 1) : "--",
        safeNumber(metrics.soh_percent) ? number(metrics.soh_percent, 0) : "--",
        safeNumber(metrics.cycles) ? number(metrics.cycles, 0) : "--",
        safeNumber(metrics.cell_delta_v) ? number(metrics.cell_delta_v * 1000, 0) : "--",
        safeNumber(metrics.temp_max_c) ? `${number(metrics.temp_min_c, 0)}…${number(metrics.temp_max_c, 0)}` : "--",
      ];
      cells.forEach((value, index) => {
        const td = document.createElement("td");
        td.textContent = value;
        if (index > 0) td.classList.add("num");
        tr.append(td);
      });
      tbody.append(tr);
    });
  }

  function renderEvents() {
    const block = $("eventsBlock");
    if (!block) return;
    const events = state.events && state.events.events ? state.events.events : [];
    block.hidden = events.length === 0;
    if (!events.length) return;
    const table = $("eventsTable");
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    thead.textContent = "";
    tbody.textContent = "";
    const headRow = document.createElement("tr");
    ["report.ev_at", "report.ev_event", "report.ev_detail"].forEach((key) => {
      const th = document.createElement("th");
      th.textContent = t(key);
      headRow.append(th);
    });
    thead.append(headRow);
    events.slice(0, 12).forEach((event) => {
      const tr = document.createElement("tr");
      const at = document.createElement("td");
      at.textContent = event.at || timestampFromTs(event.ts);
      const name = document.createElement("td");
      name.textContent = event.event || "";
      const detail = document.createElement("td");
      detail.textContent = event.detail || "";
      tr.append(at, name, detail);
      tbody.append(tr);
    });
  }

  function timestampFromTs(ts) {
    return safeNumber(ts) ? new Intl.DateTimeFormat(locale(), { dateStyle: "short", timeStyle: "short" }).format(new Date(ts * 1000)) : "--";
  }

  // ------------------------------------------------------------------ controls

  function bindControls() {
    document.querySelectorAll("[data-lang]").forEach((button) => button.addEventListener("click", () => {
      state.language = button.dataset.lang === "en" ? "en" : "ru";
      try { localStorage.setItem("hiden-control-language", state.language); } catch (error) { /* ignore */ }
      renderAll();
    }));
    document.querySelectorAll("[data-days]").forEach((button) => button.addEventListener("click", () => {
      state.days = Number(button.dataset.days) || 30;
      state.from = null;
      state.to = null;
      $("reportFrom").value = "";
      $("reportTo").value = "";
      document.querySelectorAll("[data-days]").forEach((item) => item.classList.toggle("is-active", item === button));
      window.history.replaceState(null, "", `/report?days=${state.days}`);
      loadData();
    }));
    const from = $("reportFrom");
    const to = $("reportTo");
    const applyCustom = () => {
      if (!from.value || !to.value) return;
      if (from.value > to.value) { [from.value, to.value] = [to.value, from.value]; }
      state.from = from.value;
      state.to = to.value;
      document.querySelectorAll("[data-days]").forEach((item) => item.classList.remove("is-active"));
      window.history.replaceState(null, "", `/report?from=${state.from}&to=${state.to}`);
      loadData();
    };
    if (from) from.addEventListener("change", applyCustom);
    if (to) to.addEventListener("change", applyCustom);
    $("reportPrint").addEventListener("click", () => window.print());
  }

  async function boot() {
    const params = new URLSearchParams(window.location.search);
    const daysParam = Number(params.get("days"));
    if (params.get("from") && params.get("to")) {
      state.from = params.get("from");
      state.to = params.get("to");
      $("reportFrom").value = state.from;
      $("reportTo").value = state.to;
      document.querySelectorAll("[data-days]").forEach((item) => item.classList.remove("is-active"));
    } else if ([7, 30, 90, 365].includes(daysParam)) {
      state.days = daysParam;
      document.querySelectorAll("[data-days]").forEach((item) => {
        item.classList.toggle("is-active", Number(item.dataset.days) === state.days);
      });
    }
    bindControls();
    try {
      await loadData();
    } catch (error) {
      const summary = $("reportSummary");
      if (summary) {
        summary.hidden = false;
        const grid = $("summaryGrid");
        grid.textContent = "";
        const note = document.createElement("p");
        note.className = "report-error";
        note.textContent = String(error.message || "").includes("401")
          ? t("report.auth_required")
          : `${t("report.no_data")} (${error.message})`;
        grid.append(note);
      }
    }
  }

  boot();
})();
