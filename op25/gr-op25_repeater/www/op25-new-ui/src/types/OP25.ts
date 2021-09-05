export type TalkgroupId = number | undefined;

export interface Talkgroup {
  id: TalkgroupId;
  name?: string;
  description?: string;
  skipped: boolean;
  hold: boolean;
}

export interface OP25QueueItem {
  command: string;
  arg1: number;
  arg2: number;
}
