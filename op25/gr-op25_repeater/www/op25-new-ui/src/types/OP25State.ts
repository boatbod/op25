import { Channels } from "./Channel";
import { OP25SendQueueItem } from "./OP25";
import { TerminalConfig } from "./TerminalConfig";

export interface OP25State {
  channels: Channels;
  terminalConfig?: TerminalConfig;
  send_queue: OP25SendQueueItem[];
}
