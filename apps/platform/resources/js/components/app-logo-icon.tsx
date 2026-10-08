import type { SVGAttributes } from "react";

// Reuse the locked KMJ TECHNO mark instead of the starter-kit template icon.
// Keep an SVG wrapper so existing icon-sized consumers retain their layout.
export default function AppLogoIcon(props: SVGAttributes<SVGElement>) {
  return (
    <svg
      viewBox="0 0 40 42"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="KMJ TECHNO"
      {...props}
    >
      <image
        href="/assets/brand/kmj-mark.webp"
        x="0"
        y="0"
        width="40"
        height="42"
        preserveAspectRatio="xMidYMid meet"
      />
    </svg>
  );
}
