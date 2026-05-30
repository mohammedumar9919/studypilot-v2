import type { GoldenMissHint } from '../types'

/** Eval at 100% precision@5 — no remaining misses. Dev inspector shows empty state. */
export const GOLDEN_MISSES: GoldenMissHint[] = []

/** Rough CPU rerank duration; switch progress label after this (see CURRENT_STATE). */
export const RETRIEVAL_ESTIMATE_MS = 25_000
