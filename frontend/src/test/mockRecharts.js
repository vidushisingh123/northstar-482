import React from 'react'

// jsdom has no layout, so give ResponsiveContainer a fixed size.
export async function withFixedSize(importOriginal) {
  const mod = await importOriginal()
  return {
    ...mod,
    ResponsiveContainer: ({ children }) => React.cloneElement(children, { width: 900, height: 300 }),
  }
}
