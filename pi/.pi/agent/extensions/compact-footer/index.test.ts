import { describe, expect, test } from "bun:test";
import { stripTerminalSequences, visibleWidth } from "@earendil-works/pi-tui";
import compactFooter, { align, clean, formatTokens, shortCwd, splitStatuses, usageTotals } from "./index";

const plain = stripTerminalSequences;

function fixture(mode = "tui") {
  let factory: any;
  let handler: any;
  let command: any;
  let renders = 0;
  let unsubscribed = false;
  let branchChanged: () => void = () => {};
  const statuses = new Map<string, string>();
  const ctx: any = {
    mode,
    cwd: "/dev/projects/example",
    model: { id: "test-model", provider: "test-provider", reasoning: true, contextWindow: 262144 },
    sessionManager: {
      getLeafId: () => "leaf",
      getSessionId: () => "session",
      getEntries: () => [],
      getSessionName: () => "demo",
    },
    getContextUsage: () => ({ percent: 44.6, contextWindow: 262144 }),
    ui: { setFooter: (f: any) => { factory = f; }, notify: () => {} },
  };
  compactFooter({
    on: (_name: string, fn: any) => { handler = fn; },
    registerCommand: (_name: string, spec: any) => { command = spec.handler; },
    getThinkingLevel: () => "high",
  } as any);
  handler({}, ctx);
  const component = factory?.(
    { requestRender: () => renders++ },
    { fg: (color: string, value: string) => `\x1b[${color === "error" ? 31 : color === "warning" ? 33 : 90}m${value}\x1b[39m` },
    {
      getGitBranch: () => "main",
      getExtensionStatuses: () => statuses,
      getAvailableProviderCount: () => 2,
      onBranchChange: (fn: () => void) => {
        branchChanged = fn;
        return () => { unsubscribed = true; };
      },
    },
  );
  return { ctx, statuses, component, command: (args: string) => command(args, ctx), branchChanged: () => branchChanged(), renders: () => renders, unsubscribed: () => unsubscribed };
}

describe("compact footer", () => {
  test("one metadata row, no outer padding, model ends at right edge", () => {
    const { component } = fixture();
    const lines = component.render(120);
    expect(lines).toHaveLength(1);
    const line = plain(lines[0]);
    expect(line.startsWith("/dev/projects/example (main) [demo] $0.00 • 44.6%/262k")).toBe(true);
    expect(line.endsWith("test-model • high")).toBe(true);
    expect(visibleWidth(lines[0])).toBe(120);
  });

  test("toggle, explicit on/off, invalid argument, and stats statuses", async () => {
    const f = fixture();
    f.statuses.set("mcp-adapter", "🔌 2 / 3 servers");
    f.statuses.set("plan", "plan active");
    await f.command("");
    expect(plain(f.component.render(120)[1])).toBe("↑0 ↓0 • (test-provider) • 🔌 2/3 • plan active");
    await f.command("on");
    expect(f.component.render(120)).toHaveLength(2);
    await f.command("invalid");
    expect(f.component.render(120)).toHaveLength(2);
    await f.command("off");
    expect(f.component.render(120)).toHaveLength(1);
    expect(f.renders()).toBe(3);
  });

  test("below-footer rows are always shown, sorted, sanitized, clipped, and flush left", () => {
    const f = fixture();
    f.statuses.set("below-footer:z", "second\nthird");
    f.statuses.set("below-footer:a", "\x1b[31mfirst\x1b[0m\x1b[2J");
    expect(f.component.render(100).slice(1).map(plain)).toEqual(["first", "second", "third"]);
    for (const line of f.component.render(3)) expect(visibleWidth(line)).toBeLessThanOrEqual(3);
  });

  test("all narrow widths fit, and the model survives whenever physically possible", () => {
    const f = fixture();
    f.ctx.cwd = "/very/long/界界界/project/path";
    for (let width = 1; width <= 150; width++) {
      const line = f.component.render(width)[0];
      expect(visibleWidth(line)).toBeLessThanOrEqual(width);
      if (width >= visibleWidth("test-model • high")) expect(plain(line).endsWith("test-model • high")).toBe(true);
    }
    expect(f.component.render(0)).toEqual([]);
  });

  test("context thresholds and unknown usage", () => {
    const f = fixture();
    f.ctx.getContextUsage = () => ({ percent: 60, contextWindow: 262144 });
    expect(f.component.render(120)[0]).toContain("\x1b[33m60.0%/262k");
    f.ctx.getContextUsage = () => ({ percent: 80, contextWindow: 262144 });
    expect(f.component.render(120)[0]).toContain("\x1b[31m80.0%/262k");
    f.ctx.getContextUsage = () => ({ percent: null, contextWindow: 262144 });
    expect(plain(f.component.render(120)[0])).toContain("?/262k");
  });

  test("branch subscription requests renders and is disposed", () => {
    const f = fixture();
    f.branchChanged();
    expect(f.renders()).toBe(1);
    f.component.dispose();
    expect(f.unsubscribed()).toBe(true);
  });

  test("does not install terminal UI in print/RPC modes", () => {
    expect(fixture("print").component).toBeUndefined();
    expect(fixture("rpc").component).toBeUndefined();
  });

  test("totals include assistant, tool, compaction, and independent usage; cache rate is latest prompt", () => {
    const usage = { input: 10, output: 5, cacheRead: 90, cacheWrite: 0, cost: { total: 0.1 } };
    const entries: any = [
      { type: "message", message: { role: "assistant", usage } },
      { type: "message", message: { role: "toolResult", usage } },
      { type: "compaction", usage },
      { type: "branch_summary", usage },
      { type: "usage", usage },
    ];
    const result = usageTotals(entries);
    expect(result.input).toBe(50);
    expect(result.output).toBe(25);
    expect(result.cost).toBeCloseTo(0.5);
    expect(result.cacheHit).toBe(90);
  });

  test("helpers handle paths, controls, badges, and wide text", () => {
    expect(shortCwd("/home/me/project", "/home/me")).toBe("~/project");
    expect(shortCwd("/home/me-other/project", "/home/me")).toBe("/home/me-other/project");
    expect(formatTokens(228000)).toBe("228k");
    expect(clean("a\x1b]0;title\x07\tb\n\x00c")).toBe("a b c");
    expect(visibleWidth(align("界界界", "model", 10))).toBe(10);
    expect(splitStatuses(new Map([["active-agent", "reviewer"]])).agent).toBe("reviewer");
  });
});
