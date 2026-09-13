import { useId } from "react";

/**
 * The Komalingo mark: one speech bubble cut by a manga panel gutter. The
 * left half takes `currentColor`, so it follows the theme's foreground; the
 * right half is always the brand vermilion. Same geometry as
 * brand/komalingo-mark.svg (512 grid). The mask and clip ids come from
 * useId, so two marks on one page never share them.
 */
export function BrandMark({ size = 24 }: { size?: number }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 512 512" aria-hidden="true">
      <defs>
        <mask id={`${id}-g`} maskUnits="userSpaceOnUse" x="0" y="0" width="512" height="512">
          <rect width="512" height="512" fill="#fff" />
          <line x1="306" y1="-10" x2="206" y2="522" stroke="#000" strokeWidth="30" />
        </mask>
        <clipPath id={`${id}-l`}>
          <polygon points="0,0 304,0 208,512 0,512" />
        </clipPath>
        <clipPath id={`${id}-r`}>
          <polygon points="304,0 512,0 512,512 208,512" />
        </clipPath>
      </defs>
      <g mask={`url(#${id}-g)`}>
        <g clipPath={`url(#${id}-l)`} fill="currentColor">
          <ellipse cx="262" cy="232" rx="206" ry="176" />
          <path d="M128 350 L78 474 L240 396 Z" />
        </g>
        <g clipPath={`url(#${id}-r)`} fill="#E8452C">
          <ellipse cx="262" cy="232" rx="206" ry="176" />
          <path d="M128 350 L78 474 L240 396 Z" />
        </g>
      </g>
    </svg>
  );
}
