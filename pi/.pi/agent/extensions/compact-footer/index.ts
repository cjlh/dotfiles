import { homedir } from "node:os";
import { basename, relative, isAbsolute, sep } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { sliceByColumn, stripTerminalSequences, truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

export const BELOW_FOOTER_PREFIX = "below-footer:";

export function clean(text: string): string {
  return stripTerminalSequences(text).replace(/[\x00-\x1f\x7f-\x9f]/g, " ").replace(/ +/g, " ").trim();
}

export function formatTokens(count: number): string {
  if (count < 1000) return String(count);
  if (count < 10000) return `${(count / 1000).toFixed(1)}k`;
  if (count < 1_000_000) return `${Math.round(count / 1000)}k`;
  return `${(count / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
}

export function shortCwd(cwd: string, home: string): string {
  const rel = relative(home, cwd);
  if (!rel) return "~";
  return rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel) ? `~${sep}${rel}` : cwd;
}

/** Reserve the right side first. No outer padding, even at very narrow widths. */
export function align(left: string, right: string, width: number): string {
  if (width <= 0) return "";
  const rightWidth = visibleWidth(right);
  if (rightWidth >= width) {
    // Only physically impossible widths clip the model, retaining its final cell.
    return sliceByColumn(right, rightWidth - width, width);
  }
  const available = width - rightWidth - 1;
  const clipped = available > 0 ? truncateToWidth(left, available, "…") : "";
  return clipped + " ".repeat(width - visibleWidth(clipped) - rightWidth) + right;
}

export function splitStatuses(statuses: ReadonlyMap<string, string>) {
  const ordinary: string[] = [];
  const below: string[] = [];
  let agent = "";
  let mcp = "";
  for (const [key, value] of [...statuses].sort(([a], [b]) => a.localeCompare(b))) {
    if (key.startsWith(BELOW_FOOTER_PREFIX)) {
      below.push(...value.split(/\r?\n/).map(clean));
      continue;
    }
    const text = clean(value);
    if (!text) continue;
    if (["active-agent", "active_agent", "agent"].includes(key)) {
      agent = text;
    } else {
      const badge = text.match(/🔌\s*(\d+(?:\s*\/\s*\d+)?)/u);
      if (badge) mcp = `🔌 ${badge[1].replace(/\s/g, "")}`;
      else ordinary.push(text);
    }
  }
  return { ordinary, below, agent, mcp };
}

/** Include all recorded usage, including compaction and nested-tool calls. */
export function usageTotals(entries: ReturnType<ExtensionContext["sessionManager"]["getEntries"]>) {
  let input = 0, output = 0, cost = 0;
  let cacheHit: number | undefined;
  for (const entry of entries) {
    const usage = entry.type === "message"
      ? (entry.message.role === "assistant" || entry.message.role === "toolResult" ? entry.message.usage : undefined)
      : (entry.type === "usage" || entry.type === "compaction" || entry.type === "branch_summary" ? entry.usage : undefined);
    if (!usage) continue;
    input += usage.input ?? 0;
    output += usage.output ?? 0;
    cost += usage.cost?.total ?? 0;
    if (entry.type === "message" && entry.message.role === "assistant") {
      const prompt = usage.input + usage.cacheRead + usage.cacheWrite;
      cacheHit = prompt > 0 ? usage.cacheRead / prompt * 100 : undefined;
    }
  }
  return { input, output, cost, cacheHit };
}

export default function compactFooter(pi: ExtensionAPI) {
  let moreStats = false;
  let requestRender: (() => void) | undefined;

  pi.registerCommand("toggle-footer", {
    description: "Toggle compact footer token stats (on|off|toggle)",
    handler: async (args, ctx) => {
      const action = args.trim().toLowerCase() || "toggle";
      if (!["on", "off", "toggle"].includes(action)) {
        ctx.ui.notify("Usage: /toggle-footer [on|off|toggle]", "warning");
        return;
      }
      moreStats = action === "toggle" ? !moreStats : action === "on";
      requestRender?.();
    },
  });

  pi.on("session_start", (_event, ctx) => {
    if (ctx.mode !== "tui") return;
    moreStats = false;
    ctx.ui.setFooter((tui, theme, footerData) => {
      const render = () => tui.requestRender();
      requestRender = render;
      const unsubscribe = footerData.onBranchChange(render);
      let lastLeaf: string | null | undefined;
      let lastSession: string | undefined;
      let totals = usageTotals([]);
      return {
        dispose() {
          unsubscribe();
          if (requestRender === render) requestRender = undefined;
        },
        invalidate() {},
        render(width: number): string[] {
          if (width <= 0) return [];
          const manager = ctx.sessionManager;
          const leaf = manager.getLeafId();
          const session = manager.getSessionId();
          if (leaf !== lastLeaf || session !== lastSession) {
            totals = usageTotals(manager.getEntries());
            lastLeaf = leaf;
            lastSession = session;
          }
          const dim = (text: string) => theme.fg("dim", text);
          const statuses = splitStatuses(footerData.getExtensionStatuses());
          const usage = ctx.getContextUsage();
          const percent = usage?.percent;
          const window = usage?.contextWindow ?? ctx.model?.contextWindow;
          const context = `${percent == null ? "?" : `${percent.toFixed(1)}%`}/${window ? formatTokens(window) : "?"}`;
          const contextText = theme.fg(percent != null && percent >= 80 ? "error" : percent != null && percent >= 60 ? "warning" : "dim", context);
          const branch = footerData.getGitBranch();
          const name = manager.getSessionName();
          const suffix = `${branch ? ` (${clean(branch)})` : ""}${name ? ` [${clean(name)}]` : ""}`;
          const model = clean(ctx.model?.id ?? "no-model");
          const thinking = ctx.model?.reasoning ? ` • ${pi.getThinkingLevel()}` : "";
          const right = (agent: boolean) => dim(`${model}${agent && statuses.agent ? ` • ${statuses.agent}` : ""}${thinking}`);
          const left = (cwd: string, cost: boolean) =>
            dim(`${clean(cwd)}${suffix} `) + (cost ? dim(`$${totals.cost.toFixed(2)} • `) : "") + contextText;
          const fullPath = shortCwd(ctx.cwd, homedir());
          const base = basename(ctx.cwd) || ctx.cwd;
          const candidates = [
            [left(fullPath, true), right(true)],
            [left(base, true), right(true)],
            [left(base, false), right(true)],
            [left(base, false), right(false)],
          ];
          const [lhs, rhs] = candidates.find(([l, r]) => visibleWidth(l) + 1 + visibleWidth(r) <= width) ?? candidates[candidates.length - 1];
          const lines = [align(lhs, rhs, width)];
          if (moreStats) {
            const tokens = `↑${formatTokens(totals.input)} ↓${formatTokens(totals.output)}${totals.cacheHit == null ? "" : ` ¢${totals.cacheHit.toFixed(1)}%`}`;
            const provider = footerData.getAvailableProviderCount() > 1 && ctx.model ? `(${clean(ctx.model.provider)})` : "";
            const stats = [tokens, provider, statuses.mcp, ...statuses.ordinary].filter(Boolean).join(" • ");
            lines.push(truncateToWidth(dim(stats), width, "…"));
          }
          for (const row of statuses.below) lines.push(truncateToWidth(dim(row), width, "…"));
          return lines;
        },
      };
    });
  });
}
