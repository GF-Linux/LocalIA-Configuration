export type TriggerState = { lastFiredMs: number; lastHash: string | null };

export function initialTriggerState(): TriggerState {
  return { lastFiredMs: -Infinity, lastHash: null };
}

export function hashCode(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

export function decideTrigger(
  state: TriggerState,
  nowMs: number,
  codeHash: string,
  cooldownMs: number
): { fire: boolean; nextState: TriggerState } {
  const withinCooldown = nowMs - state.lastFiredMs < cooldownMs;
  const sameCode = codeHash === state.lastHash;
  if (withinCooldown || sameCode) return { fire: false, nextState: state };
  return { fire: true, nextState: { lastFiredMs: nowMs, lastHash: codeHash } };
}
