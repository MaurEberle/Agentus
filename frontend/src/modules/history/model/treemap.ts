export type Rect = { x: number; y: number; w: number; h: number };

/**
 * Squarified treemap (Bruls, Huizing, van Wijk): one rectangle per value, its area in
 * proportion to the value, as close to a square as the order allows. Values sorted large
 * to small give the best shapes. Zero or negative values get an empty rectangle.
 */
export function squarify(values: number[], bounds: Rect): Rect[] {
  const positive = values.map((value) => (Number.isFinite(value) && value > 0 ? value : 0));
  const total = positive.reduce((sum, value) => sum + value, 0);
  const empty = (): Rect => ({ x: bounds.x, y: bounds.y, w: 0, h: 0 });
  if (total <= 0 || bounds.w <= 0 || bounds.h <= 0) return values.map(empty);
  const scale = (bounds.w * bounds.h) / total;
  const order = positive.map((value, index) => ({ index, area: value * scale })).filter((item) => item.area > 0);
  const out: Rect[] = values.map(empty);
  let rest: Rect = { ...bounds };
  let row: typeof order = [];

  const worst = (items: typeof order, side: number): number => {
    const sum = items.reduce((acc, item) => acc + item.area, 0);
    let max = 0;
    let min = Number.POSITIVE_INFINITY;
    for (const item of items) {
      max = Math.max(max, item.area);
      min = Math.min(min, item.area);
    }
    return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
  };

  const place = (items: typeof order) => {
    const sum = items.reduce((acc, item) => acc + item.area, 0);
    if (rest.w >= rest.h) {
      // A column along the left side of what is left.
      const width = sum / rest.h;
      let y = rest.y;
      for (const item of items) {
        const h = item.area / width;
        out[item.index] = { x: rest.x, y, w: width, h };
        y += h;
      }
      rest = { x: rest.x + width, y: rest.y, w: Math.max(0, rest.w - width), h: rest.h };
    } else {
      // A row along the top.
      const height = sum / rest.w;
      let x = rest.x;
      for (const item of items) {
        const w = item.area / height;
        out[item.index] = { x, y: rest.y, w, h: height };
        x += w;
      }
      rest = { x: rest.x, y: rest.y + height, w: rest.w, h: Math.max(0, rest.h - height) };
    }
  };

  let index = 0;
  while (index < order.length) {
    const side = Math.min(rest.w, rest.h);
    const next = order[index];
    if (row.length === 0 || worst([...row, next], side) <= worst(row, side)) {
      row.push(next);
      index += 1;
    } else {
      place(row);
      row = [];
    }
  }
  if (row.length > 0) place(row);
  return out;
}
