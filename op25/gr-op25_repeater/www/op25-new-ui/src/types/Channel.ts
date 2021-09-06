export interface Channel {
  id: number;
  encrypted: boolean;
  frequency?: number;
  mode?: any;
  msgqid?: number;
  name?: string;
  ppm?: number;
  sourceAddress?: number;
  sourceTag?: string;
  stream?: string;
  systemName?: string;
  tdma?: any;
  tgID?: number;
  tgTag?: string;
}

export type Channels = Channel[];
