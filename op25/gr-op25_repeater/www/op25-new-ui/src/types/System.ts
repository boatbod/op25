import { AdjacentData } from "./AdjacentData";
import { Frequencies } from "./Frequency";

export interface System {
  id: number;
  syid?: number;
  rfid?: number;
  stid?: number;
  rxFrequency?: number;
  txFrequency?: number;
  wacn?: number;
  nac?: number;
  secondaryFrequencies?: number[];
  frequencies?: Frequencies;
  name?: string;
  TopLine?: string;
  lastTSBK?: number;
  adjacentData?: AdjacentData;
}

export type Systems = System[];
