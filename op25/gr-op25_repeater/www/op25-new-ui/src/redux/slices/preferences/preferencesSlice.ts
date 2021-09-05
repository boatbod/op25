import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { RootState } from "../../app/store";
import { PreferencesState } from "../../../types/PreferencesState";

const initialState: PreferencesState = {
  darkmode: true,
  showChannelInTitle: true,
};

export const preferencesSlice = createSlice({
  name: "interface",
  initialState,
  reducers: {
    toogleDarkMode: (state) => {
      state.darkmode = !state.darkmode;
    },
    setDarkMode: (state, action: PayloadAction<boolean>) => {
      state.darkmode = action.payload;
    },
    toogleShowChannelInTitle: (state) => {
      state.showChannelInTitle = !state.showChannelInTitle;
    },
    setShowChannelInTitle: (state, action: PayloadAction<boolean>) => {
      state.showChannelInTitle = action.payload;
    },
  },
});

export const {
  toogleDarkMode,
  setDarkMode,
  toogleShowChannelInTitle,
  setShowChannelInTitle,
} = preferencesSlice.actions;

export const selectIsDarkMode = (state: RootState) =>
  state.preferences.darkmode;

export const selectShowChannelInTitle = (state: RootState) =>
  state.preferences.showChannelInTitle;

export default preferencesSlice.reducer;
