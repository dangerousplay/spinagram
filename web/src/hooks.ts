import { useCallback, useEffect, useRef, useState } from "react";
import type { UiEvent } from "./api";

export type Route =
  | { kind: "diagrams" }
  | { kind: "themes" }
  | { kind: "packs" }
  | { kind: "diagram"; key: string }
  | { kind: "theme"; ref: string }
  | { kind: "pack"; name: string };

/** A hash as a route; an empty or unknown hash is the Diagrams page. */
export function parse(hash: string): Route {
  const [, kind, ...rest] = hash.replace(/^#/, "").split("/");
  const value = decodeURIComponent(rest.join("/"));
  if (kind === "t") return value ? { kind: "theme", ref: value } : { kind: "themes" };
  if (kind === "p") return value ? { kind: "pack", name: value } : { kind: "packs" };
  if (kind === "d" && value) return { kind: "diagram", key: value };
  return { kind: "diagrams" };
}

export function href(route: Route): string {
  switch (route.kind) {
    case "diagram":
      return `#/d/${encodeURIComponent(route.key)}`;
    case "theme":
      return `#/t/${encodeURIComponent(route.ref)}`;
    case "pack":
      return `#/p/${encodeURIComponent(route.name)}`;
    case "themes":
      return "#/t";
    case "packs":
      return "#/p";
    default:
      return "#/";
  }
}

let leaveGuard: (() => boolean) | null = null;

/** While set, every route change asks it first; ``false`` keeps the current page (unsaved code edits). */
export function setLeaveGuard(guard: (() => boolean) | null): void {
  leaveGuard = guard;
}

/** Ask the leave guard (if any) whether the current page may be left. */
export function confirmLeave(): boolean {
  return leaveGuard ? leaveGuard() : true;
}

/** Hash routing: `#/` diagrams, `#/d/<key>`, `#/t` and `#/t/<ref>`, `#/p` and `#/p/<name>`. */
export function useRoute(): [Route, (r: Route, replace?: boolean) => void] {
  const [route, setRoute] = useState(() => parse(location.hash));
  const current = useRef(route);
  current.current = route;
  useEffect(() => {
    const on = () => {
      const next = parse(location.hash);
      if (href(next) === href(current.current)) return;
      if (!confirmLeave()) {
        history.replaceState(null, "", href(current.current)); // stay: the address bar shows this page again
        return;
      }
      setRoute(next);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback((r: Route, replace = false) => {
    if (href(r) !== href(current.current) && !confirmLeave()) return;
    if (replace) history.replaceState(null, "", href(r));
    else location.hash = href(r);
    setRoute(r);
  }, []);
  return [route, go];
}

/** One EventSource for the app; the browser reconnects on its own and the server greets with `hello`. */
export function useEvents(onEvent: (e: UiEvent) => void): boolean {
  const [connected, setConnected] = useState(false);
  const handler = useRef(onEvent);
  handler.current = onEvent;
  useEffect(() => {
    const es = new EventSource("api/events");
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (m) => {
      try {
        handler.current(JSON.parse(m.data) as UiEvent);
      } catch {
        /* ignore malformed */
      }
    };
    return () => es.close();
  }, []);
  return connected;
}

export type View = { scale: number; x: number; y: number };

const MIN = 0.1;
const MAX = 8;
const clamp = (v: number) => Math.min(MAX, Math.max(MIN, v));

/** Wheel zoom around the pointer, drag to pan, `fit` and `actual` (100 %). */
export function usePanZoom(size: { w: number; h: number } | null) {
  const ref = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<View>({ scale: 1, x: 0, y: 0 });

  const fit = useCallback(() => {
    const el = ref.current;
    if (!el || !size) return;
    const pad = 24;
    const s = clamp(Math.min((el.clientWidth - pad * 2) / size.w, (el.clientHeight - pad * 2) / size.h));
    setView({ scale: s, x: (el.clientWidth - size.w * s) / 2, y: (el.clientHeight - size.h * s) / 2 });
  }, [size]);

  const actual = useCallback(() => {
    const el = ref.current;
    if (!el || !size) return;
    setView({ scale: 1, x: (el.clientWidth - size.w) / 2, y: (el.clientHeight - size.h) / 2 });
  }, [size]);

  const zoomBy = useCallback((factor: number, px?: number, py?: number) => {
    const el = ref.current;
    if (!el) return;
    const cx = px ?? el.clientWidth / 2;
    const cy = py ?? el.clientHeight / 2;
    setView((v) => {
      const s = clamp(v.scale * factor);
      const k = s / v.scale;
      return { scale: s, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k };
    });
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomBy(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
    };
    let drag: { x: number; y: number } | null = null;
    const down = (e: PointerEvent) => {
      if (e.button !== 0) return;
      drag = { x: e.clientX, y: e.clientY };
      el.setPointerCapture(e.pointerId);
      el.style.cursor = "grabbing";
    };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      drag = { x: e.clientX, y: e.clientY };
      setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }));
    };
    const up = () => {
      drag = null;
      el.style.cursor = "";
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("pointerdown", down);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("pointerdown", down);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("pointercancel", up);
    };
  }, [zoomBy]);

  return { ref, view, fit, actual, zoomBy };
}

/** Keyboard shortcut, ignored while typing in a field. */
export function useKey(key: string, fn: () => void) {
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey || t.closest("input, textarea, select")) return;
      if (e.key === key) {
        e.preventDefault();
        fn();
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [key, fn]);
}
