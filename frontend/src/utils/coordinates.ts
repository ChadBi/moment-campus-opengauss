export interface Coordinate {
  latitude: number;
  longitude: number;
}

const PI = Math.PI;
const SEMI_MAJOR_AXIS = 6378245.0;
const ECCENTRICITY_SQUARED = 0.006693421622965943;

const outsideMainlandChina = (latitude: number, longitude: number) =>
  longitude < 72.004 || longitude > 137.8347 || latitude < 0.8293 || latitude > 55.8271;

const transformLatitude = (x: number, y: number) => {
  let result = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
  result += ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3;
  result += ((20 * Math.sin(y * PI) + 40 * Math.sin((y / 3) * PI)) * 2) / 3;
  result += ((160 * Math.sin((y / 12) * PI) + 320 * Math.sin((y * PI) / 30)) * 2) / 3;
  return result;
};

const transformLongitude = (x: number, y: number) => {
  let result = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
  result += ((20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2) / 3;
  result += ((20 * Math.sin(x * PI) + 40 * Math.sin((x / 3) * PI)) * 2) / 3;
  result += ((150 * Math.sin((x / 12) * PI) + 300 * Math.sin((x / 30) * PI)) * 2) / 3;
  return result;
};

/** Convert browser/GPS WGS-84 coordinates to the application's GCJ-02 contract. */
export const wgs84ToGcj02 = (latitude: number, longitude: number): Coordinate => {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new TypeError('Coordinates must be finite numbers');
  }
  if (outsideMainlandChina(latitude, longitude)) return { latitude, longitude };

  let latitudeDelta = transformLatitude(longitude - 105, latitude - 35);
  let longitudeDelta = transformLongitude(longitude - 105, latitude - 35);
  const radians = (latitude / 180) * PI;
  const sinLatitude = Math.sin(radians);
  const magic = 1 - ECCENTRICITY_SQUARED * sinLatitude * sinLatitude;
  const sqrtMagic = Math.sqrt(magic);
  latitudeDelta =
    (latitudeDelta * 180) /
    (((SEMI_MAJOR_AXIS * (1 - ECCENTRICITY_SQUARED)) / (magic * sqrtMagic)) * PI);
  longitudeDelta =
    (longitudeDelta * 180) /
    ((SEMI_MAJOR_AXIS / sqrtMagic) * Math.cos(radians) * PI);

  return {
    latitude: latitude + latitudeDelta,
    longitude: longitude + longitudeDelta,
  };
};
