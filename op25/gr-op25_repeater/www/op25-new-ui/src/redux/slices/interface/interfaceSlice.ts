import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { RootState } from "../../app/store";
import { ActiveCall } from "../../../models/ActiveCall";
import { InterfaceState } from "../../../models/InterfaceState";

const initialState: InterfaceState = {
  activeFrequency: undefined,
  activeTalkgroup: undefined,
  activeGroupAddress: undefined,
  activeSourceAddress: undefined,
  isMenuDrawerOpen: true,
  isMobileMenuDrawerOpen: false,
};

export const interfaceSlice = createSlice({
  name: "interface",
  initialState,
  reducers: {
    gotoTalkgroup: (state, action: PayloadAction<number>) => {
      // TODO: Change to async thunk and call API.
      state.activeTalkgroup = action.payload.toString(10);
    },
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
  },
});

export const {
  gotoTalkgroup,
  toggleMenuDrawerOpen,
  setMenuDrawerOpen,
  toggleMobileMenuDrawerOpen,
  setMobileMenuDrawerOpen,
} = interfaceSlice.actions;

export const selectActiveCall = (state: RootState): ActiveCall => ({
  activeFrequency: state.interface.activeFrequency,
  activeTalkgroup: state.interface.activeTalkgroup,
  activeGroupAddress: state.interface.activeGroupAddress,
  activeSourceAddress: state.interface.activeSourceAddress,
});

export const isMenuDrawerOpen = (state: RootState): boolean =>
  state.interface.isMenuDrawerOpen;

export const isMobileMenuDrawerOpen = (state: RootState): boolean =>
  state.interface.isMobileMenuDrawerOpen;

export default interfaceSlice.reducer;
