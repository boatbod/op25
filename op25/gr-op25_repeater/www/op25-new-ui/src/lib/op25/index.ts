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

import { Draft } from "@reduxjs/toolkit";
import { OP25State } from "types/OP25State";

export const frequencyToString = (frequency: number) => {
  return (frequency / 1000000.0).toFixed(6);
};

export const ppmToString = (ppm: number) => {
  return ppm.toFixed(3);
};

export const channel_update = (d: any, state: Draft<OP25State>) => {
  //   var s2_c = document.getElementById("s2_ch_lbl");
  //   var s2_d = document.getElementById("s2_ch_txt");
  //   var s2_e = document.getElementById("s2_ch_dn");
  //   var s2_f = document.getElementById("s2_ch_dmp");
  //   var s2_g = document.getElementById("s2_ch_up");

  if (d["channels"] !== undefined) {
    state.channel_list = d["channels"];

    if (state.channel_list.length > 0) {
      const c_id = state.channel_list[state.channel_index];
      state.channel_system = d[c_id]["system"];
      state.channel_name = "[" + c_id + "]";

      if (d[c_id]["name"] !== undefined && d[c_id]["name"] !== "") {
        state.channel_name += " " + d[c_id]["name"];
      } else {
        state.channel_name += " " + state.channel_system;
      }

      state.channel_frequency = d[c_id]["freq"];
      state.channel_ppm = d[c_id]["ppm"];
      state.current_talkgroupId = d[c_id]["tgid"];
      state.channel_tag = d[c_id]["tag"];
      state.channel_sourceAddress = d[c_id]["srcaddr"];
      state.channel_sourceTag = d[c_id]["srctag"];
      state.channel_streamURL = d[c_id]["stream_url"];
    } else {
      state.channel_name = "";
      state.channel_frequency = undefined;
      state.channel_system = "";
      state.current_talkgroupId = 0;
      state.channel_tag = "";
      state.channel_sourceAddress = 0;
      state.channel_sourceTag = "";
      state.channel_streamURL = "";
    }
    //channel_status();
  }
};
