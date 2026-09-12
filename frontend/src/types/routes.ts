export interface Waypoint {
  latitude: number;
  longitude: number;
}

export const SIMULATED_ROUTES: Record<
  string,
  Waypoint[]
> = {
  R001: [
    {
      latitude: 18.9679,
      longitude: 72.8347,
    },
    {
      latitude: 5,
      longitude: 65,
    },
    {
      latitude: -10,
      longitude: 55,
    },
    {
      latitude: -20,
      longitude: 30,
    },
    {
      latitude: -70.7697,
      longitude: 11.733,
    },
  ],

  R002: [
    {
      latitude: 18.9679,
      longitude: 72.8347,
    },
    {
      latitude: -5,
      longitude: 70,
    },
    {
      latitude: -30,
      longitude: 40,
    },
    {
      latitude: -70.65,
      longitude: 11.83,
    },
  ],

  R003: [
    {
      latitude: 13.0919,
      longitude: 80.2785,
    },
    {
      latitude: 2,
      longitude: 65,
    },
    {
      latitude: -15,
      longitude: 25,
    },
    {
      latitude: -70.7697,
      longitude: 11.733,
    },
  ],

  R004: [
    {
      latitude: 13.0919,
      longitude: 80.2785,
    },
    {
      latitude: -5,
      longitude: 75,
    },
    {
      latitude: -25,
      longitude: 50,
    },
    {
      latitude: -70.65,
      longitude: 11.83,
    },
  ],
};