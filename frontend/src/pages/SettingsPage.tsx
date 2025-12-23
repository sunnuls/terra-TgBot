import React from "react";
import { PixelPanel } from "../ui/PixelPanel";

export function SettingsPage() {
  return (
    <div className="container">
      <div className="pxUI">
        <PixelPanel title="Настройки">
          Экран настроек (заглушка). Здесь будут ФИО / телефон.
        </PixelPanel>
      </div>
    </div>
  );
}
