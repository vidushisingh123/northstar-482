// A line cannot be drawn through a point whose neighbours are both missing, so such a point
// would be invisible. This dot renderer draws a marker only for those isolated points.
export function isolatedDot(lineRows, key, color) {
  return function renderDot({ cx, cy, index }) {
    const has = (i) => i >= 0 && i < lineRows.length && lineRows[i][key] !== null
    // Only a point that HAS a value, with no valued neighbour, is isolated. Missing points draw nothing.
    const isolated = has(index) && !has(index - 1) && !has(index + 1)
    return isolated ? (
      <circle key={`dot-${index}`} cx={cx} cy={cy} r={2.5} fill={color} />
    ) : (
      <g key={`dot-${index}`} />
    )
  }
}
