import React from "react";

export function PixelButton({
  title,
  subtitle,
  left,
  onClick,
  disabled,
}: {
  title: string;
  subtitle?: string;
  left?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button className="pxButton" type="button" onClick={onClick} disabled={disabled}>
      <div className="pxButton__left">{left}</div>
      <div className="pxButton__text">
        <div className="pxButton__title">{title}</div>
        {subtitle ? <div className="pxButton__subtitle">{subtitle}</div> : null}
      </div>
      <div className="pxButton__right">→</div>
    </button>
  );
}
