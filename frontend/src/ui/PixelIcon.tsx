import React from "react";

export type PixelIconName = "otd" | "stats" | "settings" | "brig" | "admin" | "coin";

function IconSvg({ name }: { name: PixelIconName }) {
  // Tiny pixel-ish icons via SVG with crispEdges.
  // Each icon is a 16x16 grid.
  const common = {
    viewBox: "0 0 16 16",
    shapeRendering: "crispEdges" as const,
  };

  const fill = "currentColor";

  if (name === "coin") {
    return (
      <svg {...common}>
        <rect x="4" y="3" width="8" height="10" fill={fill} opacity="0.22" />
        <rect x="5" y="4" width="6" height="8" fill={fill} opacity="0.35" />
        <rect x="6" y="5" width="4" height="6" fill={fill} />
      </svg>
    );
  }

  if (name === "stats") {
    return (
      <svg {...common}>
        <rect x="3" y="9" width="2" height="4" fill={fill} />
        <rect x="7" y="6" width="2" height="7" fill={fill} />
        <rect x="11" y="4" width="2" height="9" fill={fill} />
        <rect x="2" y="13" width="12" height="1" fill={fill} opacity="0.5" />
      </svg>
    );
  }

  if (name === "settings") {
    return (
      <svg {...common}>
        <rect x="6" y="2" width="4" height="2" fill={fill} />
        <rect x="2" y="6" width="2" height="4" fill={fill} />
        <rect x="12" y="6" width="2" height="4" fill={fill} />
        <rect x="6" y="12" width="4" height="2" fill={fill} />
        <rect x="5" y="5" width="6" height="6" fill={fill} opacity="0.25" />
        <rect x="7" y="7" width="2" height="2" fill={fill} />
      </svg>
    );
  }

  if (name === "admin") {
    return (
      <svg {...common}>
        <rect x="4" y="2" width="8" height="3" fill={fill} />
        <rect x="5" y="5" width="6" height="2" fill={fill} opacity="0.6" />
        <rect x="3" y="7" width="10" height="7" fill={fill} opacity="0.25" />
        <rect x="6" y="9" width="4" height="5" fill={fill} />
      </svg>
    );
  }

  if (name === "brig") {
    return (
      <svg {...common}>
        <rect x="6" y="2" width="4" height="4" fill={fill} />
        <rect x="4" y="6" width="8" height="4" fill={fill} opacity="0.3" />
        <rect x="3" y="10" width="10" height="4" fill={fill} opacity="0.15" />
        <rect x="6" y="10" width="4" height="4" fill={fill} />
      </svg>
    );
  }

  // default: "otd"
  return (
    <svg {...common}>
      <rect x="3" y="2" width="10" height="12" fill={fill} opacity="0.25" />
      <rect x="5" y="4" width="6" height="1" fill={fill} />
      <rect x="5" y="7" width="6" height="1" fill={fill} opacity="0.8" />
      <rect x="5" y="10" width="4" height="1" fill={fill} opacity="0.6" />
    </svg>
  );
}

export function PixelIcon({ name, className }: { name: PixelIconName; className?: string }) {
  return (
    <span className={`pxIcon ${className || ""}`.trim()} aria-hidden="true">
      <IconSvg name={name} />
    </span>
  );
}
