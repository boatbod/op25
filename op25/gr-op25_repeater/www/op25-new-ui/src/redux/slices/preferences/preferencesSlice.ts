import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { RootState } from "../../app/store";
import { PreferencesState } from "../../../types/PreferencesState";

export const initialState: PreferencesState = {
  darkmode: true,
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
  },
});

export const { toogleDarkMode, setDarkMode } = preferencesSlice.actions;

export const selectIsDarkMode = (state: RootState) =>
  state.preferences.darkmode;

export default preferencesSlice.reducer;
