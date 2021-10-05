// function term_config(d: any) {
// TODO: Remove ANY Type
//   var lg_step = 1200;
//   var sm_step = 100;
//   var updated = 0;
//   if (
//     d["tuning_step_large"] != undefined &&
//     d["tuning_step_large"] != lg_step
//   ) {
//     lg_step = d["tuning_step_large"];
//     updated++;
//   }
//   if (
//     d["tuning_step_small"] != undefined &&
//     d["tuning_step_small"] != sm_step
//   ) {
//     sm_step = d["tuning_step_small"];
//     updated++;
//   }
//   if (updated) {
//     set_tuning_step_sizes(lg_step, sm_step);
//   }
// }
// function set_tuning_step_sizes(lg_step = 1200, sm_step = 100) {
//   var title_str = "Adjust tune ";
//   var bn_t1_U = document.getElementById("t1_U");
//   var bn_t2_U = document.getElementById("t2_U");
//   var bn_t1_D = document.getElementById("t1_D");
//   var bn_t2_D = document.getElementById("t2_D");
//   var bn_t1_u = document.getElementById("t1_u");
//   var bn_t2_u = document.getElementById("t2_u");
//   var bn_t1_d = document.getElementById("t1_d");
//   var bn_t2_d = document.getElementById("t2_d");
//   if (bn_t1_U != null && bn_t2_U != null) {
//     bn_t1_U.setAttribute("title", title_str + "+" + lg_step);
//     bn_t2_U.setAttribute("title", title_str + "+" + lg_step);
//     bn_t1_U.setAttribute(
//       "onclick",
//       "javascript:f_tune_button(" + lg_step + ");"
//     );
//     bn_t2_U.setAttribute(
//       "onclick",
//       "javascript:f_tune_button(" + lg_step + ");"
//     );
//   }
//   if (bn_t1_D != null && bn_t2_D != null) {
//     bn_t1_D.setAttribute("title", title_str + "-" + lg_step);
//     bn_t2_D.setAttribute("title", title_str + "-" + lg_step);
//     bn_t1_D.setAttribute(
//       "onclick",
//       "javascript:f_tune_button(-" + lg_step + ");"
//     );
//     bn_t2_D.setAttribute(
//       "onclick",
//       "javascript:f_tune_button(-" + lg_step + ");"
//     );
//   }
//   if (bn_t1_u != null && bn_t2_u != null) {
//     bn_t1_u.setAttribute("title", title_str + "+" + sm_step);
//     bn_t2_u.setAttribute("title", title_str + "+" + sm_step);
//     bn_t1_u.setAttribute(
//       "onclick",
//       "javascript:f_tune_button(" + sm_step + ");"
//     );
//     bn_t2_u.setAttribute(
//       "onclick",
//       "javascript:f_tune_button(" + sm_step + ");"
//     );
//   }
//   if (bn_t1_d != null && bn_t2_d != null) {
//     bn_t1_d.setAttribute("title", title_str + "-" + sm_step);
//     bn_t2_d.setAttribute("title", title_str + "-" + sm_step);
//     bn_t1_d.setAttribute(
//       "onclick",
//       "javascript:f_tune_button(-" + sm_step + ");"
//     );
//     bn_t2_d.setAttribute(
//       "onclick",
//       "javascript:f_tune_button(-" + sm_step + ");"
//     );
//   }
// }

// function rx_update(d) {
//   plotfiles = [];
//   if ((d["files"] != undefined) && (d["files"].length > 0)) {
//       for (var i=0; i < d["files"].length; i++) {
//           if (channel_list.length > 0) {
//               expr = new RegExp("plot\-" + channel_list[channel_index] + "\-");
//           }
//           else {
//               expr = new RegExp("plot\-0\-");
//           }

//           if (expr.test(d["files"][i])) {
//               plotfiles.push(d["files"][i]);
//           }
//       }

//       for (var i=0; i < 5; i++) {
//           var img = document.getElementById("img" + i);
//           if (i < plotfiles.length) {
//               if (img['src'] != plotfiles[i]) {
//                   img['src'] = plotfiles[i];
//                   img.style["display"] = "";
//               }
//           }
//           else {
//               img.style["display"] = "none";
//           }
//       }
//   }
//   else {
//       var img = document.getElementById("img0");
//       img.style["display"] = "none";
//   }
//   if (d["error"] != undefined)
//       error_val = d["error"];
//   if (d["fine_tune"] != undefined)
//       fine_tune = d["fine_tune"];
// }

