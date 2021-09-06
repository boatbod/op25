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
  | "rx_update";

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
