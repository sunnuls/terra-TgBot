export function getTelegramWebApp() {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  return tg;
}

export function getInitData(): string {
  const tg = getTelegramWebApp();
  return tg ? tg.initData || "" : "";
}

export function initTelegramUi() {
  const tg = getTelegramWebApp();
  try {
    if (tg) {
      tg.ready();
      tg.expand();
    }
  } catch {
    // ignore
  }
}
