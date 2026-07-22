import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
} 


export const isIframe = window.self !== window.top;

// Backend timestamps should always come as timezone-aware ISO strings
// (ending in Z or a +/-hh:mm offset). This is a safety net for any that
// don't (e.g. rows written before the API started returning offsets):
// without it, `new Date(iso)` treats a naive string as local time instead
// of UTC, which silently skews every displayed date/time by the user's
// UTC offset.
export function toUtcDate(iso) {
  if (!iso) return null;
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasTz ? iso : `${iso}Z`);
}
