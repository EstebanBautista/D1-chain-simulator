/*
 * Bar charts, drawn as SVG by hand.
 *
 * No charting library. Two bar charts is a small amount of geometry — scale a
 * value to a pixel width, loop, emit one <rect> per bar — and vendoring a
 * minified blob would mean reading someone else's chart configuration instead
 * of reading this.
 *
 * Both charts are horizontal. Product names and store names are long enough
 * that vertical bars would need rotated labels, which are harder to read and
 * harder to draw.
 */

const SVG_NS = "http://www.w3.org/2000/svg";

// Layout constants, in SVG user units.
const LABEL_WIDTH = 190; // room for the name at the left of each bar
const VALUE_WIDTH = 130; // room for the figure at the right
const BAR_HEIGHT = 26;
const BAR_GAP = 14;
const TOP_PADDING = 8;
const CHART_WIDTH = 900;

function createElement(name, attributes) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value);
  }
  return element;
}

function createText(x, y, content, className, anchor) {
  const text = createElement("text", {
    x,
    y,
    class: className,
    "dominant-baseline": "middle",
  });
  if (anchor) {
    text.setAttribute("text-anchor", anchor);
  }
  text.textContent = content;
  return text;
}

/**
 * Truncate a label that would overflow its column.
 *
 * SVG has no text wrapping and no ellipsis, so a long product name would run
 * under the bars. Cutting it here keeps the chart readable; the full name
 * stays available as the bar's tooltip.
 */
function truncate(label, maxCharacters) {
  if (label.length <= maxCharacters) {
    return label;
  }
  return `${label.slice(0, maxCharacters - 1)}…`;
}

/**
 * Draw a horizontal bar chart into `container`.
 *
 * Each entry: { label, value, valueText, sublabel?, className? }
 * `value` scales the bar; `valueText` is what the reader sees, already
 * formatted. Keeping those apart is what lets the same function draw pesos in
 * one chart and unit counts in the other.
 */
function renderBarChart(container, entries) {
  container.replaceChildren();

  if (!entries.length) {
    return;
  }

  const height = TOP_PADDING * 2 + entries.length * (BAR_HEIGHT + BAR_GAP);
  const svg = createElement("svg", {
    viewBox: `0 0 ${CHART_WIDTH} ${height}`,
    role: "img",
  });

  const trackWidth = CHART_WIDTH - LABEL_WIDTH - VALUE_WIDTH;

  // Scale against the largest value, so the longest bar always fills the
  // track. With every value at zero there is nothing to scale against, so fall
  // back to 1 and draw a row of empty bars rather than dividing by zero.
  const maxValue = Math.max(...entries.map((entry) => entry.value), 0) || 1;

  // The baseline every bar starts from.
  svg.appendChild(
    createElement("line", {
      x1: LABEL_WIDTH,
      y1: TOP_PADDING,
      x2: LABEL_WIDTH,
      y2: height - TOP_PADDING,
      class: "axis-line",
    })
  );

  entries.forEach((entry, index) => {
    const y = TOP_PADDING + index * (BAR_HEIGHT + BAR_GAP);
    const middle = y + BAR_HEIGHT / 2;
    const barWidth = Math.max((entry.value / maxValue) * trackWidth, 0);

    const label = createText(
      LABEL_WIDTH - 12,
      entry.sublabel ? middle - 7 : middle,
      truncate(entry.label, 26),
      "bar-label",
      "end"
    );
    svg.appendChild(label);

    if (entry.sublabel) {
      svg.appendChild(
        createText(
          LABEL_WIDTH - 12,
          middle + 8,
          truncate(entry.sublabel, 30),
          "bar-sublabel",
          "end"
        )
      );
    }

    const bar = createElement("rect", {
      x: LABEL_WIDTH,
      y,
      width: barWidth,
      height: BAR_HEIGHT,
      rx: 3,
      class: entry.className ? `bar ${entry.className}` : "bar",
    });
    // The untruncated name, for anyone who needs it.
    const title = createElement("title", {});
    title.textContent = entry.label;
    bar.appendChild(title);
    svg.appendChild(bar);

    svg.appendChild(
      createText(
        LABEL_WIDTH + barWidth + 10,
        middle,
        entry.valueText,
        "bar-value",
        "start"
      )
    );
  });

  container.appendChild(svg);
}

/** Replace a chart with a sentence explaining why it is not there. */
function renderChartMessage(container, text) {
  container.replaceChildren();
  const paragraph = document.createElement("p");
  paragraph.className = "chart-empty";
  paragraph.textContent = text;
  container.appendChild(paragraph);
}
