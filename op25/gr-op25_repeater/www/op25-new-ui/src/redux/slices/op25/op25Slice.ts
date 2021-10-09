import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { RootState } from "redux/app/store";
import {
  OP25SendQueueItem,
  OP25TypeChannelUpdate,
  OP25TypeTerminalConfig,
  OP25TypeTrunkUpdate,
  OP25Updates,
} from "types/OP25";
import { OP25State } from "types/OP25State";
import axios from "utils/axios";
import { channel_update, terminal_config, trunk_update } from "lib/op25";
import { Channel, Channels } from "types/Channel";
import { System, Systems } from "types/System";
import { AxiosResponse } from "axios";

const SEND_QLIMIT = 10;

const initialState: OP25State = {
  isConnected: false,
  channels: [],
  systems: [],
  terminalConfig: undefined,
  send_queue: [{ command: "get_config", arg1: 0, arg2: 0 }],
};

export const sendQueue = createAsyncThunk(
  "op25/sendQueue",
  async (_, { getState, dispatch }) => {
    const state = (getState() as any).op25 as OP25State;

    const queue: OP25SendQueueItem[] = [...state.send_queue];
    dispatch(emptySendQueue());

    const response = await axios().post("/", queue);

    return {
      status: response.status,
      statusText: response.statusText,
      data: response.data,
    };
  }
);

export const addToSendQueue = createAsyncThunk(
  "op25/addToSendQueue",
  async (send_command: OP25SendQueueItem, { getState, dispatch }) => {
    const state = (getState() as any).op25 as OP25State;

    if (state.send_queue.length >= SEND_QLIMIT) {
      dispatch(unshiftOnSendQueue());
    }

    dispatch(pushToSendQueue(send_command));
  }
);

export const op25Slice = createSlice({
  name: "op25",
  initialState,
  reducers: {
    pushToSendQueue: (state, action: PayloadAction<OP25SendQueueItem>) => {
      state.send_queue.push(action.payload);
    },
    unshiftOnSendQueue: (state) => {
      state.send_queue.unshift();
    },
    emptySendQueue: (state) => {
      state.send_queue = [];
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendQueue.fulfilled, (state, action) => {
        state.isConnected = true;
        const {
          status,
          statusText,
          data,
        } = action.payload as AxiosResponse<any>;
        if (status !== 200) {
          // TODO: Show the user SOMETHING!
          console.log(`Error ${status.toString(10)}: ${statusText}`);
          return;
        }

        if (data) {
          const dataUpdates: OP25Updates = data;
          try {
            dataUpdates.forEach((update) => {
              if (!update.json_type) {
                console.log("no json_type", update);
                return;
              }

              switch (update.json_type) {
                case "trunk_update":
                  //console.log("trunk_update", update);
                  trunk_update(update as OP25TypeTrunkUpdate, state);
                  return;
                case "change_freq":
                  console.log("***** change_freq *****", update);
                  // change_freq(update);
                  return;
                case "channel_update":
                  channel_update(update as OP25TypeChannelUpdate, state);
                  return;
                case "rx_update":
                  console.log("***** rx_update *****", update); // Plot Updates
                  // rx_update(update);
                  return;
                case "terminal_config":
                  terminal_config(update as OP25TypeTerminalConfig, state);
                  return;
                case "full_config":
                  console.log("full_config", update);
                  return;
                default:
                  console.log("unknown server data type", update.json_type);
                  return;
              }
            });
          } catch (err) {
            // TODO: Show the user SOMETHING!
            console.log("Error parsing response: ", err);
          }
        }
      })
      .addCase(sendQueue.rejected, (state) => {
        if (state.isConnected === undefined || state.isConnected) {
          state.isConnected = false;
          globalThis.scroll({ top: 0, left: 0, behavior: "smooth" });
        }
      })
      .addCase(addToSendQueue.fulfilled, (_) => {});
  },
});

export const {
  pushToSendQueue,
  unshiftOnSendQueue,
  emptySendQueue,
} = op25Slice.actions;

export const isConnected = (state: RootState): boolean | undefined =>
  state.op25.isConnected;

export const selectChannels = (state: RootState): Channels =>
  state.op25.channels;

export const selectChannel = (channelId: number) => (
  state: RootState
): Channel | undefined =>
  state.op25.channels.find((channel) => channel.id === channelId);

export const selectSystemFromChannelId = (channelId: number) => (
  state: RootState
): System | undefined => {
  const channel = state.op25.channels.find(
    (channel) => channel.id === channelId
  );
  return channel
    ? state.op25.systems.find((system) => system.name === channel.systemName)
    : undefined;
};

export const selectSystems = (state: RootState): Systems => state.op25.systems;

export const getSystemsCount = (state: RootState): number =>
  state.op25.systems.length;

export const selectSystem = (systemId: number) => (
  state: RootState
): System | undefined =>
  state.op25.systems.find((system) => system.id === systemId);

export const selectStepSizes = (
  state: RootState
): { stepSizeSmall: number; stepSizeLarge: number } => ({
  stepSizeSmall: state.op25.terminalConfig?.tuningStepSizeSmall || 100,
  stepSizeLarge: state.op25.terminalConfig?.tuningStepSizeLarge || 1200,
});

export default op25Slice.reducer;
