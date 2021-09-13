import { Channels } from "./Channel";
import { OP25SendQueueItem } from "./OP25";
import { Systems } from "./System";
import { TerminalConfig } from "./TerminalConfig";

export interface OP25State {
  channels: Channels;
  systems: Systems;
  terminalConfig?: TerminalConfig;
  send_queue: OP25SendQueueItem[];
}
