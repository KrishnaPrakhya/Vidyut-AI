export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const SCENARIOS = [
  { id: "heatwave", name: "Heatwave (Peak Thermal Demand)", desc: "High evening cooling load causing transformer thermal stress." },
  { id: "ev_surge", name: "EV Surge (Uncoordinated Charging)", desc: "Simultaneous residential EV charging cluster peak." },
  { id: "normal", name: "Normal Operating Day", desc: "Standard 24-hour demand profile across 3 feeders." },
];

export const HOTKEYS = [
  { key: "H", label: "Heatwave", type: "heatwave", mag: 1.2 },
  { key: "E", label: "EV Surge", type: "ev_surge", mag: 1.5 },
  { key: "C", label: "Cloud Cover", type: "cloud_cover", mag: 0.8 },
  { key: "F", label: "DT Fault", type: "dt_fault", mag: 1.0 },
  { key: "R", label: "Reset", type: "reset", mag: 1.0 },
];
