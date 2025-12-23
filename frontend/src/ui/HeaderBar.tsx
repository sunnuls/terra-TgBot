import React from "react";
import { PixelIcon } from "./PixelIcon";

export function HeaderBar({
  fullName,
  role,
  balance,
}: {
  fullName: string;
  role: string;
  balance: number;
}) {
  const letter = (fullName || "T").trim().slice(0, 1).toUpperCase() || "T";

  return (
    <header className="pxHeader">
      <div className="pxHeader__left">
        <div className="pxAvatar" aria-hidden="true">
          <div className="pxAvatar__inner">{letter}</div>
        </div>
        <div className="pxHeader__meta">
          <div className="pxHeader__name">{fullName || "—"}</div>
          <div className="pxHeader__role">{role || "—"}</div>
        </div>
      </div>

      <div className="pxHeader__right">
        <div className="pxBalance">
          <PixelIcon name="coin" />
          <span className="pxBalance__value">{balance}</span>
        </div>
      </div>
    </header>
  );
}
