import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { RootState } from "redux/app/store";
import {
  OP25SendQueueItem,
  OP25TypeChannelUpdate,
  OP25TypeTerminalConfig,
  OP25Updates,
} from "types/OP25";
import { OP25State } from "types/OP25State";
import axios from "utils/axios";
import { channel_update, terminal_config } from "lib/op25";
import { Channel, Channels } from "types/Channel";

const SEND_QLIMIT = 5;

const initialState: OP25State = {
  channels: [],
  terminalConfig: undefined,
  send_queue: [],
};

export const sendQueue = createAsyncThunk(
  "op25/sendQueue",
  async (_, { getState, dispatch }) => {
    const state = (getState() as any).op25 as OP25State;

    try {
      const queue: OP25SendQueueItem[] = [...state.send_queue];
      dispatch(emptySendQueue());
      const response = await axios().post("/", queue);
      if (response.status !== 200) {
        // TODO: Show the user SOMETHING!
        console.log(
          `Error ${response.status.toString(10)}: ${response.statusText}`
        );
        return;
      }
      return response.data;
    } catch (err) {
      // TODO: Show the user SOMETHING!
      console.log("Axios request error:", err);
    }
  }
);

export const addToSendQueue = createAsyncThunk(
  "op25/addToSendQueue",
  async (send_command: OP25SendQueueItem, { getState, dispatch }) => {
    const state = (getState() as any).op25 as OP25State;

    if (state.send_queue.length >= SEND_QLIMIT) {
      dispatch(unshiftOnSendQueue(undefined));
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
    unshiftOnSendQueue: (state, action: PayloadAction<any | undefined>) => {
      state.send_queue.unshift(action.payload);
    },
    emptySendQueue: (state) => {
      state.send_queue = [];
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(sendQueue.fulfilled, (state, action: any) => {
        if (action.payload) {
          const data: OP25Updates = action.payload;
          try {
            data.forEach((update) => {
              if (!update.json_type) {
                console.log("no json_type", update);
                return;
              }

              switch (update.json_type) {
                case "trunk_update":
                  //console.log("trunk_update", update);
                  // trunk_update(update);
                  return;
                case "change_freq":
                  //console.log("***** change_freq *****", update);
                  // change_freq(update);
                  return;
                case "channel_update":
                  channel_update(update as OP25TypeChannelUpdate, state);
                  return;
                case "rx_update":
                  // console.log("***** rx_update *****", update); // Plot Updates
                  // rx_update(update);
                  return;
                case "terminal_config":
                  terminal_config(update as OP25TypeTerminalConfig, state);
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
      .addCase(addToSendQueue.fulfilled, (_, action) => {});
  },
});

export const { pushToSendQueue, unshiftOnSendQueue, emptySendQueue } =
  op25Slice.actions;

export const selectChannels = (state: RootState): Channels =>
  state.op25.channels;

export const selectChannel =
  (channelId: number) =>
  (state: RootState): Channel | undefined =>
    state.op25.channels.find((channel) => channel.id === channelId);

export const selectStepSizes = (
  state: RootState
): { stepSizeSmall: number; stepSizeLarge: number } => ({
  stepSizeSmall: state.op25.terminalConfig?.tuningStepSizeSmall || 100,
  stepSizeLarge: state.op25.terminalConfig?.tuningStepSizeLarge || 1200,
});

export default op25Slice.reducer;