import { Draft } from "@reduxjs/toolkit";
import { StoreType } from "redux/app/store";
import { addToSendQueue } from "redux/slices/op25/op25Slice";
import { AdjacentData } from "types/AdjacentData";
import { Channel } from "types/Channel";
import { Frequencies } from "types/Frequency";
import {
  OP25ChannelUpdateChannelData,
  OP25TrunkUpdateChannelData,
  OP25TrunkUpdateChannelDataAdjacentDataItem,
  OP25TrunkUpdateChannelDataFrequency,
  OP25TrunkUpdateChannelDataFrequencyData,
  OP25TypeChannelUpdate,
  OP25TypeTerminalConfig,
  OP25TypeTrunkUpdate,
} from "types/OP25";
import { OP25State } from "types/OP25State";
import { System } from "types/System";
import { TerminalConfig } from "types/TerminalConfig";

export const frequencyToString = (frequency: number) => {
  return (frequency / 1000000.0).toFixed(6);
};

export const ppmToString = (ppm: number) => {
  return ppm.toFixed(3);
};

export const channel_update = (
  data: OP25TypeChannelUpdate,
  state: Draft<OP25State>
) => {
  if (data.json_type === "channel_update" && data.channels) {
    data.channels.forEach((channel) => {
      const channelData = data[channel] as OP25ChannelUpdateChannelData;
      const newData: Channel = {
        id: Number.parseInt(channel),
        encrypted: channelData.encrypted === 1,
        frequency: channelData.freq,
        mode: channelData.mode,
        name: channelData.name,
        sourceAddress: channelData.srcaddr,
        sourceTag: channelData.srctag,
        stream: channelData.stream,
        msgqid: channelData.msgqid,
        ppm: channelData.ppm,
        systemName: channelData.system,
        tdma: channelData.tdma,
        tgID: channelData.tgid,
        tgTag: channelData.tag,
      };

      const currentItemIndex = state.channels.findIndex(
        (ch) => ch.id === Number.parseInt(channel)
      );

      if (currentItemIndex === -1) {
        state.channels.push(newData);
      } else {
        state.channels[currentItemIndex] = newData;
      }
    });
  }
};

export const trunk_update = (
  data: OP25TypeTrunkUpdate,
  state: Draft<OP25State>
) => {
  if (data.json_type === "trunk_update") {
    Object.keys(data)
      .filter((id) => id !== "json_type" && id !== "nac")
      .forEach((id) => {
        const systemData = data[id] as OP25TrunkUpdateChannelData;

        let frequencies: Frequencies = [];
        let adjacentdata: AdjacentData = [];

        Object.keys(
          systemData.frequencies as OP25TrunkUpdateChannelDataFrequency
        ).forEach((freq) => {
          const freqDisplayData = (systemData.frequencies as OP25TrunkUpdateChannelDataFrequency)[
            freq
          ];

          const freqData = (systemData.frequency_data as OP25TrunkUpdateChannelDataFrequencyData)[
            Number.parseInt(freq)
          ];

          frequencies.push({
            frequency: Number.parseInt(freq),
            counter: freqData.counter,
            lastActivitySeconds: Number.parseInt(freqData.last_activity),
            talkgroups: freqData.tgids.map((talkgroup) => ({
              id: talkgroup,
            })),
            displayText: freqDisplayData,
          });
        });

        Object.keys(
          systemData.adjacent_data as OP25TrunkUpdateChannelDataAdjacentDataItem
        ).forEach((adjItem) => {
          const adjItemData = (systemData.adjacent_data as OP25TrunkUpdateChannelDataAdjacentDataItem)[
            adjItem
          ];

          adjacentdata.push({
            id: Number.parseInt(adjItem),
            rfid: adjItemData.rfid,
            stid: adjItemData.stid,
            uplink: { frequency: adjItemData.uplink },
            table: adjItemData.table,
          });
        });

        const newData: System = {
          id: Number.parseInt(id),
          syid: systemData.syid,
          rfid: systemData.rfid,
          stid: systemData.stid,
          rxFrequency: systemData.rxchan,
          txFrequency: systemData.txchan,
          wacn: systemData.wacn,
          nac: systemData.nac,
          secondaryFrequencies: systemData.secondary,
          frequencies: frequencies,
          name: systemData.system,
          TopLine: systemData.top_line,
          lastTSBK: systemData.last_tsbk,
          adjacentData: adjacentdata,
        };

        const currentItemIndex = state.systems.findIndex(
          (sys) => sys.id === Number.parseInt(id)
        );

        if (currentItemIndex === -1) {
          state.systems.push(newData);
        } else {
          state.systems[currentItemIndex] = newData;
        }
      });
  }
};

