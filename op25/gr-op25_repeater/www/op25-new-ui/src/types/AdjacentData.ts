import { Frequency } from "./Frequency";

export interface AdjacentDataItem {
  id: number;
  rfid?: number;
  stid?: number;
  uplink?: Frequency;
  table?: number;
}

export type AdjacentData = AdjacentDataItem[];
