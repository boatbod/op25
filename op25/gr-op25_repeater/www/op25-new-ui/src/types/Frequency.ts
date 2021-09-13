import { Talkgroups } from "./Talkgroup";

export interface Frequency {
  frequency: number;
  rxFrequency?: number;
  txFrequency?: number;
  displayText?: string;
  talkgroups?: Talkgroups;
  lastActivitySeconds?: number;
  counter?: number;
}

export type Frequencies = Frequency[];
