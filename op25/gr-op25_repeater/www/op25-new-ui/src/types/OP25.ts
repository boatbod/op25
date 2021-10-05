export interface OP25SendQueueItem {
  command: string;
  arg1: number;
  arg2: number;
}

export type OP25UpdateTypes =
  | "channel_update"
  | "terminal_config"
  | "trunk_update"
  | "change_freq"
  | "rx_update"
  | "full_config";

export interface OP25Update {
  json_type: OP25UpdateTypes;
}

export type OP25Updates = OP25Update[];

// channel_update

export interface OP25ChannelUpdateChannelData {
  freq?: number;
  tdma?: Boolean | null;
  tgid?: number;
  system?: string;
  tag?: string;
  srcaddr?: number;
  srctag?: string;
  encrypted: number;
  mode?: any;
  stream?: string;
  msgqid?: number;
  name?: string;
  ppm?: number;
}

export type OP25TypeChannelUpdateData =
  | "channel_update"
  | OP25ChannelUpdateChannelData
  | string[];

export interface OP25TypeChannelUpdate {
  ["json_type"]: "channel_update";
  ["channels"]: string[];
  [channelId: string]: OP25TypeChannelUpdateData;
}

// trunk_update

export type OP25TrunkUpdateChannelDataFrequency = {
  [frequency: string]: string;
};

export type OP25TrunkUpdateChannelDataFrequencyData = {
  [frequency: string]: {
    tgids: number[];
    last_activity: string;
    counter: number;
  };
};

export type OP25TrunkUpdateChannelDataAdjacentDataItem = {
  [frequency: string]: {
    rfid: number;
    stid: number;
    uplink: number;
    table: number;
  };
};

export interface OP25TrunkUpdateChannelData {
  system?: string;
  top_line?: string;
  syid?: number;
  rfid?: number;
  stid?: number;
  sysid?: number;
  rxchan?: number;
  txchan?: number;
  wacn?: number;
  nac?: number;
  secondary?: number[];
  frequencies?: OP25TrunkUpdateChannelDataFrequency;
  frequency_data?: OP25TrunkUpdateChannelDataFrequencyData;
  last_tsbk?: number;
  adjacent_data: OP25TrunkUpdateChannelDataAdjacentDataItem;
}

export type OP25TypeTrunkUpdateData =
  | "trunk_update"
  | OP25TrunkUpdateChannelData
  | string[]
  | number;

export interface OP25TypeTrunkUpdate {
  ["json_type"]: "trunk_update";
  [channelId: string]: OP25TypeTrunkUpdateData;
  ["nac"]: number;
}

// terminal_config

export interface OP25TypeTerminalConfig {
  json_type: "terminal_config";
  module: string;
  terminal_type: string;
  curses_plot_interval: number;
  http_plot_interval: number;
  http_plot_directory: string;
  tuning_step_large: number;
  tuning_step_small: number;
}
