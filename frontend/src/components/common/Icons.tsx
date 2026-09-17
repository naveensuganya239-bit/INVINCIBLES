import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;
const base = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export const IconOrbit = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <circle cx="12" cy="12" r="3.2" />
    <ellipse cx="12" cy="12" rx="10" ry="4.2" transform="rotate(-20 12 12)" />
  </svg>
);
export const IconLayers = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M12 3 3 8l9 5 9-5-9-5Z" />
    <path d="M3 13.5 12 18.5 21 13.5" />
    <path d="M3 18 12 23 21 18" />
  </svg>
);
export const IconTarget = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <circle cx="12" cy="12" r="4" />
    <circle cx="12" cy="12" r="0.6" fill="currentColor" />
  </svg>
);
export const IconWave = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M2 12c2 0 2-6 4-6s2 12 4 12 2-12 4-12 2 6 4 6 2-4 4-4" />
  </svg>
);
export const IconLink = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <circle cx="6" cy="6" r="2.4" />
    <circle cx="18" cy="18" r="2.4" />
    <path d="M8 8l8 8" strokeDasharray="2.5 2.5" />
  </svg>
);
export const IconChart = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M4 20V10M11 20V4M18 20v-7" />
    <path d="M2 20h20" />
  </svg>
);
export const IconGrid = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <rect x="3" y="3" width="7.5" height="7.5" rx="1" />
    <rect x="13.5" y="3" width="7.5" height="7.5" rx="1" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="1" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1" />
  </svg>
);
export const IconSparkle = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
    <path d="M12 8a4 4 0 0 0 4 4 4 4 0 0 0-4 4 4 4 0 0 0-4-4 4 4 0 0 0 4-4Z" />
  </svg>
);
export const IconDoc = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M6 2.5h9l4 4V21a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1Z" />
    <path d="M14.5 2.5V7h4" />
    <path d="M8 12h8M8 15.5h8M8 8.5h3" />
  </svg>
);
export const IconHistory = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M3 12a9 9 0 1 0 3-6.7" />
    <path d="M3 4v4h4" />
    <path d="M12 7v5l3.5 2" />
  </svg>
);
export const IconChevronLeft = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M15 5 8 12l7 7" /></svg>
);
export const IconChevronRight = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M9 5l7 7-7 7" /></svg>
);
export const IconPlay = (p: IconProps) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...p}><path d="M8 5.5v13l11-6.5-11-6.5Z" /></svg>
);
export const IconDownload = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M12 3v12" />
    <path d="M7 11l5 5 5-5" />
    <path d="M4 19.5h16" />
  </svg>
);
export const IconRefresh = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M3.5 12a8.5 8.5 0 0 1 14.6-5.9L20.5 8.5" />
    <path d="M20.5 4v4.5H16" />
    <path d="M20.5 12a8.5 8.5 0 0 1-14.6 5.9L3.5 15.5" />
    <path d="M3.5 20v-4.5H8" />
  </svg>
);
export const IconArrowRight = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 12h15M13 6l7 6-7 6" /></svg>
);
export const IconCheck = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}><path d="M4 12.5l5.5 5.5L20 6" /></svg>
);
export const IconAlert = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M12 3 2 20h20L12 3Z" />
    <path d="M12 10v4" />
    <circle cx="12" cy="17" r="0.6" fill="currentColor" />
  </svg>
);
export const IconLock = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <rect x="5" y="10.5" width="14" height="10" rx="1.5" />
    <path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" />
  </svg>
);
export const IconSlider = (p: IconProps) => (
  <svg viewBox="0 0 24 24" {...base} {...p}>
    <path d="M4 7h9M17 7h3M4 17h3M9 17h11" />
    <circle cx="15" cy="7" r="2" />
    <circle cx="7" cy="17" r="2" />
  </svg>
);
