const SVG_NS = 'http://www.w3.org/2000/svg';

/**
 * Marker path starts at the visual tip (50, 100). Keeping that point on the
 * SVG's bottom edge lets MapLibre's anchor="bottom" target the same point
 * without any pixel compensation.
 */
export const MAP_MARKER_PATH =
  'M 50 100 C 46 91 10 64 10 37 C 10 16.6 27.9 0 50 0 C 72.1 0 90 16.6 90 37 C 90 64 54 91 50 100 Z';

interface MapMarkerElementOptions {
  color: string;
  count: number;
  size: number;
}

const setAttributes = (element: Element, attributes: Record<string, string>) => {
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
};

export const createMapMarkerElement = ({ color, count, size }: MapMarkerElementOptions) => {
  const isGrouped = count > 1;
  const element = document.createElement('div');
  element.className = 'custom-marker';
  element.dataset.markerKind = isGrouped ? 'grouped' : 'single';
  element.style.cssText = `width: ${size}px; height: ${size}px; cursor: pointer; position: relative; transition: none;`;

  const svg = document.createElementNS(SVG_NS, 'svg');
  setAttributes(svg, {
    'aria-hidden': 'true',
    class: 'custom-marker__visual',
    focusable: 'false',
    height: String(size),
    viewBox: '0 0 100 100',
    width: String(size),
  });
  svg.style.cssText = [
    'display: block',
    'width: 100%',
    'height: 100%',
    'overflow: visible',
    'pointer-events: none',
    'transform: scale(1)',
    'transform-origin: 50% 100%',
    'transition: none',
    'will-change: transform',
    `filter: drop-shadow(0 2px ${isGrouped ? '4px' : '3px'} rgba(0, 0, 0, ${isGrouped ? '0.35' : '0.3'}))`,
  ].join('; ');

  const path = document.createElementNS(SVG_NS, 'path');
  setAttributes(path, {
    class: 'custom-marker__shape',
    d: MAP_MARKER_PATH,
    fill: color,
  });
  svg.appendChild(path);

  if (isGrouped) {
    const text = document.createElementNS(SVG_NS, 'text');
    setAttributes(text, {
      'dominant-baseline': 'middle',
      fill: '#ffffff',
      'font-family': 'system-ui, sans-serif',
      'font-size': '36',
      'font-weight': '700',
      'text-anchor': 'middle',
      x: '50',
      y: '36',
    });
    text.textContent = String(count);
    svg.appendChild(text);
  } else {
    const dot = document.createElementNS(SVG_NS, 'circle');
    setAttributes(dot, {
      cx: '50',
      cy: '35',
      fill: '#ffffff',
      r: '18',
    });
    svg.appendChild(dot);
  }

  element.appendChild(svg);
  element.addEventListener('mouseenter', () => {
    element.style.zIndex = '10';
    svg.style.transform = 'scale(1.2)';
  });
  element.addEventListener('mouseleave', () => {
    element.style.zIndex = '';
    svg.style.transform = 'scale(1)';
  });

  return element;
};
