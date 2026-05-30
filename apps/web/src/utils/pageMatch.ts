/** ±1 page tolerance — matches eval/score_precision.py */
export function pageHitsExpected(retrievedPage: number, expectedPages: number[]): boolean {
  return expectedPages.some((expected) => Math.abs(retrievedPage - expected) <= 1)
}

export function evaluatePageMatch(
  retrievedPages: number[],
  expectedPages: number[],
): { hit: boolean; matchedPages: number[]; missedExpected: number[] } {
  const matchedPages = retrievedPages.filter((page) => pageHitsExpected(page, expectedPages))
  const missedExpected = expectedPages.filter(
    (expected) => !retrievedPages.some((page) => Math.abs(page - expected) <= 1),
  )
  return {
    hit: matchedPages.length > 0,
    matchedPages,
    missedExpected,
  }
}
