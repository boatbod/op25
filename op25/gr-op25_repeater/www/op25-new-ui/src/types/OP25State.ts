import { OP25QueueItem } from "./OP25";

export interface OP25State {
  current_talkgroupId: number | undefined;
  channel_system: string | undefined;
  channel_name: string | undefined;
  channel_frequency: number | undefined;
  channel_ppm: number | undefined;
  channel_tag: string | undefined;
  channel_sourceAddress: number | undefined;
  channel_sourceTag: string | undefined;
  channel_streamURL: string | undefined;
  stepSizeSmall: number;
  stepSizeLarge: number;
  channel_list: [];
  channel_index: number;
  send_queue: OP25QueueItem[];
}
