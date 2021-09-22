import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { RootState } from "../../app/store";
import { InterfaceState } from "../../../types/InterfaceState";

export const initialState: InterfaceState = {
  isMenuDrawerOpen: true,
  isMobileMenuDrawerOpen: false,
  isPreferencesDrawerOpen: false,
};

export const interfaceSlice = createSlice({
  name: "interface",
  initialState,
  reducers: {
    toggleMenuDrawerOpen: (state) => {
      state.isMenuDrawerOpen = !state.isMenuDrawerOpen;
    },
    setMenuDrawerOpen: (state, action: PayloadAction<boolean>) => {
      state.isMenuDrawerOpen = action.payload;
    },
    toggleMobileMenuDrawerOpen: (state) => {
      state.isMobileMenuDrawerOpen = !state.isMobileMenuDrawerOpen;
    },
    setMobileMenuDrawerOpen: (state, action: PayloadAction<boolean>) => {
      state.isMobileMenuDrawerOpen = action.payload;
    },
    togglePreferencesDrawerOpen: (state) => {
      state.isPreferencesDrawerOpen = !state.isPreferencesDrawerOpen;
    },
    setPreferencesDrawerOpen: (state, action: PayloadAction<boolean>) => {
      state.isPreferencesDrawerOpen = action.payload;
    },
  },
});

export const {
  toggleMenuDrawerOpen,
  setMenuDrawerOpen,
  toggleMobileMenuDrawerOpen,
  setMobileMenuDrawerOpen,
  togglePreferencesDrawerOpen,
  setPreferencesDrawerOpen,
} = interfaceSlice.actions;

export const isMenuDrawerOpen = (state: RootState): boolean =>
  state.interface.isMenuDrawerOpen;

export const isMobileMenuDrawerOpen = (state: RootState): boolean =>
  state.interface.isMobileMenuDrawerOpen;

export const isPreferencesOpen = (state: RootState): boolean =>
  state.interface.isPreferencesDrawerOpen;

export default interfaceSlice.reducer;
