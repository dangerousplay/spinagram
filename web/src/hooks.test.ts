// Section routes (spec: .specs/features/diagram-catalog/spec.md, META-27). Run: `bun test`.
import { describe, expect, test } from "bun:test";
import { href, parse, type Route } from "./hooks";

describe("META-27 default route", () => {
  test("no hash lands on the Diagrams page", () => {
    for (const hash of ["", "#", "#/", "#/d", "#/d/"]) expect(parse(hash)).toEqual({ kind: "diagrams" });
  });
  test("an unknown hash lands on the Diagrams page", () => {
    expect(parse("#/zzz/thing")).toEqual({ kind: "diagrams" });
  });
});

describe("section routes", () => {
  test("Themes and Icon packs have index pages", () => {
    expect(parse("#/t")).toEqual({ kind: "themes" });
    expect(parse("#/p/")).toEqual({ kind: "packs" });
  });
  test("every route round-trips through href", () => {
    const routes: Route[] = [
      { kind: "diagrams" },
      { kind: "themes" },
      { kind: "packs" },
      { kind: "diagram", key: "sub dir/aws.py#AWS01" },
      { kind: "theme", ref: "default" },
      { kind: "pack", name: "k8s" },
    ];
    for (const r of routes) expect(parse(href(r))).toEqual(r);
  });
});
