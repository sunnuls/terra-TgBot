import React from "react";

export function PixelPanel({
  title,
  children,
  className,
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`pxPanel ${className || ""}`.trim()}>
      {title ? <div className="pxPanel__title">{title}</div> : null}
      <div className="pxPanel__body">{children}</div>
    </section>
  );
}
