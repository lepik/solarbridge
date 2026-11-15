(() => {
  "use strict";

  const translations = {
    ru: {
      "page.title": "HIDEN",
      "page.description": "Локальный read-only мониторинг HIDEN HS-20-5548 PRO",
      "language.label": "Язык",
      "theme.to_light": "Переключить на светлую тему",
      "theme.to_dark": "Переключить на тёмную тему",
      "common.refresh": "Обновить данные",
      "common.waiting": "ожидание...",
      "common.source_usb": "USB serial",
      "common.error": "Ошибка",
      "common.code": "код",
      "common.none": "нет",
      "common.registers": "регистров",
      "common.state": "состояние",
      "common.not_available": "--",
      "hero.device": "HS-20-5548 PRO",
            "hero.last": "Последние данные",
      "hero.source": "Источник",
     "tab.01": "01 · Сейчас",
     "tab.02": "02 · Батареи",
     "tab.03": "03 · Графики",
     "tab.04": "04 · Система",
     "tab.05": "05 · Детали",
     "tab.06": "06 · Параметры",
     "tab.07": "07 · Диагностика",
     "tab.08": "08 · Финансы",
     "tab.09": "09 · PC Master",
      "bank.kicker": "02 / БАТАРЕИ",
      "bank.title": "Модули батарей",
      "bank.note": "BMS телеметрия · только чтение",
      "bank.online": "онлайн",
      "bank.waiting": "Ожидание первого опроса шины батарей",
      "bank.no_data": "нет данных",
      "bank.normal": "норма",
      "bank.alarm": "авария",
      "bank.protection": "защита",
      "bank.offline_state": "модуль офлайн",
      "bank.charge": "заряд",
      "bank.discharge": "разряд",
      "bank.idle": "покой",
      "bank.cycles": "циклы",
      "bank.cell_delta": "Δ ячеек",
      "bank.soc_title": "SOC модуля",
      "today.pv": "PV сегодня",
      "today.load": "Нагрузка",
      "today.grid": "Сеть",
      "today.batt": "Батарея",
      "today.note": "kWh с начала суток · расчёт из часовых бакетов",
      "today.turnover_title": "Суммарная энергия через батарею за сегодня",
      "bank.expand": "Подробнее",
      "bank.temps": "Температуры",
      "bank.capacity": "Ёмкость",
      "bank.mos_state": "Состояние MOS",
      "bank.balance": "Балансировка",
      "bank.diagnostics": "Диагностика",
      "bank.charge_limit": "Лимит заряда",
      "bank.discharge_limit": "Лимит разряда",
      "bank.flags": "Флаги BMS",
      "bank.protection_limits": "Пороги защиты",
      "bank.cell_faults": "Авария ячеек",
      "bank.flag_charge_enable": "заряд разрешён",
      "bank.flag_discharge_enable": "разряд разрешён",
      "bank.flag_charge_now": "немедленный заряд",
      "bank.flag_full_charge": "запрос полного заряда",
      "bank.lim_cell_high": "банка, верх",
      "bank.lim_cell_low_alarm": "банка, низ (авария)",
      "bank.lim_cell_low_protect": "банка, низ (защита)",
      "bank.lim_mod_high": "модуль, верх",
      "bank.lim_mod_low_alarm": "модуль, низ (авария)",
      "bank.lim_mod_low_protect": "модуль, низ (защита)",
      "bank.lim_chg_temp": "заряд T, верх/низ",
      "bank.lim_dis_temp": "разряд T, верх/низ",
      "alarm.title": "Активные события инвертора — перейти к диагностике",
      "alarm.errors_one": "ошибка",
      "alarm.errors_few": "ошибки",
      "alarm.errors_many": "ошибок",
      "alarm.warnings_one": "предупреждение",
      "alarm.warnings_few": "предупреждения",
      "alarm.warnings_many": "предупреждений",
      "snapshot.note": "Данные обновляются сами · SSE, каждые 15 с",
      "section.now": "01 / СЕЙЧАС",
      "section.flow": "Мощности сейчас",
      "metric.pv.label": "PV мощность",
      "metric.pv.unit": "выработка панелей",
      "metric.load.label": "Нагрузка",
      "metric.load.unit": "домашнее потребление",
      "metric.grid.label": "Grid",
      "metric.grid.unit": "обмен с сетью",
      "metric.battery.label": "Battery",
      "metric.battery.unit": "батарея · напряжение",
      "metric.live": "LIVE",
      "metric.group_power": "Поток мощности",
      "metric.group_voltage": "Напряжение",
      "metric.group_current": "Ток / частота",
      "metric.group_temperature": "Температура",
      "metric.option_load_power": "Нагрузка, W",
      "metric.option_pv_power": "PV генерация, W",
      "metric.option_grid_power": "Поток сети, W",
      "metric.option_battery_power": "Мощность батареи, W",
      "metric.option_load_percent": "Нагрузка, %",
      "metric.option_battery_voltage": "Батарея, V",
      "metric.option_pv_voltage": "PV voltage, V",
      "metric.option_inverter_voltage": "AC output, V",
      "metric.option_grid_voltage": "Grid, V",
      "metric.option_bus_voltage": "DC bus, V",
      "metric.option_pv_current": "PV current, A",
      "metric.option_inverter_current": "AC output current, A",
      "metric.option_grid_current": "Grid current, A",
      "metric.option_load_current": "Load current, A",
      "metric.option_inverter_frequency": "Inverter frequency, Hz",
      "metric.option_grid_frequency": "Grid frequency, Hz",
      "metric.option_ac_temp": "AC radiator, °C",
      "metric.option_transformer_temp": "Transformer, °C",
      "metric.option_dc_temp": "DC radiator, °C",
      "history.kicker": "03 / ГРАФИКИ",
      "history.title": "История показателей",
      "history.range_aria": "Период истории",
      "history.chart_aria": "График исторических показателей",
      "range.24h": "24 ч",
      "range.7d": "7 дней",
      "range.30d": "30 дней",
      "range.1y": "1 год",
      "range.all": "Всё",
      "history.metric": "Показатель",
      "history.resolution": "Разрешение",
      "period.minute": "1 мин",
      "period.30m": "30 мин",
      "period.hour": "Час",
      "period.day": "День",
      "period.week": "Неделя",
      "period.month": "Месяц",
      "period.raw": "Raw samples",
      "history.export": "CSV export",
      "history.report": "Отчёт PDF",
      "history.report_title": "Печатная версия отчёта (Ctrl+P → PDF)",
      "history.empty": "История появится после первых сохранённых samples",
      "history.no_data": "Нет сохранённых данных",
      "history.points_one": "точка",
      "history.points_many": "точек",
      "history.shown_limit": "показан лимит raw points",
      "status.kicker": "04 / СОСТОЯНИЕ",
      "status.title": "Система",
      "status.model": "Модель",
      "status.nominal": "Номинал",
      "status.serial": "Serial number",
      "status.firmware": "Firmware",
      "status.protocol": "Протокол",
      "status.charger_model": "Зарядник",
      "status.charger_state": "Стадия зарядника",
      "status.poll": "Последний poll",
      "state.0": "включение",
      "state.1": "самотест",
      "state.2": "автономный",
      "state.3": "сетевой",
      "state.4": "байпас",
      "state.5": "останов",
      "state.6": "заряд от сети",
      "chg.work.0": "Инициализация",
      "chg.work.1": "Самотест",
      "chg.work.2": "Работа",
      "chg.work.3": "Останов",
      "chg.mppt.0": "Останов",
      "chg.mppt.1": "MPPT",
      "chg.mppt.2": "Ограничение тока",
      "chg.charging.0": "Останов",
      "chg.charging.1": "Поглощение",
      "chg.charging.2": "Буферный заряд",
      "chg.charging.3": "Уравнивание",
      "relay.aria": "Состояние реле",
      "relay.inverter": "ИНВ",
      "relay.inverter_full": "Реле инвертора",
      "relay.grid": "СЕТЬ",
      "relay.grid_full": "Реле сети",
      "relay.load": "НАГР",
      "relay.load_full": "Реле нагрузки",
      "relay.n_line": "N",
      "relay.n_line_full": "Реле линии N",
      "relay.dc": "DC",
      "relay.dc_full": "Реле DC-шины",
      "relay.earth": "PE",
      "relay.earth_full": "Реле заземления",
      "relay.battery": "БАТ",
      "relay.battery_full": "Реле батареи",
      "relay.pv": "PV",
      "relay.pv_full": "Реле PV-входа",
      "relay.on": "замкнуто",
      "relay.off": "разомкнуто",
      "flow.pv": "PV → инвертор",
      "flow.load": "инвертор → нагрузка",
      "flow.batt.charge": "заряд",
      "flow.batt.discharge": "разряд",
      "flow.batt.connected": "соединена",
      "flow.batt.off": "отключена",
      "flow.grid.buy": "покупка",
      "flow.grid.sell": "продажа",
      "flow.grid.connected": "соединена",
      "flow.grid.off": "отключена",
      "system.waiting": "Ожидание",
      "system.connecting": "Подключение к инвертору",
      "system.connected": "Подключено",
      "system.ok": "Всё в норме",
      "system.channel_ok": "Шина RS485 отвечает",
      "system.partial": "Частичные данные",
      "system.degraded": "Деградированный режим",
      "system.partial_detail": "Отдельные блоки не отвечают",
      "system.offline": "Нет связи",
      "system.offline_detail": "Ожидание ответа от порта",
      "system.starting": "Запуск сервиса",
      "system.starting_detail": "Первый poll ещё не завершён",
      "system.stale": "Данные устарели",
      "system.stale_detail": "Последний sample слишком старый",
      "health.active": "Канал read-only: команд записи в инвертор не существует",
      "health.stale_age": "Последний sample",
      "telemetry.kicker": "05 / ДЕТАЛИ",
      "telemetry.title": "Детали сигнала",
      "telemetry.ac": "AC output",
      "telemetry.dc": "DC / bus",
      "telemetry.temperatures": "Температуры",
      "telemetry.accumulated": "Накопленные показатели",
      "telemetry.current": "Ток",
      "telemetry.frequency": "Частота",
      "telemetry.reactive": "Reactive",
      "telemetry.pf": "cos φ",
      "telemetry.battery_current": "Battery current",
      "telemetry.pv_voltage": "PV voltage",
      "telemetry.pv_current": "PV current",
      "telemetry.ac_radiator": "AC radiator",
      "telemetry.dc_radiator": "DC radiator",
      "telemetry.transformer": "Transformer",
      "telemetry.charger_radiator": "Charger radiator",
      "telemetry.charged": "Charged",
      "telemetry.discharged": "Discharged",
      "telemetry.uptime": "Charger uptime",
      "uptime.day_short": "д",
      "battery.track_title": "Положение напряжения в рабочем диапазоне, не оценка SOC",
      "config.kicker": "06 / ПАРАМЕТРЫ",
      "config.title": "Настройки инвертора",
      "config.readonly": "READ ONLY",
      "config.charger": "Зарядный контур",
      "config.inverter": "Инверторный контур",
      "config.charger_work": "Charger",
      "config.absorb_voltage": "Absorb voltage",
      "config.float_voltage": "Float voltage",
      "config.battery_low": "Battery low",
      "config.battery_high": "Battery high",
      "config.max_current": "Max current",
      "config.capacity": "Battery capacity",
      "config.battery_type": "Тип батареи",
      "config.equalization": "Equalization",
      "config.offgrid": "Off-grid",
      "config.output": "Output",
      "config.frequency": "Frequency",
      "config.search_mode": "Search mode",
      "config.energy_mode": "Energy mode",
      "config.grid_standard": "Стандарт сети",
      "config.max_discharge": "Max discharge",
      "config.grid_charge": "Grid charge",
      "config.source_priority": "Source priority",
      "config.system_flags": "Системные флаги",
      "cfg.sysflag.overload_restart": "рестарт при перегрузке запрещён",
      "cfg.sysflag.overtemp_restart": "рестарт при перегреве запрещён",
      "cfg.sysflag.overload_bypass": "bypass при перегрузке запрещён",
      "cfg.sysflag.auto_page": "автолистание LCD запрещено",
      "cfg.sysflag.grid_buzzer": "зумер от сети вкл.",
      "cfg.sysflag.buzzer_off": "зумер выключен",
      "cfg.sysflag.lcd_light": "подсветка LCD вкл.",
      "cfg.energy.1": "SBU · солнце → батарея → сеть",
      "cfg.energy.2": "SUB · солнце → сеть → батарея",
      "cfg.energy.3": "UTI · приоритет сети",
      "cfg.energy.4": "SOL · только солнце",
      "cfg.grid_standard.0": "VDE4105",
      "cfg.grid_standard.1": "UPS",
      "cfg.grid_standard.2": "домашний",
      "cfg.grid_standard.3": "генератор",
      "cfg.priority.0": "сначала солнце",
      "cfg.priority.2": "солнце и сеть",
      "cfg.priority.3": "только солнце",
      "cfg.battery_type.0": "не выбрана",
      "cfg.battery_type.1": "пользовательская",
      "cfg.battery_type.2": "литий",
      "cfg.battery_type.3": "герметизированная (SLA)",
      "cfg.battery_type.4": "AGM",
      "cfg.battery_type.5": "GEL",
      "cfg.battery_type.6": "заливная",
      "diagnostics.kicker": "07 / СОБЫТИЯ",
      "diagnostics.title": "Диагностика",
      "diagnostics.nominal": "NOMINAL",
      "diagnostics.alarm": "АВАРИЯ",
      "diagnostics.warning": "ПРЕДУПРЕЖДЕНИЕ",
      "diagnostics.active": "Активные события",
      "diagnostics.channel": "Serial channel",
      "diagnostics.latency": "Response latency",
      "diagnostics.charger_error": "Charger error code",
      "diagnostics.charger_warning": "Charger warning code",
      "diagnostics.frames": "Frames",
      "diagnostics.section_errors": "Section errors",
      "diagnostics.raw": "Raw register frames",
      "diagnostics.expand": "развернуть",
      "fault.unknown": "бит без описания",
      "fault.inv.e1.0": "Вентилятор заблокирован при выключенном инверторе",
      "fault.inv.e1.1": "Перегрев трансформатора инвертора",
      "fault.inv.e1.2": "Напряжение батареи слишком высокое",
      "fault.inv.e1.3": "Напряжение батареи слишком низкое",
      "fault.inv.e1.4": "Короткое замыкание на выходе",
      "fault.inv.e1.5": "Выходное напряжение инвертора завышено",
      "fault.inv.e1.6": "Тайм-аут перегрузки",
      "fault.inv.e1.7": "Напряжение шины DC слишком высокое",
      "fault.inv.e1.8": "Сбой мягкого старта шины DC",
      "fault.inv.e1.9": "Неисправность главного реле",
      "fault.inv.e1.10": "Ошибка датчика выходного напряжения",
      "fault.inv.e1.11": "Ошибка датчика напряжения сети",
      "fault.inv.e1.12": "Ошибка датчика выходного тока",
      "fault.inv.e1.13": "Ошибка датчика тока сети",
      "fault.inv.e1.14": "Ошибка датчика тока нагрузки",
      "fault.inv.e1.15": "Сверхток сети инвертора",
      "fault.inv.e2.0": "Перегрев радиатора инвертора",
      "fault.inv.e2.1": "Ошибка класса напряжения батареи зарядника",
      "fault.inv.e2.2": "Ошибка датчика тока MPPT-зарядника",
      "fault.inv.e2.3": "Ток зарядника неуправляем",
      "fault.inv.e2.4": "Напряжение сети занижено",
      "fault.inv.e2.5": "Напряжение сети завышено",
      "fault.inv.e2.6": "Частота сети занижена",
      "fault.inv.e2.7": "Частота сети завышена",
      "fault.inv.e2.8": "Срабатывание защиты по току инвертора",
      "fault.inv.e2.9": "Напряжение шины DC слишком низкое",
      "fault.inv.e2.10": "Сбой мягкого старта инвертора",
      "fault.inv.e2.11": "Постоянное напряжение на выходе AC",
      "fault.inv.e2.12": "Обрыв цепи батареи",
      "fault.inv.e2.13": "Ошибка датчика тока управления",
      "fault.inv.e2.14": "Выходное напряжение занижено",
      "fault.inv.w1.0": "Вентилятор заблокирован при работающем инверторе",
      "fault.inv.w1.1": "Вентилятор 2 заблокирован при работающем инверторе",
      "fault.inv.w1.2": "Батарея перезаряжена",
      "fault.inv.w1.3": "Низкий заряд батареи",
      "fault.inv.w1.4": "Перегрузка",
      "fault.inv.w1.5": "Снижение выходной мощности (derating)",
      "fault.inv.w1.6": "MPPT остановлен: батарея разряжена",
      "fault.inv.w1.7": "MPPT остановлен: высокое напряжение PV",
      "fault.inv.w1.8": "MPPT остановлен: перегрузка",
      "fault.inv.w1.9": "Перегрев MPPT-зарядника",
      "fault.inv.w1.10": "Ошибка связи с PV-зарядником",
      "fault.chg.e.0": "Аппаратная защита зарядника",
      "fault.chg.e.1": "Сверхток зарядника",
      "fault.chg.e.2": "Ошибка датчика тока зарядника",
      "fault.chg.e.3": "Перегрев зарядника",
      "fault.chg.e.4": "Напряжение PV слишком высокое",
      "fault.chg.e.5": "Напряжение PV слишком низкое",
      "fault.chg.e.6": "Напряжение батареи слишком высокое",
      "fault.chg.e.7": "Напряжение батареи слишком низкое",
      "fault.chg.e.8": "Ток зарядника неуправляем",
      "fault.chg.e.9": "Ошибка параметров зарядника",
      "fault.chg.w.0": "Ошибка вентилятора зарядника",
      "finance.kicker": "08 / ФИНАНСЫ",
      "finance.title": "Энергия и деньги",
      "finance.note": "Оценка по вашим тарифам · правка тарифа пересчитывает историю мгновенно",
      "finance.yesterday": "Вчера",
      "finance.today": "Сегодня",
      "finance.today_live": "Сегодня · LIVE",
      "finance.net_label": "экономия PV − покупки сети",
      "finance.empty": "Строки появятся после первых замеров. Задайте тариф, чтобы видеть деньги.",
      "finance.pv": "PV генерация",
      "finance.pv_savings": "Экономия PV",
      "finance.load": "Нагрузка",
      "finance.grid_buy": "Куплено из сети",
      "finance.grid_cost": "Расходы",
      "finance.charge_grid_incl": "в т.ч. заряд из сети",
      "finance.grid_sell": "PV в сеть дома",
      "finance.charge": "Заряд батареи",
      "finance.charge_break": "из PV · из сети",
      "finance.discharge": "Разряд батареи",
      "finance.tariff": "Тариф",
      "finance.coverage": "Данных за",
      "finance.hours_short": "ч",
      "finance.no_tariff": "тариф не задан",
      "finance.load_total": "Итого в нагрузку",
      "finance.load_total_cost": "Стоимость по тарифу",
      "finance.load_total_hint": "Вся нагрузка, оценённая по тарифу. Фактические затраты — строка «Расходы».",
      "tariff.kicker": "ТАРИФ",
      "tariff.title": "Цена кВт·ч",
      "tariff.local_tag": "LOCAL",
      "tariff.price": "Цена, ₽/кВт·ч",
      "tariff.valid_from": "Действует с",
      "tariff.note": "Заметка",
      "tariff.note_placeholder": "например: летний",
      "tariff.save": "Сохранить тариф",
      "tariff.saving": "Сохранение…",
      "tariff.saved": "Тариф сохранён · история пересчитана",
      "tariff.deleted": "Тариф удалён",
      "tariff.active": "активный",
      "tariff.delete_confirm": "Удалить тариф с этой даты?",
      "tariff.empty": "Тарифов пока нет — добавьте первый выше.",
      "tariff.error_prefix": "Ошибка: ",
      "tariff.expand": "Подробнее: редактор и история тарифов",
      "tariff.current_none": "тариф не задан",
      "tariff.current_since": "действует с {date}",
      "disk.banner": "Мало места на диске: {free}% свободно (порог {min}%). Запись в БД приостановлена — кадры уходят только приёмникам. Освободите место или удалите старые данные через install.py.",
      "auth.title": "Требуется вход",
      "auth.login": "Логин",
      "auth.password": "Пароль",
      "auth.submit": "Войти",
      "auth.error": "Неверный логин или пароль",
      "auth.in_progress": "Вход...",
      "system.version_mismatch": "Расхождение версий: мастер {master}, приёмник {local}. Обновите SolarBridge на приёмнике.",
      "machine.kicker": "09 / PC MASTER POLL",
      "machine.title": "PC Master",
      "machine.note": "Нагрузка, температура и питание хоста мастера · обновление с heartbeat",
      "machine.cpu_temp": "CPU",
      "machine.load": "Load 1/5/15",
      "machine.ram": "RAM",
      "machine.disk": "Диск",
      "machine.master_id": "master_id",
      "machine.version": "Версия мастера",
      "machine.uptime": "Uptime сервиса",
      "machine.host_uptime": "Uptime машины",
      "machine.throttled": "Питание (throttled)",
      "machine.heartbeat": "Heartbeat",
      "machine.throttled_ok": "норма",
      "machine.throttled_bad": "требует внимания",
      "machine.unknown": "нет данных",
      "machine.seconds_ago": "{n} с назад",
      "footer": "Локальный сервис · Modbus RTU только чтение · время в UTC",
    },
    en: {
      "page.title": "HIDEN",
      "page.description": "Local read-only monitoring for the HIDEN HS-20-5548 PRO",
      "language.label": "Language",
      "theme.to_light": "Switch to light theme",
      "theme.to_dark": "Switch to dark theme",
      "common.refresh": "Refresh data",
      "common.waiting": "waiting...",
      "common.source_usb": "USB serial",
      "common.error": "Error",
      "common.code": "code",
      "common.none": "none",
      "common.registers": "registers",
      "common.state": "state",
      "common.not_available": "--",
      "hero.device": "HS-20-5548 PRO",
            "hero.last": "Last data",
      "hero.source": "Source",
     "tab.01": "01 · Live",
     "tab.02": "02 · Batteries",
     "tab.03": "03 · Charts",
     "tab.04": "04 · System",
     "tab.05": "05 · Details",
     "tab.06": "06 · Settings",
     "tab.07": "07 · Events",
     "tab.08": "08 · Money",
     "tab.09": "09 · PC Master",
      "bank.kicker": "02 / BATTERY BANK",
      "bank.title": "Battery modules",
      "bank.note": "BMS telemetry · read-only",
      "bank.online": "online",
      "bank.waiting": "Waiting for the first battery bus poll",
      "bank.no_data": "no data",
      "bank.normal": "normal",
      "bank.alarm": "alarm",
      "bank.protection": "protection",
      "bank.offline_state": "module offline",
      "bank.charge": "charging",
      "bank.discharge": "discharging",
      "bank.idle": "idle",
      "bank.cycles": "cycles",
      "bank.cell_delta": "cell Δ",
      "bank.soc_title": "Module SOC",
      "today.pv": "PV today",
      "today.load": "Load",
      "today.grid": "Grid",
      "today.batt": "Battery",
      "today.note": "kWh since local midnight · computed from hourly buckets",
      "today.turnover_title": "Total energy through the battery today",
      "bank.expand": "Details",
      "bank.temps": "Temperatures",
      "bank.capacity": "Capacity",
      "bank.mos_state": "MOS state",
      "bank.balance": "Balancing",
      "bank.diagnostics": "Diagnostics",
      "bank.charge_limit": "Charge limit",
      "bank.discharge_limit": "Discharge limit",
      "bank.flags": "BMS flags",
      "bank.protection_limits": "Protection thresholds",
      "bank.cell_faults": "Cell faults",
      "bank.flag_charge_enable": "charge enabled",
      "bank.flag_discharge_enable": "discharge enabled",
      "bank.flag_charge_now": "charge immediately",
      "bank.flag_full_charge": "full charge requested",
      "bank.lim_cell_high": "cell, high",
      "bank.lim_cell_low_alarm": "cell, low (alarm)",
      "bank.lim_cell_low_protect": "cell, low (protect)",
      "bank.lim_mod_high": "module, high",
      "bank.lim_mod_low_alarm": "module, low (alarm)",
      "bank.lim_mod_low_protect": "module, low (protect)",
      "bank.lim_chg_temp": "charge T, hi/lo",
      "bank.lim_dis_temp": "discharge T, hi/lo",
      "alarm.title": "Active inverter events — jump to diagnostics",
      "alarm.errors_one": "error",
      "alarm.errors_few": "errors",
      "alarm.errors_many": "errors",
      "alarm.warnings_one": "warning",
      "alarm.warnings_few": "warnings",
      "alarm.warnings_many": "warnings",
      "snapshot.note": "Live updates via SSE every 15 s",
      "section.now": "01 / LIVE",
      "section.flow": "Live power",
      "metric.pv.label": "PV power",
      "metric.pv.unit": "panel output",
      "metric.load.label": "Load",
      "metric.load.unit": "house draw",
      "metric.grid.label": "Grid",
      "metric.grid.unit": "grid exchange",
      "metric.battery.label": "Battery",
      "metric.battery.unit": "battery · bus voltage",
      "metric.live": "LIVE",
      "metric.group_power": "Power flow",
      "metric.group_voltage": "Voltage",
      "metric.group_current": "Current / frequency",
      "metric.group_temperature": "Temperature",
      "metric.option_load_power": "Load, W",
      "metric.option_pv_power": "PV generation, W",
      "metric.option_grid_power": "Grid flow, W",
      "metric.option_battery_power": "Battery power, W",
      "metric.option_load_percent": "Load, %",
      "metric.option_battery_voltage": "Battery, V",
      "metric.option_pv_voltage": "PV voltage, V",
      "metric.option_inverter_voltage": "AC output, V",
      "metric.option_grid_voltage": "Grid, V",
      "metric.option_bus_voltage": "DC bus, V",
      "metric.option_pv_current": "PV current, A",
      "metric.option_inverter_current": "AC output current, A",
      "metric.option_grid_current": "Grid current, A",
      "metric.option_load_current": "Load current, A",
      "metric.option_inverter_frequency": "Inverter frequency, Hz",
      "metric.option_grid_frequency": "Grid frequency, Hz",
      "metric.option_ac_temp": "AC radiator, °C",
      "metric.option_transformer_temp": "Transformer, °C",
      "metric.option_dc_temp": "DC radiator, °C",
      "history.kicker": "03 / CHARTS",
      "history.title": "Charts",
      "history.range_aria": "History range",
      "history.chart_aria": "Historical metrics chart",
      "range.24h": "24 hrs",
      "range.7d": "7 days",
      "range.30d": "30 days",
      "range.1y": "1 year",
      "range.all": "All",
      "history.metric": "Metric",
      "history.resolution": "Resolution",
      "period.minute": "1 min",
      "period.30m": "30 min",
      "period.hour": "Hour",
      "period.day": "Day",
      "period.week": "Week",
      "period.month": "Month",
      "period.raw": "Raw samples",
      "history.export": "CSV export",
      "history.report": "PDF report",
      "history.report_title": "Printable report view (Ctrl+P → PDF)",
      "history.empty": "History will appear after the first saved samples",
      "history.no_data": "No saved data",
      "history.points_one": "point",
      "history.points_many": "points",
      "history.shown_limit": "raw point limit shown",
      "status.kicker": "04 / STATUS",
      "status.title": "System",
      "status.model": "Model",
      "status.nominal": "Rated",
      "status.serial": "Serial number",
      "status.firmware": "Firmware",
      "status.protocol": "Protocol",
      "status.charger_model": "Charger",
      "status.charger_state": "Charger stage",
      "status.poll": "Last poll",
      "state.0": "power on",
      "state.1": "self-test",
      "state.2": "off-grid",
      "state.3": "grid-tie",
      "state.4": "bypass",
      "state.5": "stop",
      "state.6": "grid charging",
      "chg.work.0": "Initialization",
      "chg.work.1": "Self-test",
      "chg.work.2": "Work",
      "chg.work.3": "Stop",
      "chg.mppt.0": "Stop",
      "chg.mppt.1": "MPPT",
      "chg.mppt.2": "Current limiting",
      "chg.charging.0": "Stop",
      "chg.charging.1": "Absorb",
      "chg.charging.2": "Float",
      "chg.charging.3": "Equalization",
      "relay.aria": "Relay states",
      "relay.inverter": "INV",
      "relay.inverter_full": "Inverter relay",
      "relay.grid": "GRID",
      "relay.grid_full": "Grid relay",
      "relay.load": "LOAD",
      "relay.load_full": "Load relay",
      "relay.n_line": "N",
      "relay.n_line_full": "N-line relay",
      "relay.dc": "DC",
      "relay.dc_full": "DC bus relay",
      "relay.earth": "PE",
      "relay.earth_full": "Earth relay",
      "relay.battery": "BAT",
      "relay.battery_full": "Battery relay",
      "relay.pv": "PV",
      "relay.pv_full": "PV input relay",
      "relay.on": "closed",
      "relay.off": "open",
      "flow.pv": "PV → unit",
      "flow.load": "unit → load",
      "flow.batt.charge": "charging",
      "flow.batt.discharge": "discharging",
      "flow.batt.connected": "connected",
      "flow.batt.off": "disconnected",
      "flow.grid.buy": "buying",
      "flow.grid.sell": "selling",
      "flow.grid.connected": "connected",
      "flow.grid.off": "disconnected",
      "system.waiting": "Waiting",
      "system.connecting": "Connecting to inverter",
      "system.connected": "Connected",
      "system.ok": "All nominal",
      "system.channel_ok": "RS485 bus responds",
      "system.partial": "Partial data",
      "system.degraded": "Degraded mode",
      "system.partial_detail": "Some sections are not responding",
      "system.offline": "No connection",
      "system.offline_detail": "Waiting for a port response",
      "system.starting": "Starting service",
      "system.starting_detail": "First poll is not complete",
      "system.stale": "Data is stale",
      "system.stale_detail": "The last sample is too old",
      "health.active": "Read-only bus — no write commands exist",
      "health.stale_age": "Last sample",
      "telemetry.kicker": "05 / DETAILS",
      "telemetry.title": "Signal details",
      "telemetry.ac": "AC output",
      "telemetry.dc": "DC / bus",
      "telemetry.temperatures": "Temperatures",
      "telemetry.accumulated": "Accumulated",
      "telemetry.current": "Current",
      "telemetry.frequency": "Frequency",
      "telemetry.reactive": "Reactive",
      "telemetry.pf": "cos φ",
      "telemetry.battery_current": "Battery current",
      "telemetry.pv_voltage": "PV voltage",
      "telemetry.pv_current": "PV current",
      "telemetry.ac_radiator": "AC radiator",
      "telemetry.dc_radiator": "DC radiator",
      "telemetry.transformer": "Transformer",
      "telemetry.charger_radiator": "Charger radiator",
      "telemetry.charged": "Charged",
      "telemetry.discharged": "Discharged",
      "telemetry.uptime": "Charger uptime",
      "uptime.day_short": "d",
      "battery.track_title": "Voltage position within the working range, not an SOC estimate",
      "config.kicker": "06 / SETTINGS",
      "config.title": "Inverter settings",
      "config.readonly": "READ ONLY",
      "config.charger": "Charger circuit",
      "config.inverter": "Inverter circuit",
      "config.charger_work": "Charger",
      "config.absorb_voltage": "Absorb voltage",
      "config.float_voltage": "Float voltage",
      "config.battery_low": "Battery low",
      "config.battery_high": "Battery high",
      "config.max_current": "Max current",
      "config.capacity": "Battery capacity",
      "config.battery_type": "Battery type",
      "config.equalization": "Equalization",
      "config.offgrid": "Off-grid",
      "config.output": "Output",
      "config.frequency": "Frequency",
      "config.search_mode": "Search mode",
      "config.energy_mode": "Energy mode",
      "config.grid_standard": "Grid standard",
      "config.max_discharge": "Max discharge",
      "config.grid_charge": "Grid charge",
      "config.source_priority": "Source priority",
      "config.system_flags": "System flags",
      "cfg.sysflag.overload_restart": "overload restart forbid",
      "cfg.sysflag.overtemp_restart": "overtemp restart forbid",
      "cfg.sysflag.overload_bypass": "overload bypass forbid",
      "cfg.sysflag.auto_page": "LCD auto page forbid",
      "cfg.sysflag.grid_buzzer": "grid buzzer on",
      "cfg.sysflag.buzzer_off": "buzzer off",
      "cfg.sysflag.lcd_light": "LCD backlight on",
      "cfg.energy.1": "SBU · solar → battery → grid",
      "cfg.energy.2": "SUB · solar → grid → battery",
      "cfg.energy.3": "UTI · grid priority",
      "cfg.energy.4": "SOL · solar only",
      "cfg.grid_standard.0": "VDE4105",
      "cfg.grid_standard.1": "UPS",
      "cfg.grid_standard.2": "home",
      "cfg.grid_standard.3": "generator",
      "cfg.priority.0": "solar first",
      "cfg.priority.2": "solar + utility",
      "cfg.priority.3": "solar only",
      "cfg.battery_type.0": "not selected",
      "cfg.battery_type.1": "user defined",
      "cfg.battery_type.2": "lithium",
      "cfg.battery_type.3": "sealed lead (SLA)",
      "cfg.battery_type.4": "AGM",
      "cfg.battery_type.5": "GEL",
      "cfg.battery_type.6": "flooded",
      "diagnostics.kicker": "07 / EVENTS",
      "diagnostics.title": "Diagnostics",
      "diagnostics.nominal": "NOMINAL",
      "diagnostics.alarm": "ALARM",
      "diagnostics.warning": "WARNING",
      "diagnostics.active": "Active events",
      "diagnostics.channel": "Serial channel",
      "diagnostics.latency": "Response latency",
      "diagnostics.charger_error": "Charger error code",
      "diagnostics.charger_warning": "Charger warning code",
      "diagnostics.frames": "Frames",
      "diagnostics.section_errors": "Section errors",
      "diagnostics.raw": "Raw register frames",
      "diagnostics.expand": "expand",
      "fault.unknown": "undocumented bit",
      "fault.inv.e1.0": "Fan is locked when inverter is off",
      "fault.inv.e1.1": "Inverter transformer over temperature",
      "fault.inv.e1.2": "Battery voltage is too high",
      "fault.inv.e1.3": "Battery voltage is too low",
      "fault.inv.e1.4": "Output short circuited",
      "fault.inv.e1.5": "Inverter output voltage is high",
      "fault.inv.e1.6": "Overload time out",
      "fault.inv.e1.7": "Inverter bus voltage is too high",
      "fault.inv.e1.8": "Bus soft start failed",
      "fault.inv.e1.9": "Main relay failed",
      "fault.inv.e1.10": "Inverter output voltage sensor error",
      "fault.inv.e1.11": "Inverter grid voltage sensor error",
      "fault.inv.e1.12": "Inverter output current sensor error",
      "fault.inv.e1.13": "Inverter grid current sensor error",
      "fault.inv.e1.14": "Inverter load current sensor error",
      "fault.inv.e1.15": "Inverter grid over current error",
      "fault.inv.e2.0": "Inverter radiator over temperature",
      "fault.inv.e2.1": "Solar charger battery voltage class error",
      "fault.inv.e2.2": "Solar charger current sensor error",
      "fault.inv.e2.3": "Solar charger current is uncontrollable",
      "fault.inv.e2.4": "Inverter grid voltage is low",
      "fault.inv.e2.5": "Inverter grid voltage is high",
      "fault.inv.e2.6": "Inverter grid under frequency",
      "fault.inv.e2.7": "Inverter grid over frequency",
      "fault.inv.e2.8": "Inverter over current protection error",
      "fault.inv.e2.9": "Inverter bus voltage is too low",
      "fault.inv.e2.10": "Inverter soft start failed",
      "fault.inv.e2.11": "Over DC voltage in AC output",
      "fault.inv.e2.12": "Battery connection is open",
      "fault.inv.e2.13": "Inverter control current sensor error",
      "fault.inv.e2.14": "Inverter output voltage is too low",
      "fault.inv.w1.0": "Fan is locked when inverter is on",
      "fault.inv.w1.1": "Fan2 is locked when inverter is on",
      "fault.inv.w1.2": "Battery is over-charged",
      "fault.inv.w1.3": "Low battery",
      "fault.inv.w1.4": "Overload",
      "fault.inv.w1.5": "Output power derating",
      "fault.inv.w1.6": "Solar charger stops due to low battery",
      "fault.inv.w1.7": "Solar charger stops due to high PV voltage",
      "fault.inv.w1.8": "Solar charger stops due to over load",
      "fault.inv.w1.9": "Solar charger over temperature",
      "fault.inv.w1.10": "PV charger communication error",
      "fault.chg.e.0": "Charger hardware protection",
      "fault.chg.e.1": "Charger over current",
      "fault.chg.e.2": "Charger current sensor error",
      "fault.chg.e.3": "Charger over temperature",
      "fault.chg.e.4": "PV voltage is too high",
      "fault.chg.e.5": "PV voltage is too low",
      "fault.chg.e.6": "Battery voltage is too high",
      "fault.chg.e.7": "Battery voltage is too low",
      "fault.chg.e.8": "Current is uncontrollable",
      "fault.chg.e.9": "Charger parameter error",
      "fault.chg.w.0": "Charger fan error",
      "finance.kicker": "08 / FINANCES",
      "finance.title": "Energy and money",
      "finance.note": "Estimated with your tariffs · editing a tariff instantly reprices history",
      "finance.yesterday": "Yesterday",
      "finance.today": "Today",
      "finance.today_live": "Today · LIVE",
      "finance.net_label": "PV savings − grid purchases",
      "finance.empty": "Rows appear after the first measurements. Set a tariff to see money.",
      "finance.pv": "PV generation",
      "finance.pv_savings": "PV savings",
      "finance.load": "Load",
      "finance.grid_buy": "Bought from grid",
      "finance.grid_cost": "Costs",
      "finance.charge_grid_incl": "incl. grid charging",
      "finance.grid_sell": "PV into house grid",
      "finance.charge": "Battery charge",
      "finance.charge_break": "from PV · from grid",
      "finance.discharge": "Battery discharge",
      "finance.tariff": "Tariff",
      "finance.coverage": "Data for",
      "finance.hours_short": "h",
      "finance.no_tariff": "no tariff set",
      "finance.load_total": "Total to load",
      "finance.load_total_cost": "Cost at tariff",
      "finance.load_total_hint": "The whole load valued at the tariff; actual spending is the 'Costs' row.",
      "tariff.kicker": "TARIFF",
      "tariff.title": "Price per kWh",
      "tariff.local_tag": "LOCAL",
      "tariff.price": "Price, ₽/kWh",
      "tariff.valid_from": "Effective from",
      "tariff.note": "Note",
      "tariff.note_placeholder": "e.g. summer",
      "tariff.save": "Save tariff",
      "tariff.saving": "Saving…",
      "tariff.saved": "Tariff saved · history repriced",
      "tariff.deleted": "Tariff deleted",
      "tariff.active": "active",
      "tariff.delete_confirm": "Delete the tariff from this date?",
      "tariff.empty": "No tariffs yet — add the first one above.",
      "tariff.error_prefix": "Error: ",
      "tariff.expand": "Details: editor and tariff history",
      "tariff.current_none": "no tariff set",
      "tariff.current_since": "effective from {date}",
      "disk.banner": "Low disk space: {free}% free (threshold {min}%). Database writes are paused — frames go to receivers only. Free some space or delete old data via install.py.",
      "auth.title": "Sign in required",
      "auth.login": "Login",
      "auth.password": "Password",
      "auth.submit": "Sign in",
      "auth.error": "Invalid login or password",
      "auth.in_progress": "Signing in...",
      "system.version_mismatch": "Version mismatch: master {master}, receiver {local}. Update SolarBridge on the receiver.",
      "machine.kicker": "09 / PC MASTER POLL",
      "machine.title": "PC Master",
      "machine.note": "Master host load, temperature and power · updated with the heartbeat",
      "machine.cpu_temp": "CPU",
      "machine.load": "Load 1/5/15",
      "machine.ram": "RAM",
      "machine.disk": "Disk",
      "machine.master_id": "master_id",
      "machine.version": "Master version",
      "machine.uptime": "Service uptime",
      "machine.host_uptime": "Machine uptime",
      "machine.throttled": "Power (throttled)",
      "machine.heartbeat": "Heartbeat",
      "machine.throttled_ok": "ok",
      "machine.throttled_bad": "attention required",
      "machine.unknown": "no data",
      "machine.seconds_ago": "{n} s ago",
      "footer": "Local service · Modbus RTU (read-only) · UTC timestamps",
    },
  };

  const state = {
    range: "24h",
    period: "30m",
    metric: "load_power_w",
    language: readLanguage(),
    theme: readTheme(),
    current: null,
    health: null,
    history: null,
    battery: null,
    finance: null,
    tariffs: null,
    historyRequest: 0,
    alarms: { errors: [], warnings: [] },
    todayTimer: 0,
    financeTimer: 0,
    bankExpanded: {},
    host: null,
  };

  const metricMeta = {
    load_power_w: { labelKey: "metric.load.label", unit: "W", color: "--series-load", decimals: 0 },
    pv_power_w: { labelKey: "metric.pv.label", unit: "W", color: "--series-pv", decimals: 0 },
    grid_power_w: { labelKey: "metric.grid.label", unit: "W", color: "--series-grid", decimals: 0 },
    battery_power_w: { labelKey: "metric.battery.label", unit: "W", color: "--series-batt", decimals: 0 },
    pv_voltage_v: { labelKey: "telemetry.pv_voltage", unit: "V", color: "--series-pv", decimals: 1 },
    battery_voltage_v: { labelKey: "metric.battery.label", unit: "V", color: "--series-batt", decimals: 2 },
    inverter_voltage_v: { labelKey: "telemetry.ac", unit: "V", color: "--series-grid", decimals: 1 },
    grid_voltage_v: { labelKey: "metric.grid.label", unit: "V", color: "--series-grid", decimals: 1 },
    bus_voltage_v: { labelKey: "telemetry.dc", unit: "V", color: "--series-grid", decimals: 1 },
    pv_current_a: { labelKey: "telemetry.pv_current", unit: "A", color: "--series-pv", decimals: 1 },
    inverter_current_a: { labelKey: "telemetry.ac", unit: "A", color: "--series-grid", decimals: 1 },
    grid_current_a: { labelKey: "metric.grid.label", unit: "A", color: "--series-grid", decimals: 1 },
    load_current_a: { labelKey: "metric.load.label", unit: "A", color: "--series-load", decimals: 1 },
    inverter_frequency_hz: { labelKey: "telemetry.frequency", unit: "Hz", color: "--series-grid", decimals: 2 },
    grid_frequency_hz: { labelKey: "telemetry.frequency", unit: "Hz", color: "--series-grid", decimals: 2 },
    load_percent: { labelKey: "metric.load.label", unit: "%", color: "--series-load", decimals: 0 },
    ac_radiator_temperature_c: { labelKey: "telemetry.ac_radiator", unit: "°C", color: "--series-load", decimals: 0 },
    transformer_temperature_c: { labelKey: "telemetry.transformer", unit: "°C", color: "--series-load", decimals: 0 },
    dc_radiator_temperature_c: { labelKey: "telemetry.dc_radiator", unit: "°C", color: "--series-load", decimals: 0 },
  };

  const $ = (id) => document.getElementById(id);
  const setText = (id, value) => { const node = $(id); if (node) node.textContent = value; };
  const safeNumber = (value) => typeof value === "number" && Number.isFinite(value);
  const normalizeLang = (value) => (value === "en" ? "en" : "ru");

  function readLanguage() {
    try {
      return localStorage.getItem("hiden-control-language") === "en" ? "en" : "ru";
    } catch (error) {
      return "ru";
    }
  }

  function readTheme() {
    try {
      return localStorage.getItem("hiden-control-theme") === "dark" ? "dark" : "light";
    } catch (error) {
      return "dark";
    }
  }

  function t(key) {
    return translations[state.language][key] || translations.ru[key] || key;
  }

  function enumLabel(prefix, code) {
    if (code == null) return t("common.not_available");
    const key = `${prefix}.${code}`;
    return translations.ru[key] ? t(key) : `${t("common.code")} ${code}`;
  }

  function countLabel(count, base) {
    if (state.language !== "ru") {
      return `${count} ${count === 1 ? t(`${base}s_one`) : t(`${base}s_many`)}`;
    }
    const mod10 = count % 10;
    const mod100 = count % 100;
    let key = `${base}s_many`;
    if (mod10 === 1 && mod100 !== 11) key = `${base}s_one`;
    else if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) key = `${base}s_few`;
    return `${count} ${t(key)}`;
  }

  function applyLanguage() {
    document.documentElement.lang = state.language === "en" ? "en" : "ru";
    document.title = t("page.title");
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = t("page.description");
    document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
    document.querySelectorAll("[data-i18n-label]").forEach((node) => { node.label = t(node.dataset.i18nLabel); });
    document.querySelectorAll("[data-i18n-title]").forEach((node) => { node.title = t(node.dataset.i18nTitle); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => { node.placeholder = t(node.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => { node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel)); });
    document.querySelectorAll("[data-lang]").forEach((button) => {
      const active = normalizeLang(button.dataset.lang) === state.language;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const legend = $("legendLabel");
    if (legend) legend.textContent = t((metricMeta[state.metric] || metricMeta.load_power_w).labelKey);
    updateThemeToggleTooltip();
    if (state.health) renderHealth(state.health);
    if (state.current) renderCurrent(state.current);
    if (state.history) renderHistory(state.history);
    if (state.battery) renderBattery(state.battery);
    if (state.finance) renderFinance();
    if (state.tariffs) renderTariffs();
    if (state.host) renderMachine(state.host, state.health);
  }

  function updateThemeToggleTooltip() {
    const toggle = $("themeToggle");
    if (!toggle) return;
    const text = t(state.theme === "light" ? "theme.to_dark" : "theme.to_light");
    toggle.title = text;
    toggle.setAttribute("aria-label", text);
  }

  function applyTheme(theme) {
    state.theme = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = state.theme;
    updateThemeToggleTooltip();
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = state.theme === "light" ? "#eef2f5" : "#0d1117";
    if (state.history) renderChart();
  }

  function locale() { return state.language === "en" ? "en-GB" : "ru-RU"; }

  function number(value, decimals = 0) {
    if (!safeNumber(value)) return "--";
    return new Intl.NumberFormat(locale(), { maximumFractionDigits: decimals, minimumFractionDigits: decimals }).format(value);
  }

  function power(value) {
    if (!safeNumber(value)) return "--";
    const absolute = Math.abs(value);
    return absolute >= 1000 ? `${number(value / 1000, 2)} kW` : `${number(value, 0)} W`;
  }

  function valueWithUnit(value, unit, decimals = 1) {
    return safeNumber(value) ? `${number(value, decimals)} ${unit}` : `-- ${unit}`;
  }

  function timeLabel(iso) {
    if (!iso) return t("common.waiting");
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "--";
    return new Intl.DateTimeFormat(locale(), { dateStyle: "short", timeStyle: "medium" }).format(date);
  }

  function shortTime(iso, period = state.period) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    if (period === "month" || period === "week" || period === "day") return new Intl.DateTimeFormat(locale(), { month: "short", day: "numeric" }).format(date);
    return new Intl.DateTimeFormat(locale(), { hour: "2-digit", minute: "2-digit" }).format(date);
  }

  function uptimeLabel(uptime) {
    if (!uptime || !safeNumber(uptime.days)) return "--";
    const pad = (part) => String(Math.max(0, part)).padStart(2, "0");
    return `${uptime.days} ${t("uptime.day_short")} ${pad(uptime.hours)}:${pad(uptime.minutes)}`;
  }

  function durationLabel(seconds) {
    if (!safeNumber(seconds) || seconds < 0) return "--";
    const total = Math.round(seconds);
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const pad = (part) => String(part).padStart(2, "0");
    if (days > 0) return `${days} ${t("uptime.day_short")} ${pad(hours)}:${pad(minutes)}`;
    return `${pad(hours)}:${pad(minutes)}`;
  }

  function energy(kwh) {
    return safeNumber(kwh) ? `${number(kwh, 2)} kWh` : "-- kWh";
  }

  function money(rub) {
    return safeNumber(rub) ? `${number(rub, 2)} ₽` : "-- ₽";
  }

  function tariffLabel(price) {
    return safeNumber(price) ? `${number(price, 2)} ₽/кВт·ч` : t("finance.no_tariff");
  }

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

  function statusMeta(status) {
    return {
      online: [t("system.connected"), t("system.ok"), t("system.channel_ok")],
      degraded: [t("system.partial"), t("system.degraded"), t("system.partial_detail")],
      offline: [t("system.offline"), t("system.offline"), t("system.offline_detail")],
      starting: [t("system.starting"), t("system.waiting"), t("system.starting_detail")],
      stale: [t("system.stale"), t("system.stale"), t("system.stale_detail")],
    }[status] || [t("common.not_available"), t("common.not_available"), t("common.not_available")];
  }

  // ------------------------------------------------------------------ auth

  const AUTH_STORAGE_KEY = "sbridge-auth-token";

  function authToken() {
    try {
      return localStorage.getItem(AUTH_STORAGE_KEY) || "";
    } catch (error) {
      return "";
    }
  }

  function authHeaders() {
    const headers = { Accept: "application/json" };
    const token = authToken();
    if (token) headers["X-Auth-Token"] = token;
    return headers;
  }

  function showAuthOverlay() {
    const overlay = $("authOverlay");
    if (overlay) overlay.hidden = false;
  }

  function hideAuthOverlay() {
    const overlay = $("authOverlay");
    if (overlay) overlay.hidden = true;
  }

  function waitForLogin() {
    // Resolved once the user submits valid credentials; the 401 retry then
    // re-runs the failed request. Only one dialog is wired per page load.
    if (!window.__sbAuthWait) {
      window.__sbAuthWait = new Promise((resolve) => {
        const form = $("authForm");
        if (!form) { resolve(false); return; }
        showAuthOverlay();
        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          const button = form.querySelector("button[type=submit]");
          if (button) button.disabled = true;
          const error = $("authError");
          if (error) error.hidden = true;
          try {
            const response = await fetch("/api/auth/login", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                login: ($("authLogin") && $("authLogin").value) || "",
                password: ($("authPassword") && $("authPassword").value) || "",
              }),
            });
            if (!response.ok) throw new Error("bad credentials");
            const data = await response.json();
            try {
              localStorage.setItem(AUTH_STORAGE_KEY, data.token || "");
            } catch (storageError) { /* private mode: cookie still works */ }
            hideAuthOverlay();
            resolve(true);
          } catch (loginError) {
            if (error) error.hidden = false;
          } finally {
            if (button) button.disabled = false;
          }
        });
      });
    }
    return window.__sbAuthWait;
  }

  async function getJson(url) {
    const response = await fetch(url, { headers: authHeaders(), cache: "no-store" });
    if (response.status === 401) {
      // Login required (or the stored token expired): ask, then retry once.
      await waitForLogin();
      const retry = await fetch(url, { headers: authHeaders(), cache: "no-store" });
      const retryBody = await retry.json();
      if (!retry.ok) throw new Error(retryBody.error || `HTTP ${retry.status}`);
      return retryBody;
    }
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
    return body;
  }

  async function ensureAuth() {
    try {
      const status = await fetch("/api/auth/status", { headers: authHeaders(), cache: "no-store" });
      const body = await status.json();
      if (body.auth_required && !body.authenticated) await waitForLogin();
    } catch (error) { /* service down: the regular error paths will show it */ }
  }

  function cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  }

  function collectAlarms(snapshot) {
    const inverter = (snapshot.status && snapshot.status.inverter) || {};
    const charger = (snapshot.status && snapshot.status.charger) || {};
    const errors = [
      ...(inverter.error_flags || []).map((flag) => ({ ...flag, source: "inverter" })),
      ...(charger.error_flags || []).map((flag) => ({ ...flag, source: "charger" })),
    ];
    const warnings = [
      ...(inverter.warning_flags || []).map((flag) => ({ ...flag, source: "inverter" })),
      ...(charger.warning_flags || []).map((flag) => ({ ...flag, source: "charger" })),
    ];
    return { errors, warnings };
  }

  function flagLabel(flag) {
    const label = t(flag.key);
    if (label === flag.key) return `${t("fault.unknown")} · bit ${flag.bit}`;
    return label;
  }

  function updateDiagnosticBadge() {
    const badge = $("diagnosticBadge");
    if (!badge) return;
    if (state.alarms.errors.length) {
      badge.dataset.state = "alarm";
      badge.textContent = t("diagnostics.alarm");
      return;
    }
    if (state.alarms.warnings.length) {
      badge.dataset.state = "warning";
      badge.textContent = t("diagnostics.warning");
      return;
    }
    const status = (state.health && state.health.status) || "starting";
    badge.dataset.state = status;
    badge.textContent = status === "online" ? t("diagnostics.nominal") : status.toUpperCase();
  }

  function renderAlarms(snapshot) {
    const alarms = collectAlarms(snapshot);
    state.alarms = alarms;
    const badge = $("alarmBadge");
    if (badge) {
      const total = alarms.errors.length + alarms.warnings.length;
      badge.hidden = total === 0;
      badge.dataset.severity = alarms.errors.length ? "error" : "warning";
      const parts = [];
      if (alarms.errors.length) parts.push(countLabel(alarms.errors.length, "alarm.error"));
      if (alarms.warnings.length) parts.push(countLabel(alarms.warnings.length, "alarm.warning"));
      setText("alarmBadgeText", parts.join(" · "));
    }
    const chips = $("alarmChips");
    const chipsList = $("alarmChipsList");
    if (chips && chipsList) {
      chipsList.replaceChildren();
      const items = [
        ...alarms.errors.map((flag) => ({ ...flag, severity: "error" })),
        ...alarms.warnings.map((flag) => ({ ...flag, severity: "warning" })),
      ];
      chips.hidden = items.length === 0;
      items.forEach((flag) => {
        const chip = document.createElement("span");
        chip.className = "fault-chip";
        chip.dataset.severity = flag.severity;
        const code = document.createElement("b");
        code.textContent = flag.code;
        chip.append(code, document.createTextNode(flagLabel(flag)));
        chipsList.append(chip);
      });
    }
    updateDiagnosticBadge();
  }

  function renderHealth(health) {
    if (!health) return;
    state.health = health;
    // The footer version always mirrors the running service, not a static string.
    if (health.version) setText("footerVersion", `v${health.version}`);
    const status = health.status || "starting";
    const [badge, title, detail] = statusMeta(status);
    const badgeNode = $("connectionBadge");
    const systemNode = $("systemState");
    if (badgeNode) { badgeNode.dataset.state = status; }
    if (systemNode) { systemNode.dataset.state = status; }
    setText("connectionLabel", badge);
    setText("systemStateTitle", title);
    setText("systemStateText", detail);
    setText("pollLatency", safeNumber(health.latency_ms) ? `${number(health.latency_ms, 0)} ms` : "--");
    const error = health.last_error ? `${t("common.error")}: ${health.last_error}` : t("health.active");
    const staleAge = safeNumber(health.sample_age_seconds) ? ` · ${number(health.sample_age_seconds, 0)} s` : "";
    setText("healthMessage", status === "online" ? t("health.active") : status === "stale" ? `${t("health.stale_age")}${staleAge}` : error);
    renderVersionBanner(health);
    renderDiskBanner(health);
    updateDiagnosticBadge();
  }

  function renderDiskBanner(health) {
    const banner = $("diskBanner");
    if (!banner) return;
    if (health.storage_paused) {
      banner.hidden = false;
      setText(
        "diskBannerText",
        t("disk.banner")
          .replace("{free}", number(health.disk_free_percent, 1))
          .replace("{min}", number(health.disk_min_free_percent, 0))
      );
    } else {
      banner.hidden = true;
    }
  }

  function renderVersionBanner(health) {
    const banner = $("versionBanner");
    if (!banner) return;
    const local = health.version;
    const master = health.master_app_version;
    const mismatch = Boolean(master && local && master !== local);
    banner.hidden = !mismatch;
    if (mismatch) {
      setText(
        "versionBannerText",
        t("system.version_mismatch").replace("{master}", master).replace("{local}", local)
      );
    }
  }

  function renderMachine(host, health) {
    const section = $("machineSection");
    if (!section) return;
    if (!host) { section.hidden = true; return; }
    state.host = host;
    section.hidden = false;
    setText("machineCpu", safeNumber(host.cpu_temp_c) ? `${number(host.cpu_temp_c, 1)} °C` : "--");
    const loads = [host.load_1m, host.load_5m, host.load_15m];
    setText("machineLoad", loads.every(safeNumber) ? loads.map((value) => number(value, 2)).join(" / ") : "--");
    setText("machineRam", safeNumber(host.mem_used_percent) ? `${number(host.mem_used_percent, 1)} %` : "--");
    setText("machineDisk", safeNumber(host.disk_used_percent) ? `${number(host.disk_used_percent, 1)} %` : "--");
    setText("machineId", host.master_id || (health && health.master_id) || "--");
    setText("machineVersion", (health && (health.master_app_version || health.version)) || "--");
    setText("machineUptime", durationLabel((health && health.master_service_uptime_s) || host.service_uptime_s));
    setText("machineHostUptime", durationLabel(host.uptime_s));
    const throttled = $("machineThrottled");
    if (throttled) {
      throttled.classList.remove("is-ok", "is-bad");
      if (host.throttled === true) {
        throttled.textContent = t("machine.throttled_bad");
        throttled.classList.add("is-bad");
        throttled.title = host.throttled_raw || "";
      } else if (host.throttled === false) {
        throttled.textContent = t("machine.throttled_ok");
        throttled.classList.add("is-ok");
        throttled.title = "";
      } else {
        throttled.textContent = t("machine.unknown");
        throttled.title = "";
      }
    }
    const hbAge = health && health.heartbeat_age_seconds;
    setText(
      "machineHeartbeat",
      safeNumber(hbAge) ? t("machine.seconds_ago").replace("{n}", number(hbAge, 0)) : "--"
    );
  }

  function stateLabel(code) {
    return enumLabel("state", code);
  }

  function setFlowChip(node, active, text) {
    if (!node) return;
    node.hidden = false;
    node.classList.add("flow-chip");
    node.classList.toggle("is-on", Boolean(active));
    node.textContent = text;
  }

  function renderFlows(inverter) {
    const pvChip = $("pvFlow");
    const loadChip = $("loadFlow");
    const gridChip = $("gridFlow");
    const battChip = $("batteryState");
    if (!pvChip || !loadChip || !gridChip || !battChip) return;
    const arrow = inverter.arrow;
    if (!arrow) {
      pvChip.hidden = true;
      loadChip.hidden = true;
      gridChip.hidden = true;
      battChip.classList.remove("flow-chip", "is-on");
      battChip.hidden = false;
      battChip.textContent = `${t("common.state")} ${stateLabel(inverter.work_state_code)}`;
      return;
    }
    setFlowChip(pvChip, arrow.pv_to_machine, t("flow.pv"));
    setFlowChip(loadChip, arrow.machine_to_load, t("flow.load"));
    const gridModes = { 0: ["flow.grid.off", false], 1: ["flow.grid.sell", true], 2: ["flow.grid.buy", true], 3: ["flow.grid.connected", true] };
    const gridMode = gridModes[arrow.machine_grid];
    if (gridMode) setFlowChip(gridChip, gridMode[1], t(gridMode[0])); else gridChip.hidden = true;
    const battModes = { 0: ["flow.batt.off", false], 1: ["flow.batt.charge", true], 2: ["flow.batt.discharge", true], 3: ["flow.batt.connected", true] };
    const battMode = battModes[arrow.machine_battery];
    if (battMode) setFlowChip(battChip, battMode[1], t(battMode[0])); else battChip.hidden = true;
  }

  // ------------------------------------------------------------------ flow diagram (hero)

  const FLOW_MIN_W = 5;
  const FLOW_SPEED_LOW_W = 80;
  const FLOW_SPEED_HIGH_W = 5500;

  function flowDuration(watts) {
    const value = Math.min(FLOW_SPEED_HIGH_W, Math.max(FLOW_SPEED_LOW_W, Math.abs(watts || 0)));
    const ratio = (value - FLOW_SPEED_LOW_W) / (FLOW_SPEED_HIGH_W - FLOW_SPEED_LOW_W);
    return `${(4.0 - ratio * 2.9).toFixed(2)}s`;
  }

  function setEdge(id, active, watts, reverse = false) {
    const edge = document.getElementById(id);
    if (!edge) return;
    edge.classList.toggle("is-active", active);
    edge.classList.toggle("is-reverse", active && reverse);
    if (active) edge.style.animationDuration = flowDuration(watts);
    else edge.style.removeProperty("animation-duration");
  }

  function setFlowText(id, watts) {
    const node = document.getElementById(id);
    if (node) node.textContent = safeNumber(watts) ? power(watts) : "--";
  }

  function renderFlowDiagram(metrics, inverter) {
    const svg = $("flowDiagram");
    if (!svg) return;
    const arrow = (inverter && inverter.arrow) || null;
    const pv = safeNumber(metrics.pv_power_w) ? Math.abs(metrics.pv_power_w) : 0;
    const load = safeNumber(metrics.load_power_w) ? Math.abs(metrics.load_power_w) : 0;
    const grid = safeNumber(metrics.grid_power_w) ? metrics.grid_power_w : 0;
    const batt = safeNumber(metrics.battery_power_w) ? metrics.battery_power_w : 0;

    const gridMode = arrow ? arrow.machine_grid : null;
    const battMode = arrow ? arrow.machine_battery : null;
    // The arrow register is authoritative; sign is the fallback for ambiguous "connected".
    const gridSell = gridMode != null ? gridMode === 1 || (gridMode === 3 && grid < 0) : grid < 0;
    const battDischarge = battMode != null ? battMode === 2 || (battMode === 3 && batt < 0) : batt < 0;

    setEdge("edgePv", pv > FLOW_MIN_W, pv);
    setEdge("edgeGrid", Math.abs(grid) > FLOW_MIN_W, Math.abs(grid), gridSell);
    setEdge("edgeLoad", load > FLOW_MIN_W, load);
    setEdge("edgeBatt", Math.abs(batt) > FLOW_MIN_W, Math.abs(batt), battDischarge);

    setFlowText("flowPvPower", pv);
    setFlowText("flowGridPower", grid);
    setFlowText("flowLoadPower", load);
    setFlowText("flowBattPower", Math.abs(batt));

    const battFlow = battMode === 1 ? "charge" : battMode === 2 ? "discharge" : null;
    const battState = battFlow || (Math.abs(batt) > FLOW_MIN_W ? (battDischarge ? "discharge" : "charge") : "idle");
    svg.dataset.battState = battState;
  }

  // ------------------------------------------------------------------ battery bank

  const SOC_RING_RADIUS = 27;
  const SOC_RING_LENGTH = 2 * Math.PI * SOC_RING_RADIUS;

  function bankModuleState(metrics) {
    if (safeNumber(metrics.protection_bits) && metrics.protection_bits !== 0) return "fault";
    // pace-modbus-rtu reports warnings in warning_bits, pylon in alarm_bits.
    const alarm = safeNumber(metrics.alarm_bits) ? metrics.alarm_bits : metrics.warning_bits;
    if (safeNumber(alarm) && alarm !== 0) return "alarm";
    if (!safeNumber(metrics.soc_percent)) return "offline";
    return "ok";
  }

  function bankProblems(payload) {
    const status = payload && payload.status;
    if (!status || typeof status !== "object") return [];
    const problems = [];
    ["protection", "cell_warn", "temp_warn", "errors"].forEach((key) => {
      if (Array.isArray(status[key])) problems.push(...status[key].filter(Boolean).map(String));
    });
    ["charge_current_warn", "voltage_warn", "discharge_current_warn"].forEach((key) => {
      if (status[key]) problems.push(String(status[key]));
    });
    return problems;
  }

  function bankStat(label, value, tone = "") {
    const stat = document.createElement("div");
    stat.className = "bank-stat";
    const name = document.createElement("span");
    name.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    if (tone) strong.classList.add(tone);
    stat.append(name, strong);
    return stat;
  }

  function bankCard(module, position = 0) {
    const metrics = (module && module.metrics) || {};
    const payload = (module && module.payload) || {};
    const problems = bankProblems(payload);
    const card = document.createElement("article");
    card.className = "bank-card";
    card.dataset.state = bankModuleState(metrics);
    if (problems.length) card.title = problems.join("\n");

    const index = safeNumber(module.module_index) ? Math.trunc(module.module_index) : null;
    const extended = payload.extended || {};
    const serial = (extended.module_sn && extended.module_sn.sn) || module.module_serial
      || (index != null ? `ADR ${index}` : t("bank.no_data"));

    const top = document.createElement("div");
    top.className = "bank-top";
    const name = document.createElement("span");
    name.textContent = index != null ? `MODULE ${String(index).padStart(2, "0")}` : "MODULE";
    const serialNode = document.createElement("span");
    serialNode.className = "bank-serial";
    serialNode.textContent = serial;
    const led = document.createElement("span");
    led.className = "bank-led";
    top.append(name, serialNode, led);

    const soc = safeNumber(metrics.soc_percent) ? Math.max(0, Math.min(100, metrics.soc_percent)) : null;
    const level = soc == null ? "none" : soc > 49 ? "high" : soc > 19 ? "mid" : "low";
    const ring = document.createElement("div");
    ring.className = "bank-ring";
    ring.dataset.level = level;
    ring.title = t("bank.soc_title");
    const svgNs = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("viewBox", "0 0 64 64");
    svg.setAttribute("aria-hidden", "true");
    const track = document.createElementNS(svgNs, "circle");
    track.setAttribute("class", "ring-track");
    track.setAttribute("cx", "32");
    track.setAttribute("cy", "32");
    track.setAttribute("r", String(SOC_RING_RADIUS));
    svg.append(track);
    if (soc != null) {
      const value = document.createElementNS(svgNs, "circle");
      value.setAttribute("class", "ring-value");
      value.setAttribute("cx", "32");
      value.setAttribute("cy", "32");
      value.setAttribute("r", String(SOC_RING_RADIUS));
      value.setAttribute("stroke-dasharray", `${(soc * SOC_RING_LENGTH / 100).toFixed(1)} ${SOC_RING_LENGTH.toFixed(1)}`);
      svg.append(value);
    }
    const ringLabel = document.createElement("span");
    ringLabel.className = "bank-ring-label";
    const socStrong = document.createElement("strong");
    socStrong.textContent = soc == null ? "--" : number(soc, 0);
    const socSmall = document.createElement("small");
    socSmall.textContent = "SOC";
    ringLabel.append(socStrong, socSmall);
    ring.append(svg, ringLabel);

    const current = metrics.current_a;
    const tone = safeNumber(current) ? (current > 0.05 ? "is-charge" : current < -0.05 ? "is-discharge" : "") : "";
    const temp = safeNumber(metrics.temp_min_c) && safeNumber(metrics.temp_max_c)
      ? `${number(metrics.temp_min_c, 0)}…${number(metrics.temp_max_c, 0)}`
      : safeNumber(metrics.temp_max_c) ? number(metrics.temp_max_c, 0) : "--";

    const stats = document.createElement("div");
    stats.className = "bank-stats";
    stats.append(
      bankStat("V", safeNumber(metrics.voltage_v) ? number(metrics.voltage_v, 2) : "--"),
      bankStat("A", safeNumber(current) ? number(current, 1) : "--", tone),
      bankStat("°C", temp),
      bankStat(t("bank.cycles"), safeNumber(metrics.cycles) ? number(metrics.cycles, 0) : "--"),
      bankStat(`${t("bank.cell_delta")} mV`, safeNumber(metrics.cell_delta_v) ? number(metrics.cell_delta_v * 1000, 0) : "--"),
      bankStat("SOH %", safeNumber(metrics.soh_percent) ? number(metrics.soh_percent, 0) : "--"),
    );

    const main = document.createElement("div");
    main.className = "bank-main";
    main.append(ring, stats);
    card.append(top, main);
    const extra = bankExtraBlock(module, index != null ? index : position);
    if (extra) card.append(extra);
    return card;
  }

  function bankEmptyCard() {
    const card = document.createElement("div");
    card.className = "bank-empty";
    card.textContent = t("bank.waiting");
    return card;
  }

  function bankHexByte(value) {
    return safeNumber(value) ? `0x${Math.trunc(value).toString(16).padStart(2, "0").toUpperCase()}` : "--";
  }

  function bankIssue(text, severity) {
    const row = document.createElement("div");
    row.className = `bank-issue is-${severity}`;
    row.textContent = text;
    return row;
  }

  function bankCellStrip(cells) {
    const values = cells.filter((value) => safeNumber(value));
    if (!values.length) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = Math.max(0.004, (max - min) * 0.18);
    const lo = min - pad;
    const hi = max + pad;
    const wrap = document.createElement("div");
    wrap.className = "bank-cells-block";
    const strip = document.createElement("div");
    strip.className = "bank-cells";
    values.forEach((v, i) => {
      const cell = document.createElement("span");
      cell.className = "bank-cell";
      if (values.length > 1) {
        if (v === min) cell.classList.add("is-min");
        if (v === max) cell.classList.add("is-max");
      }
      cell.title = `Cell ${i + 1}: ${number(v, 3)} V`;
      const fill = document.createElement("i");
      fill.style.height = `${Math.max(8, Math.min(100, ((v - lo) / (hi - lo)) * 100)).toFixed(0)}%`;
      cell.append(fill);
      strip.append(cell);
    });
    const caption = document.createElement("div");
    caption.className = "bank-cells-caption";
    caption.textContent = `min ${number(min, 3)} V · max ${number(max, 3)} V · Δ ${number((max - min) * 1000, 0)} mV`;
    wrap.append(strip, caption);
    return wrap;
  }

  function bankExtraBlock(module, position) {
    const payload = (module && module.payload) || {};
    const metrics = (module && module.metrics) || {};
    const analog = payload.analog || null;
    const status = payload.status || null;
    const extended = payload.extended || {};
    const pace = !analog;
    const cells = analog ? (analog.cells_mv || []).map((mv) => mv / 1000) : (payload.cells_v || []);
    const temperatureList = ((analog ? analog.temps_c : payload.temps_c) || []).filter((value) => safeNumber(value));
    if (pace) {
      [payload.mos_temp_c, payload.env_temp_c].forEach((value) => {
        if (safeNumber(value)) temperatureList.push(value);
      });
    }
    const capacity = analog
      ? [analog.remain_ah, analog.full_ah, analog.design_ah]
      : [payload.remain_capacity_ah, payload.full_capacity_ah, payload.design_capacity_ah];
    const chargeLimits = extended.charge_limits || null;
    const systemParams = extended.system_params || null;

    const details = document.createElement("details");
    details.className = "bank-details";
    // The card is rebuilt on every snapshot; keep the open state per module.
    const key = String(position);
    details.open = Boolean(state.bankExpanded[key]);
    details.addEventListener("toggle", () => {
      if (details.open) state.bankExpanded[key] = true;
      else delete state.bankExpanded[key];
    });
    const summary = document.createElement("summary");
    const summaryText = document.createElement("span");
    summaryText.textContent = t("bank.expand");
    const protocol = document.createElement("span");
    protocol.className = "bank-protocol";
    protocol.textContent = payload.protocol || "--";
    summary.append(summaryText, protocol);

    const extra = document.createElement("div");
    extra.className = "bank-extra";
    const rows = document.createElement("div");
    rows.className = "bank-rows";
    const addRow = (label, value) => {
      const row = document.createElement("div");
      row.className = "bank-row";
      const name = document.createElement("span");
      name.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      row.append(name, strong);
      rows.append(row);
    };

    const cellsBlock = cells.length ? bankCellStrip(cells) : null;
    if (cellsBlock) extra.append(cellsBlock);

    if (temperatureList.length) {
      addRow(t("bank.temps"), `${temperatureList.map((value) => number(value, 1)).join(" · ")} °C`);
    }
    if (capacity.some((value) => safeNumber(value))) {
      let text = `${number(capacity[0], 1)} / ${number(capacity[1], 1)} Ah`;
      if (safeNumber(capacity[2]) && capacity[2] > 0) text += ` (${number(capacity[2], 0)})`;
      addRow(t("bank.capacity"), text);
    }
    if (status && Array.isArray(status.system) && status.system.length) {
      addRow(t("bank.mos_state"), status.system.join(" · "));
    }
    if (pace) {
      addRow(t("bank.flags"), [
        `warn ${bankHexByte(metrics.warning_bits)}`,
        `prot ${bankHexByte(metrics.protection_bits)}`,
        `stat ${bankHexByte(metrics.status_bits)}`,
        `bal ${bankHexByte(metrics.balance_bits)}`,
      ].join(" · "));
    }
    if (chargeLimits && safeNumber(chargeLimits.charge_voltage_limit_v)) {
      addRow(t("bank.charge_limit"),
        `${number(chargeLimits.charge_voltage_limit_v, 2)} V · ${number(chargeLimits.charge_current_limit_a, 1)} A`);
      addRow(t("bank.discharge_limit"),
        `${number(chargeLimits.discharge_voltage_limit_v, 2)} V · ${number(chargeLimits.discharge_current_limit_a, 1)} A`);
      const flags = [];
      if (chargeLimits.charge_enable) flags.push(t("bank.flag_charge_enable"));
      if (chargeLimits.discharge_enable) flags.push(t("bank.flag_discharge_enable"));
      if (chargeLimits.charge_immediately) flags.push(t("bank.flag_charge_now"));
      if (chargeLimits.full_charge_request) flags.push(t("bank.flag_full_charge"));
      if (flags.length) addRow(t("bank.flags"), flags.join(" · "));
    }
    if (systemParams && safeNumber(systemParams.cell_voltage_high_limit_v)) {
      addRow(t("bank.lim_cell_high"), `${number(systemParams.cell_voltage_high_limit_v, 3)} V`);
      addRow(t("bank.lim_cell_low_alarm"), `${number(systemParams.cell_voltage_low_alarm_v, 3)} V`);
      addRow(t("bank.lim_cell_low_protect"), `${number(systemParams.cell_voltage_low_protect_v, 3)} V`);
      addRow(t("bank.lim_mod_high"), `${number(systemParams.module_voltage_high_limit_v, 1)} V`);
      addRow(t("bank.lim_mod_low_alarm"), `${number(systemParams.module_voltage_low_alarm_v, 1)} V`);
      addRow(t("bank.lim_mod_low_protect"), `${number(systemParams.module_voltage_low_protect_v, 1)} V`);
      addRow(t("bank.lim_chg_temp"), `${number(systemParams.charge_high_temp_limit_c, 0)} / ${number(systemParams.charge_low_temp_limit_c, 0)} °C`);
      addRow(t("bank.lim_dis_temp"), `${number(systemParams.discharge_high_temp_limit_c, 0)} / ${number(systemParams.discharge_low_temp_limit_c, 0)} °C`);
    }
    if (rows.children.length) extra.append(rows);

    if (status) {
      const issues = [];
      (Array.isArray(status.protection) ? status.protection : []).forEach((name) => issues.push(bankIssue(name, "fault")));
      ["cell_warn", "temp_warn"].forEach((key) => {
        (Array.isArray(status[key]) ? status[key] : []).forEach((name) => issues.push(bankIssue(name, "warn")));
      });
      ["charge_current_warn", "voltage_warn", "discharge_current_warn"].forEach((key) => {
        if (status[key]) issues.push(bankIssue(status[key], "warn"));
      });
      if (Array.isArray(status.cell_faults) && status.cell_faults.length) {
        issues.push(bankIssue(`${t("bank.cell_faults")}: ${status.cell_faults.join(", ")}`, "fault"));
      }
      (Array.isArray(status.errors) ? status.errors : []).forEach((name) => issues.push(bankIssue(String(name), "fault")));
      (Array.isArray(status.state) ? status.state : []).forEach((name) => issues.push(bankIssue(name, "info")));
      if (issues.length) {
        const block = document.createElement("div");
        block.className = "bank-issues";
        const title = document.createElement("span");
        title.className = "bank-extra-title";
        title.textContent = t("bank.diagnostics");
        block.append(title, ...issues);
        extra.append(block);
      }
      if (status.raw) {
        const raw = document.createElement("div");
        raw.className = "bank-raw";
        raw.textContent = status.raw;
        extra.append(raw);
      }
    }

    if (!extra.childNodes.length) return null;
    details.append(summary, extra);
    return details;
  }

  function renderBattery(battery) {
    state.battery = battery || null;
    const heading = $("bankHeading");
    const grid = $("bankGrid");
    if (!heading || !grid) return;
    const healthBattery = (state.health && state.health.battery) || null;
    const modules = battery && Array.isArray(battery.modules) ? battery.modules : [];
    const visible = Boolean(healthBattery) || modules.length > 0;
    heading.hidden = !visible;
    grid.hidden = !visible;
    if (!visible) { grid.replaceChildren(); return; }
    const note = $("bankNote");
    if (note) {
      const counts = healthBattery && safeNumber(healthBattery.modules_total)
        ? `${t("bank.online")} ${number(healthBattery.modules_online, 0)}/${number(healthBattery.modules_total, 0)}`
        : "";
      note.textContent = counts ? `${t("bank.note")} · ${counts}` : t("bank.note");
    }
    grid.replaceChildren();
    if (!modules.length) { grid.append(bankEmptyCard()); return; }
    modules.forEach((module, position) => grid.append(bankCard(module, position)));
  }

  function renderRelays(inverter, charger) {
    const strip = $("relayStrip");
    if (!strip) return;
    const items = [
      ["inverter", inverter.inverter_relay_connected],
      ["grid", inverter.grid_relay_connected],
      ["load", inverter.load_relay_connected],
      ["n_line", inverter.n_line_relay_connected],
      ["dc", inverter.dc_relay_connected],
      ["earth", inverter.earth_relay_connected],
      ["battery", charger.battery_relay_connected],
      ["pv", charger.pv_relay_connected],
    ];
    strip.replaceChildren();
    items.forEach(([key, connected]) => {
      if (connected == null) return;
      const chip = document.createElement("span");
      chip.className = `relay-chip${connected ? " is-on" : " is-off"}`;
      chip.textContent = t(`relay.${key}`);
      chip.title = `${t(`relay.${key}_full`)}: ${connected ? t("relay.on") : t("relay.off")}`;
      strip.append(chip);
    });
  }

  function renderChargerStages(charger) {
    const parts = [];
    if (charger.work_state_code != null) parts.push(enumLabel("chg.work", charger.work_state_code));
    if (charger.mppt_state_code != null) parts.push(enumLabel("chg.mppt", charger.mppt_state_code));
    if (charger.charging_state_code != null) parts.push(enumLabel("chg.charging", charger.charging_state_code));
    setText("chargerStage", parts.join(" · ") || t("common.not_available"));
  }

  function renderCurrent(snapshot) {
    if (!snapshot) return;
    state.current = snapshot;
    const metrics = snapshot.metrics || {};
    const identity = snapshot.identity || {};
    const chargerIdentity = snapshot.charger_identity || {};
    const inverter = (snapshot.status && snapshot.status.inverter) || {};
    const charger = (snapshot.status && snapshot.status.charger) || {};
    setText("lastUpdated", timeLabel(snapshot.captured_at));
    setText("sourcePort", snapshot.source ? `${snapshot.source.port} · ID ${snapshot.source.slave_id}` : t("common.source_usb"));
    setText("pvPower", power(metrics.pv_power_w));
    setText("pvVoltage", valueWithUnit(metrics.pv_voltage_v, "V", 1));
    setText("pvCurrent", valueWithUnit(metrics.pv_current_a, "A", 1));
    setText("loadPower", power(metrics.load_power_w));
    setText("loadPercent", `${number(metrics.load_percent, 0)}%`);
    setText("loadCurrent", valueWithUnit(metrics.load_current_a, "A", 1));
    setText("gridPower", power(metrics.grid_power_w));
    setText("gridVoltage", valueWithUnit(metrics.grid_voltage_v, "V", 1));
    setText("gridFrequency", valueWithUnit(metrics.grid_frequency_hz, "Hz", 2));
    setText("batteryVoltage", valueWithUnit(metrics.battery_voltage_v, "V", 2));
    setText("batteryPower", power(metrics.battery_power_w));
    const loadBar = $("loadBar");
    if (loadBar) loadBar.style.width = `${Math.max(0, Math.min(100, metrics.load_percent || 0))}%`;
    const batteryBar = $("batteryBar");
    if (batteryBar) batteryBar.style.width = `${batteryVoltagePosition(metrics.battery_voltage_v, snapshot.configuration)}%`;

    setText("identityModel", identity.model || "PV1800");
    setText("ratedPower", safeNumber(metrics.rated_power_w)
      ? `${number(metrics.rated_power_w, 0)} W`
      : safeNumber(metrics.rated_power_va) ? `${number(metrics.rated_power_va, 0)} VA` : "--");
    setText("identitySerial", identity.serial_number || inverter.serial_number || "--");
    setText("identityFirmware", [identity.hardware_version, identity.software_version].filter(Boolean).join(" / ") || "--");
    setText("protocolVersion", [inverter.communication_protocol_version, identity.communication_protocol_version].find(Boolean) || "--");
    setText("chargerIdentity", [chargerIdentity.model, chargerIdentity.software_version].filter(Boolean).join(" · ") || "--");
    setText("workState", stateLabel(inverter.work_state_code));
    renderChargerStages(charger);
    renderRelays(inverter, charger);
    renderFlows(inverter);
    renderFlowDiagram(metrics, inverter);
    setText("inverterVoltage", valueWithUnit(metrics.inverter_voltage_v, "V", 1));
    setText("inverterCurrent", valueWithUnit(metrics.inverter_current_a, "A", 1));
    setText("inverterFrequency", valueWithUnit(metrics.inverter_frequency_hz, "Hz", 2));
    setText("inverterReactive", valueWithUnit(inverter.inverter_reactive_power_var, "var", 0));
    setText("inverterPowerFactor", safeNumber(inverter.power_factor) ? number(inverter.power_factor, 2) : "--");
    setText("busVoltage", valueWithUnit(metrics.bus_voltage_v, "V", 1));
    setText("batteryCurrent", valueWithUnit(inverter.battery_current_a, "A", 0));
    setText("pvVoltageDetail", valueWithUnit(metrics.pv_voltage_v, "V", 1));
    setText("pvCurrentDetail", valueWithUnit(metrics.pv_current_a, "A", 1));
    setText("tempAc", valueWithUnit(metrics.ac_radiator_temperature_c, "°C", 0));
    setText("tempDc", valueWithUnit(metrics.dc_radiator_temperature_c, "°C", 0));
    setText("tempTransformer", valueWithUnit(metrics.transformer_temperature_c, "°C", 0));
    setText("tempCharger", valueWithUnit(charger.radiator_temperature_c, "°C", 0));
    setText("accumulatedLoad", energy(inverter.accumulated_load_power_kwh));
    setText("accumulatedCharge", energy(inverter.accumulated_charger_power_kwh));
    setText("accumulatedDischarge", energy(inverter.accumulated_discharger_power_kwh));
    setText("chargerUptime", uptimeLabel(charger.uptime));
    renderConfiguration(snapshot.configuration);
    renderDiagnostics(snapshot);
    renderRaw(snapshot.raw);
    renderAlarms(snapshot);
  }

  function batteryVoltagePosition(voltage, configuration) {
    if (!safeNumber(voltage)) return 0;
    const inverter = configuration && configuration.inverter;
    const low = safeNumber(inverter && inverter.battery_low_voltage_v) ? inverter.battery_low_voltage_v : 24;
    const high = safeNumber(inverter && inverter.battery_high_voltage_v) ? inverter.battery_high_voltage_v : 30;
    return Math.max(0, Math.min(100, ((voltage - low) / Math.max(.1, high - low)) * 100));
  }

  function renderConfiguration(configuration) {
    const charger = configuration && configuration.charger;
    const inverter = configuration && configuration.inverter;
    const chargerRows = [
      [t("config.charger_work"), yesNo(charger && charger.charger_work_enabled)],
      [t("config.absorb_voltage"), valueWithUnit(charger && charger.absorb_voltage_v, "V", 1)],
      [t("config.float_voltage"), valueWithUnit(charger && charger.float_voltage_v, "V", 1)],
      [t("config.battery_low"), valueWithUnit(charger && charger.battery_low_voltage_v, "V", 1)],
      [t("config.battery_high"), valueWithUnit(charger && charger.battery_high_voltage_v, "V", 1)],
      [t("config.max_current"), valueWithUnit(charger && charger.max_charger_current_a, "A", 1)],
      [t("config.capacity"), valueWithUnit(charger && charger.battery_capacity_ah, "Ah", 0)],
      [t("config.battery_type"), enumLabel("cfg.battery_type", charger && charger.battery_type_code)],
      [t("config.equalization"), yesNo(charger && charger.equalization_enabled)],
    ];
    const inverterRows = [
      [t("config.offgrid"), yesNo(inverter && inverter.offgrid_work_enabled)],
      [t("config.output"), valueWithUnit(inverter && inverter.output_voltage_v, "V", 1)],
      [t("config.frequency"), valueWithUnit(inverter && inverter.output_frequency_hz, "Hz", 2)],
      [t("config.search_mode"), yesNo(inverter && inverter.search_mode_enabled)],
      [t("config.energy_mode"), enumLabel("cfg.energy", inverter && inverter.energy_use_mode_code)],
      [t("config.grid_standard"), enumLabel("cfg.grid_standard", inverter && inverter.grid_protect_standard_code)],
      [t("config.max_discharge"), valueWithUnit(inverter && inverter.max_discharger_current_a, "A", 1)],
      [t("config.grid_charge"), valueWithUnit(inverter && inverter.grid_max_charger_current_a, "A", 1)],
      [t("config.source_priority"), enumLabel("cfg.priority", inverter && inverter.charger_source_priority_code)],
      [t("config.system_flags"), systemFlagsLabel(inverter)],
    ];
    renderKeyValues("chargerConfig", chargerRows);
    renderKeyValues("inverterConfig", inverterRows);
  }

  function yesNo(value) {
    if (typeof value !== "boolean") return "--";
    return value ? (state.language === "en" ? "Yes" : "Да") : (state.language === "en" ? "No" : "Нет");
  }

  // Register 20142 "System setting": display-only bit expansion, so the raw
  // code stays visible next to the decoded names.
  const SYSTEM_FLAGS = [
    ["overload_restart_forbid", "cfg.sysflag.overload_restart"],
    ["overtemp_restart_forbid", "cfg.sysflag.overtemp_restart"],
    ["overload_bypass_forbid", "cfg.sysflag.overload_bypass"],
    ["auto_turn_page_forbid", "cfg.sysflag.auto_page"],
    ["grid_buzzer_enable", "cfg.sysflag.grid_buzzer"],
    ["buzzer_forbid", "cfg.sysflag.buzzer_off"],
    ["lcd_light_enable", "cfg.sysflag.lcd_light"],
  ];

  function systemFlagsLabel(inverter) {
    const flags = inverter && inverter.system_setting_flags;
    if (!flags) return "--";
    const active = SYSTEM_FLAGS.filter(([key]) => flags[key]).map(([, labelKey]) => t(labelKey));
    const none = state.language === "en" ? "none set" : "не заданы";
    const code = safeNumber(inverter.system_setting_code)
      ? ` (0x${Number(inverter.system_setting_code).toString(16).toUpperCase().padStart(4, "0")})`
      : "";
    return `${active.length ? active.join(" · ") : none}${code}`;
  }

  function renderKeyValues(id, rows) {
    const root = $(id);
    if (!root) return;
    root.replaceChildren();
    rows.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "key-value";
      const name = document.createElement("span");
      const result = document.createElement("span");
      name.textContent = label;
      result.textContent = value;
      row.append(name, result);
      root.append(row);
    });
  }

  function renderDiagnostics(snapshot) {
    const root = $("diagnosticsList");
    if (!root) return;
    const connection = snapshot.connection || {};
    const errors = connection.section_errors || {};
    const raw = snapshot.raw || {};
    const rows = [
      [t("diagnostics.channel"), connection.status || t("common.not_available")],
      [t("diagnostics.latency"), valueWithUnit(connection.latency_ms, "ms", 0)],
      [t("diagnostics.charger_error"), code(snapshot.status && snapshot.status.charger && snapshot.status.charger.error_code)],
      [t("diagnostics.charger_warning"), code(snapshot.status && snapshot.status.charger && snapshot.status.charger.warning_code)],
      [t("diagnostics.frames"), `${Object.keys(raw).length} / ${Object.keys(raw).length + Object.keys(errors).length}`],
      [t("diagnostics.section_errors"), Object.keys(errors).length ? Object.keys(errors).join(", ") : t("common.none")],
    ];
    root.replaceChildren();
    rows.forEach(([label, value]) => {
      const row = document.createElement("div");
      const name = document.createElement("span");
      const result = document.createElement("strong");
      name.textContent = label;
      result.textContent = value;
      row.append(name, result);
      root.append(row);
    });
  }

  function code(value) { return value == null ? t("common.not_available") : `${t("common.code")} ${value}`; }

  function renderRaw(raw) {
    const root = $("rawRegisters");
    if (!root) return;
    root.replaceChildren();
    Object.entries(raw || {}).forEach(([section, registers]) => {
      const wrapper = document.createElement("div");
      wrapper.className = "raw-section";
      const title = document.createElement("h4");
      title.textContent = `${section} · ${registers.length} ${t("common.registers")}`;
      const table = document.createElement("table");
      table.className = "raw-table";
      const body = document.createElement("tbody");
      registers.forEach((register, index) => {
        const row = document.createElement("tr");
        const indexCell = document.createElement("td");
        const valueCell = document.createElement("td");
        indexCell.textContent = String(index);
        valueCell.textContent = register == null ? "--" : `0x${Number(register).toString(16).padStart(4, "0").toUpperCase()} · ${register}`;
        row.append(indexCell, valueCell);
        body.append(row);
      });
      table.append(body);
      wrapper.append(title, table);
      root.append(wrapper);
    });
  }

  // ------------------------------------------------------------------ today totals

  async function loadToday() {
    try {
      const history = await getJson("/api/history?range=24h&period=hour");
      renderToday(history);
    } catch (error) { /* keep the previous totals on transient errors */ }
  }

  function todayBuckets(points) {
    const now = new Date();
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const nowTs = now.getTime();
    return points
      .map((point) => {
        const start = new Date(point.captured_at).getTime();
        if (Number.isNaN(start)) return null;
        const end = start + 3600000;
        const from = Math.max(start, midnight);
        const to = Math.min(end, nowTs);
        const hours = (to - from) / 3600000;
        if (hours <= 0) return null;
        return { point, hours };
      })
      .filter(Boolean);
  }

  function renderToday(history) {
    const strip = $("todayStrip");
    if (!strip) return;
    // Preferred source: the exact hardware counters behind /api/finance.
    const todayRow = ((state.finance && state.finance.rows) || [])
      .find((row) => row.date === localDateKey(0)) || null;
    const buckets = todayBuckets((history && history.points) || []);
    if (!todayRow && !buckets.length) { strip.hidden = true; return; }
    let totals;
    if (todayRow) {
      totals = {
        pv: safeNumber(todayRow.pv_kwh) ? todayRow.pv_kwh : 0,
        load: safeNumber(todayRow.load_kwh) ? todayRow.load_kwh : 0,
        grid: safeNumber(todayRow.grid_buy_kwh) ? todayRow.grid_buy_kwh : 0,
        batt: (safeNumber(todayRow.batt_charge_kwh) ? todayRow.batt_charge_kwh : 0)
            + (safeNumber(todayRow.batt_discharge_kwh) ? todayRow.batt_discharge_kwh : 0),
      };
    } else {
      totals = { pv: 0, load: 0, grid: 0, batt: 0 };
      buckets.forEach(({ point, hours }) => {
        const weight = hours / 1000;
        totals.pv += Math.max(0, safeNumber(point.pv_power_w) ? point.pv_power_w : 0) * weight;
        totals.load += Math.max(0, safeNumber(point.load_power_w) ? point.load_power_w : 0) * weight;
        // HIDEN sign convention: grid < 0 = buying from the grid.
        totals.grid += Math.max(0, -(safeNumber(point.grid_power_w) ? point.grid_power_w : 0)) * weight;
        totals.batt += Math.abs(safeNumber(point.battery_power_w) ? point.battery_power_w : 0) * weight;
      });
    }
    strip.hidden = false;
    setText("todayPv", energy(totals.pv));
    setText("todayLoad", energy(totals.load));
    setText("todayGrid", energy(totals.grid));
    setText("todayBatt", energy(totals.batt));
    const battItem = strip.querySelector(".today-item.is-batt");
    if (battItem) battItem.title = t("today.turnover_title");
  }

  // ------------------------------------------------------------------ finance & tariffs

  async function loadFinance() {
    try {
      const tz = new Date().getTimezoneOffset();
      const [finance, tariffs] = await Promise.all([
        getJson(`/api/finance?days=2&tz=${encodeURIComponent(tz)}`),
        getJson("/api/tariffs"),
      ]);
      state.finance = finance;
      state.tariffs = tariffs;
      renderFinance();
      renderTariffs();
      prefillTariffForm();
    } catch (error) { /* transient: keep the previous figures */ }
  }

  function renderFinance() {
    const rows = (state.finance && state.finance.rows) || [];
    const today = rows.find((row) => row.date === localDateKey(0)) || null;
    const yesterday = rows.find((row) => row.date === localDateKey(1)) || null;
    renderFinanceCard("Y", yesterday);
    renderFinanceCard("T", today);
    const empty = $("financeEmpty");
    if (empty) empty.hidden = Boolean(today || yesterday);
    // The day tiles prefer the same exact finance numbers.
    renderToday(state.history);
  }

  function renderFinanceCard(prefix, row) {
    const card = $(`financeCard${prefix}`);
    if (!card) return;
    if (!row) { card.hidden = true; return; }
    card.hidden = false;
    setText(`fin${prefix}Date`, dayLabel(row.date));
    const netNode = $(`fin${prefix}Net`);
    if (netNode) {
      netNode.textContent = safeNumber(row.net) ? money(row.net) : t("finance.no_tariff");
      netNode.classList.toggle("is-positive", safeNumber(row.net) && row.net >= 0);
      netNode.classList.toggle("is-negative", safeNumber(row.net) && row.net < 0);
    }
    setText(`fin${prefix}Pv`, energy(row.pv_kwh));
    setText(`fin${prefix}Savings`, safeNumber(row.pv_savings) ? money(row.pv_savings) : "-- ₽");
    setText(`fin${prefix}Load`, energy(row.load_kwh));
    setText(`fin${prefix}Buy`, energy(row.grid_buy_kwh));
    setText(`fin${prefix}BuyCost`, safeNumber(row.grid_buy_cost) ? money(row.grid_buy_cost) : "-- ₽");
    const chargeGridRow = $(`fin${prefix}ChargeGridRow`);
    if (chargeGridRow) chargeGridRow.hidden = !safeNumber(row.charge_grid_cost);
    setText(`fin${prefix}ChargeGridCost`, safeNumber(row.charge_grid_cost) ? money(row.charge_grid_cost) : "-- ₽");
    setText(`fin${prefix}Sell`, energy(row.grid_sell_kwh));
    setText(`fin${prefix}Charge`, energy(row.batt_charge_kwh));
    setText(`fin${prefix}ChargeBreak`,
      `${number(row.batt_charge_from_pv_kwh, 2)} / ${number(row.batt_charge_from_grid_kwh, 2)} kWh`);
    setText(`fin${prefix}Discharge`, energy(row.batt_discharge_kwh));
    setText(`fin${prefix}Tariff`, tariffLabel(row.tariff));
    setText(`fin${prefix}Hours`, `${number(row.hours, 1)} ${t("finance.hours_short")}`);
    const totalNode = $(`fin${prefix}LoadTotal`);
    if (totalNode) totalNode.textContent = energy(row.load_kwh);
    const totalCostNode = $(`fin${prefix}LoadTotalCost`);
    if (totalCostNode) {
      totalCostNode.textContent = safeNumber(row.tariff) && safeNumber(row.load_kwh)
        ? money(row.load_kwh * row.tariff)
        : "--";
    }
  }

  function renderTariffs() {
    const list = $("tariffList");
    if (!list) return;
    const tariffs = (state.tariffs && state.tariffs.tariffs) || [];
    // Compact "current rate" line above the collapsible editor.
    const todayKey = localDateKey(0);
    const active = tariffs.find((item) => item.valid_from <= todayKey)
      || (tariffs.length ? tariffs[tariffs.length - 1] : null);
    const priceNode = $("tariffCurrentPrice");
    const sinceNode = $("tariffCurrentSince");
    if (priceNode) priceNode.textContent = tariffLabel(active ? active.price_per_kwh : null);
    if (sinceNode) {
      sinceNode.textContent = active
        ? t("tariff.current_since").replace("{date}", active.valid_from)
        : "";
    }
    list.textContent = "";
    if (!tariffs.length) {
      const note = document.createElement("p");
      note.className = "tariff-empty";
      note.textContent = t("tariff.empty");
      list.append(note);
      return;
    }
    let activeSeen = false;
    tariffs.forEach((tariff) => {
      const row = document.createElement("div");
      row.className = "tariff-row";
      const dateCell = document.createElement("span");
      dateCell.className = "tariff-row-date";
      dateCell.textContent = tariff.valid_from;
      const priceCell = document.createElement("span");
      priceCell.className = "tariff-row-price";
      priceCell.textContent = tariffLabel(tariff.price_per_kwh);
      const noteCell = document.createElement("span");
      noteCell.className = "tariff-row-note";
      noteCell.textContent = tariff.note || "";
      noteCell.title = tariff.note || "";
      const tail = document.createElement("span");
      tail.className = "tariff-row-tail";
      if (!activeSeen && tariff.valid_from <= todayKey) {
        activeSeen = true;
        const chip = document.createElement("span");
        chip.className = "tariff-active-chip";
        chip.textContent = t("tariff.active");
        tail.append(chip);
      }
      const del = document.createElement("button");
      del.type = "button";
      del.className = "tariff-delete";
      del.textContent = "×";
      del.setAttribute("aria-label", `${t("tariff.delete_confirm")} ${tariff.valid_from}`);
      del.addEventListener("click", () => deleteTariff(tariff.id));
      tail.append(del);
      row.append(dateCell, priceCell, noteCell, tail);
      list.append(row);
    });
  }

  function prefillTariffForm() {
    const priceInput = $("tariffPrice");
    const dateInput = $("tariffValidFrom");
    if (!priceInput || !dateInput) return;
    const tariffs = (state.tariffs && state.tariffs.tariffs) || [];
    const todayKey = localDateKey(0);
    const active = tariffs.find((item) => item.valid_from <= todayKey) || null;
    if (!priceInput.value && active) priceInput.value = String(active.price_per_kwh);
    if (!dateInput.value) dateInput.value = todayKey;
  }

  function bindTariffControls() {
    const form = $("tariffForm");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = $("tariffStatus");
      const button = form.querySelector("button[type=submit]");
      const validFrom = ($("tariffValidFrom") && $("tariffValidFrom").value) || "";
      const price = Number(($("tariffPrice") && $("tariffPrice").value) || NaN);
      const note = ($("tariffNote") && $("tariffNote").value) || "";
      if (button) button.disabled = true;
      if (status) status.textContent = t("tariff.saving");
      try {
        const response = await fetch("/api/tariffs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ valid_from: validFrom, price_per_kwh: price, note }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        state.tariffs = { tariffs: data.tariffs || [] };
        renderTariffs();
        if (status) status.textContent = t("tariff.saved");
        loadFinance();
      } catch (error) {
        if (status) status.textContent = `${t("tariff.error_prefix")}${error.message}`;
      } finally {
        if (button) button.disabled = false;
        window.setTimeout(() => { const node = $("tariffStatus"); if (node) node.textContent = ""; }, 5000);
      }
    });
  }

  async function deleteTariff(id) {
    if (!window.confirm(t("tariff.delete_confirm"))) return;
    const status = $("tariffStatus");
    try {
      const response = await fetch(`/api/tariffs/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      state.tariffs = { tariffs: data.tariffs || [] };
      renderTariffs();
      if (status) status.textContent = t("tariff.deleted");
      loadFinance();
    } catch (error) {
      if (status) status.textContent = `${t("tariff.error_prefix")}${error.message}`;
    } finally {
      window.setTimeout(() => { const node = $("tariffStatus"); if (node) node.textContent = ""; }, 5000);
    }
  }

  async function loadCurrent() {
    try {
      const response = await getJson("/api/current");
      renderHealth(response.health);
      renderBattery(response.battery);
      renderMachine(response.host, response.health);
      if (response.data) renderCurrent(response.data);
    } catch (error) {
      renderHealth({ status: "offline", last_error: error.message });
    }
  }

  async function loadHistory() {
    const requestId = ++state.historyRequest;
    const url = `/api/history?range=${encodeURIComponent(state.range)}&period=${encodeURIComponent(state.period)}`;
    const exportUrl = `/api/export.csv?range=${encodeURIComponent(state.range)}&period=${encodeURIComponent(state.period)}`;
    const link = $("exportLink");
    if (link) link.href = exportUrl;
    try {
      const history = await getJson(url);
      if (requestId !== state.historyRequest) return;
      state.history = history;
      renderHistory(history);
    } catch (error) {
      if (requestId !== state.historyRequest) return;
      state.history = null;
      setText("historySummary", `${t("common.error")}: ${error.message}`);
      renderChart();
    }
  }

  function renderHistory(history) {
    const count = history.points ? history.points.length : 0;
    const suffix = history.truncated ? ` · ${t("history.shown_limit")}` : "";
    const pointWord = count === 1 ? t("history.points_one") : t("history.points_many");
    const periodLabel = t(`period.${history.period || state.period}`);
    setText("historySummary", `${count} ${pointWord} · ${periodLabel}${suffix}`);
    setText("legendLabel", t((metricMeta[state.metric] || metricMeta.load_power_w).labelKey));
    renderChart();
  }

  function renderChart() {
    const canvas = $("historyChart");
    const empty = $("chartEmpty");
    if (!canvas) return;
    const points = (state.history && state.history.points) || [];
    const axisColor = cssVar("--chart-axis", "#52616d");
    const gridColor = cssVar("--chart-grid", "rgba(173, 194, 208, .10)");
    if (!points.length) {
      if (empty) empty.classList.remove("is-hidden");
      const context = canvas.getContext("2d");
      context.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    if (empty) empty.classList.add("is-hidden");
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * ratio));
    canvas.height = Math.max(1, Math.floor(rect.height * ratio));
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const width = rect.width;
    const height = rect.height;
    const padding = { top: 18, right: 12, bottom: 31, left: 46 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const meta = metricMeta[state.metric] || metricMeta.load_power_w;
    const values = points.map((point) => point[state.metric]).filter(safeNumber);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!values.length) return;
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) { min -= 1; max += 1; }
    const pad = (max - min) * .14;
    min -= pad; max += pad;
    const x = (index) => padding.left + (points.length === 1 ? chartWidth / 2 : index / (points.length - 1) * chartWidth);
    const y = (value) => padding.top + chartHeight - ((value - min) / (max - min)) * chartHeight;
    ctx.clearRect(0, 0, width, height);
    ctx.font = "9px Cascadia Mono, Consolas, monospace";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i += 1) {
      const lineY = padding.top + chartHeight * i / 4;
      ctx.strokeStyle = gridColor;
      ctx.beginPath(); ctx.moveTo(padding.left, lineY); ctx.lineTo(width - padding.right, lineY); ctx.stroke();
      ctx.fillStyle = axisColor;
      ctx.fillText(formatAxis(max - (max - min) * i / 4, meta), 4, lineY + 3);
    }
    const valid = points.map((point, index) => safeNumber(point[state.metric]) ? [x(index), y(point[state.metric])] : null).filter(Boolean);
    if (!valid.length) return;
    const gradient = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
    gradient.addColorStop(0, hexToRgba(cssVar(meta.color, "#64748b"), .24));
    gradient.addColorStop(1, hexToRgba(cssVar(meta.color, "#64748b"), 0));
    ctx.beginPath();
    ctx.moveTo(valid[0][0], height - padding.bottom);
    valid.forEach(([pointX, pointY]) => ctx.lineTo(pointX, pointY));
    ctx.lineTo(valid[valid.length - 1][0], height - padding.bottom);
    ctx.closePath(); ctx.fillStyle = gradient; ctx.fill();
    ctx.beginPath();
    valid.forEach(([pointX, pointY], index) => index ? ctx.lineTo(pointX, pointY) : ctx.moveTo(pointX, pointY));
    ctx.strokeStyle = cssVar(meta.color, "#64748b"); ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.stroke();
    ctx.fillStyle = axisColor;
    const labels = Math.min(5, points.length);
    for (let i = 0; i < labels; i += 1) {
      const index = Math.round(i * (points.length - 1) / Math.max(1, labels - 1));
      ctx.fillText(shortTime(points[index].captured_at), x(index) - 18, height - 8);
    }
  }

  function formatAxis(value, meta) {
    if (!safeNumber(value)) return "--";
    return `${number(value, meta.decimals)} ${meta.unit}`;
  }

  function hexToRgba(hex, alpha) {
    const value = hex.replace("#", "");
    const bigint = parseInt(value, 16);
    return `rgba(${(bigint >> 16) & 255}, ${(bigint >> 8) & 255}, ${bigint & 255}, ${alpha})`;
  }

  function connectEvents() {
    if (!("EventSource" in window)) return;
    if (window.__sbEvents) { window.__sbEvents.close(); }
    const token = authToken();
    const suffix = token ? `?token=${encodeURIComponent(token)}` : "";
    const events = new EventSource(`/api/events${suffix}`);
    window.__sbEvents = events;
    events.addEventListener("snapshot", (event) => {
      try {
        const payload = JSON.parse(event.data);
        renderHealth(payload.health);
        renderBattery(payload.battery);
        renderMachine(payload.host, payload.health);
        renderCurrent(payload.data);
        window.clearTimeout(state.historyTimer);
        state.historyTimer = window.setTimeout(loadHistory, 1000);
        window.clearTimeout(state.todayTimer);
        state.todayTimer = window.setTimeout(loadToday, 1000);
        window.clearTimeout(state.financeTimer);
        state.financeTimer = window.setTimeout(loadFinance, 1500);
      } catch (error) { console.warn("Invalid snapshot event", error); }
    });
    events.addEventListener("health", (event) => {
      try { renderHealth(JSON.parse(event.data).health); } catch (error) { console.warn("Invalid health event", error); }
    });
    events.onerror = () => {
      if (!state.health || state.health.status === "online") renderHealth({ status: "offline", last_error: "SSE connection lost" });
    };
  }

  function bindControls() {
    document.querySelectorAll("[data-lang]").forEach((button) => button.addEventListener("click", () => {
      state.language = normalizeLang(button.dataset.lang);
      try { localStorage.setItem("hiden-control-language", state.language); } catch (error) { /* storage can be unavailable */ }
      applyLanguage();
    }));
    const themeToggle = $("themeToggle");
    if (themeToggle) themeToggle.addEventListener("click", () => {
      const next = state.theme === "light" ? "dark" : "light";
      try { localStorage.setItem("hiden-control-theme", next); } catch (error) { /* storage can be unavailable */ }
      applyTheme(next);
    });
    const alarmBadge = $("alarmBadge");
    if (alarmBadge) alarmBadge.addEventListener("click", () => {
      const target = $("diagnosticBadge");
      if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    const defaultPeriods = { "24h": "30m", "7d": "day", "30d": "day", "1y": "month", all: "month" };
    document.querySelectorAll("[data-range]").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll("[data-range]").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      state.range = button.dataset.range;
      state.period = defaultPeriods[state.range] || state.period;
      $("periodSelect").value = state.period;
      loadHistory();
    }));
    $("metricSelect").addEventListener("change", (event) => {
      state.metric = event.target.value;
      renderHistory(state.history || { points: [], period: state.period });
    });
    $("periodSelect").addEventListener("change", (event) => { state.period = event.target.value; loadHistory(); });
    $("refreshButton").addEventListener("click", () => { loadCurrent(); loadHistory(); loadToday(); loadFinance(); });
    bindTariffControls();
    window.addEventListener("resize", () => renderChart());
  }

  async function boot() {
    applyTheme(state.theme);
    applyLanguage();
    bindControls();
    await ensureAuth();
    await Promise.all([loadCurrent(), loadHistory(), loadToday(), loadFinance()]);
    connectEvents();
  }

  boot();
})();
