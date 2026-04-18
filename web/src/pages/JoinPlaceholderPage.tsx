import React from "react";
import { useParams } from "react-router-dom";

/** Публичная страница по пригласительной ссылке (для мобильного приложения / будущей регистрации). */
export default function JoinPlaceholderPage() {
  const { token } = useParams<{ token: string }>();
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-700 to-primary-900 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md text-center">
        <div className="text-4xl mb-3">🌾</div>
        <h1 className="text-xl font-bold text-primary-800 mb-2">TerraApp</h1>
        <p className="text-gray-600 text-sm mb-4">
          Пригласительная ссылка активна. Откройте приложение TerraApp на телефоне или войдите через веб-панель администратора.
        </p>
        <p className="text-xs text-gray-400 break-all font-mono">token: {token}</p>
      </div>
    </div>
  );
}