export const terminal_config = (
  data: OP25TypeTerminalConfig,
  state: Draft<OP25State>
) => {
  if (data.json_type === "terminal_config") {
    const config: TerminalConfig = {
      module: data.module,
      terminalType: data.terminal_type,
      cursesPlotInterval: data.curses_plot_interval,
      httpPlotInterval: data.http_plot_interval,
      httpPlotDirectory: data.http_plot_directory,
      tuningStepSizeLarge: data.tuning_step_large,
      tuningStepSizeSmall: data.tuning_step_small,
    };

    state.terminalConfig = config;
  }
};

export class OP25 {
  private static instance: OP25;

  private _store: StoreType | null;

  static getInstance() {
    if (!OP25.instance) {
      OP25.instance = new OP25();
    }

    return OP25.instance;
  }

  constructor() {
    this._store = null;
  }

  setStore(store: StoreType): void {
    this._store = store;
  }

  async sendGetSimpleConfig(): Promise<void> {
    if (!this._store) {
      return;
    }

    await this._store.dispatch(
      addToSendQueue({ command: "get_config", arg1: 0, arg2: 0 })
    );
  }

  async sendGetFullConfig(): Promise<void> {
    if (!this._store) {
      return;
    }

    await this._store.dispatch(
      addToSendQueue({ command: "get_full_config", arg1: 0, arg2: 0 })
    );
  }

  async sendUpdateChannels(): Promise<void> {
    if (!this._store) {
      return;
    }
    const state = this._store.getState();

    const { channels } = state.op25;

    if (channels.length === 0) {
      await this._store?.dispatch(
        addToSendQueue({ command: "update", arg1: 0, arg2: 0 })
      );
    } else {
      channels.forEach(async (channel) => {
        await this._store?.dispatch(
          addToSendQueue({
            command: "update",
            arg1: 0,
            arg2: channel.id,
          })
        );
      });
    }
  }

  async sendHoldOnChannel(
    channelId: number,
    talkgroupId: number
  ): Promise<void> {
    await this._store?.dispatch(
      addToSendQueue({ command: "hold", arg1: talkgroupId, arg2: channelId })
    );
  }

  async sendUnHoldOnChannel(channelId: number): Promise<void> {
    await this._store?.dispatch(
      addToSendQueue({ command: "hold", arg1: 0, arg2: channelId })
    );
  }

  async sendSkipOnChannel(channelId: number): Promise<void> {
    await this._store?.dispatch(
      addToSendQueue({ command: "skip", arg1: 0, arg2: channelId })
    );
  }

  async sendBlacklistOnChannel(
    channelId: number,
    talkgroupId: number
  ): Promise<void> {
    await this._store?.dispatch(
      addToSendQueue({ command: "lockout", arg1: talkgroupId, arg2: channelId })
    );
  }

  async sendWhitelistOnChannel(
    channelId: number,
    talkgroupId: number
  ): Promise<void> {
    await this._store?.dispatch(
      addToSendQueue({
        command: "whitelist",
        arg1: talkgroupId,
        arg2: channelId,
      })
    );
  }

  async sendReloadOnChannel(channelId: number): Promise<void> {
    await this._store?.dispatch(
      addToSendQueue({ command: "reload", arg1: 0, arg2: channelId })
    );
  }

  async sendSetDebugOnChannel(
    channelId: number,
    debugLevel: number
  ): Promise<void> {
    await this._store?.dispatch(
      addToSendQueue({
        command: "set_debug",
        arg1: debugLevel,
        arg2: channelId,
      })
    );
  }
}
