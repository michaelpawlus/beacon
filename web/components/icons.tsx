"use client";

import type { ReactNode } from "react";
import type { IconProps } from "./primitives";

type IconFactory = (props?: IconProps) => ReactNode;

function makeIcon(children: ReactNode, viewBox = "0 0 16 16"): IconFactory {
  const Comp = ({ size = 14, color = "currentColor", strokeWidth = 1.5 }: IconProps = {}) => (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
  return Comp;
}

const p = (d: string) => makeIcon(<path d={d} />);

export const icons = {
  dashboard: p("M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2zM9 9h5v5H9z"),
  companies: p("M2 14V5l5-3 5 3v9M6 14V9h2v5M2 14h12"),
  jobs: p("M2 5h12v8H2zM5 5V3h6v2M2 8h12"),
  apps: p("M3 2h10v12H3zM6 5h4M6 8h4M6 11h2"),
  content: p("M3 2h7l3 3v9H3zM10 2v3h3"),
  settings: p(
    "M8 2v2M8 12v2M14 8h-2M4 8H2M12.2 3.8l-1.4 1.4M5.2 10.8l-1.4 1.4M12.2 12.2l-1.4-1.4M5.2 5.2L3.8 3.8",
  ),
  search: p("M7 12a5 5 0 100-10 5 5 0 000 10zM14 14l-3.5-3.5"),
  bolt: p("M9 1L2 9h4l-1 6 7-8H8z"),
  dot: makeIcon(<circle cx="8" cy="8" r="3" />),
  chevDown: p("M4 6l4 4 4-4"),
  chevRight: p("M6 4l4 4-4 4"),
  plus: p("M8 3v10M3 8h10"),
  star: p("M8 2l1.8 3.7 4 .6-2.9 2.8.7 4-3.6-1.9-3.6 1.9.7-4L2 6.3l4-.6z"),
  clock: p("M8 4v4l2.5 2.5M8 14A6 6 0 108 2a6 6 0 000 12z"),
  external: p("M6 3H3v10h10V10M9 3h4v4M13 3L8 8"),
  sparkle: p("M8 2v4M8 10v4M2 8h4M10 8h4M4 4l2 2M10 10l2 2M4 12l2-2M10 6l2-2"),
  arrowUp: p("M8 13V3M4 7l4-4 4 4"),
  arrowRight: p("M3 8h10M9 4l4 4-4 4"),
  check: p("M3 8l3 3 7-7"),
  bell: p("M4 11V7a4 4 0 118 0v4l1.5 2h-11zM7 14a1 1 0 002 0"),
  calendar: p("M3 4h10v10H3zM3 7h10M6 2v3M10 2v3"),
  trending: p("M2 11l4-4 3 3 5-5M10 5h3v3"),
  terminal: p("M3 5l3 3-3 3M7 11h6M2 2h12v12H2z"),
  filter: p("M2 4h12M4 8h8M6 12h4"),
  sortDesc: p("M3 4h10M3 8h7M3 12h4"),
  link: p("M7 9l2-2M6 4l1-1a2.8 2.8 0 014 4l-1 1M10 12l-1 1a2.8 2.8 0 01-4-4l1-1"),
  users: p(
    "M11 13v-1a3 3 0 00-3-3H5a3 3 0 00-3 3v1M6.5 7a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM14 13v-1a3 3 0 00-2-2.8M10.5 2.2a2.5 2.5 0 010 4.6",
  ),
  dollar: p("M8 2v12M11 5H6.5a1.5 1.5 0 000 3h3a1.5 1.5 0 010 3H5"),
  mapPin: p("M8 14s5-4.5 5-8a5 5 0 00-10 0c0 3.5 5 8 5 8zM8 8a1.5 1.5 0 100-3 1.5 1.5 0 000 3z"),
} as const;

export type IconName = keyof typeof icons;
