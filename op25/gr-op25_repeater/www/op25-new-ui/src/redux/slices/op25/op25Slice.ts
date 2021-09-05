import { createAsyncThunk, createSlice, PayloadAction } from "@reduxjs/toolkit";
import { RootState } from "redux/app/store";
import { OP25QueueItem } from "models/OP25";
import { OP25State } from "models/OP25State";
import axios from "lib/axios";
import { channel_update } from "lib/op25";

const SEND_QLIMIT = 5;

const initialState: OP25State = {
  current_talkgroupId: undefined,
  channel_system: undefined,
  channel_name: undefined,
  channel_frequency: undefined,
  channel_ppm: undefined,
  channel_tag: undefined,
  channel_sourceAddress: undefined,
  channel_sourceTag: undefined,
  channel_streamURL: undefined,
  stepSizeSmall: 100,
  stepSizeLarge: 1200,
  channel_list: [],
  channel_index: 0,
  send_queue: [],
};

export const sendQueue = createAsyncThunk(
  "op25/sendQueue",
  async (_, { getState, dispatch }) => {
    const state = (getState() as any).op25 as OP25State;

    try {
      const queue: OP25QueueItem[] = [...state.send_queue];
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
  async (send_command: OP25QueueItem, { getState, dispatch }) => {
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
    pushToSendQueue: (state, action: PayloadAction<OP25QueueItem>) => {
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
        const data = action.payload;
        try {
          for (var i = 0; i < data.length; i++) {
            const d = data[i];
            if (!d.json_type) {
              console.log("no json_type", d);
              continue;
            }

            switch (d.json_type) {
              case "trunk_update":
                //console.log("type hit", d.json_type);
                // trunk_update(d);
                continue;
              case "change_freq":
                //console.log("type hit", d.json_type);
                // change_freq(d);
                continue;
              case "channel_update":
                // console.log("channel_update", d);
                channel_update(d, state);
                continue;
              case "rx_update":
                //console.log("rx_update", d);
                // rx_update(d);
                continue;
              case "terminal_config":
                console.log("terminal_config", d);
                //term_config(d);
                continue;
              default:
                console.log("unknown type", d.json_type);
                continue;
            }
          }
        } catch (err) {
          // TODO: Show the user SOMETHING!
          console.log("Error parsing response: ", err);
        }
      })
      .addCase(addToSendQueue.fulfilled, (_, action) => {});
  },
});

export const { pushToSendQueue, unshiftOnSendQueue, emptySendQueue } =
  op25Slice.actions;

export const selectAllState = (state: RootState): OP25State => state.op25;

export const selectCurrentTalkgroupId = (
  state: RootState
): number | undefined => state.op25.current_talkgroupId;

export default op25Slice.reducer;
