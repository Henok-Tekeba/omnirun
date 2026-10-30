import devices from "./devices.json";
import type { DeviceEntry } from "../api/types";

export const STATIC_DEVICES = devices as unknown as DeviceEntry[];
