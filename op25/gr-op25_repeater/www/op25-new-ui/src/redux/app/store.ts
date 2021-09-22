import { configureStore, ThunkAction, Action } from "@reduxjs/toolkit";
import interfaceReducer from "../slices/interface/interfaceSlice";
import op25Reducer from "../slices/op25/op25Slice";
import preferencesReducer from "../slices/preferences/preferencesSlice";

export const store = configureStore({
  reducer: {
    interface: interfaceReducer,
    op25: op25Reducer,
    preferences: preferencesReducer,
  },
});

export const dummyData: RootState = {
  interface: {
    isMenuDrawerOpen: true,
    isMobileMenuDrawerOpen: false,
    isPreferencesDrawerOpen: false,
  },
  preferences: {
    darkmode: true,
  },
  op25: {
    isConnected: false,
    channels: [
      {
        id: 1,
        encrypted: false,
        frequency: 856250000,
        name: "Dummy Channel",
        ppm: 0,
        sourceAddress: 1234,
        sourceTag: "Dispatcher",
        systemName: "Dummy System",
        tdma: false,
        tgID: 123,
        tgTag: "Dummy Talkgroup",
      },
      {
        id: 2,
        encrypted: true,
        frequency: 856250000,
        name: "Acme Channel",
        ppm: 0,
        sourceAddress: 9876,
        sourceTag: "Roadrunner",
        systemName: "Acme Corp",
        tdma: true,
        tgID: 999,
        tgTag: "Acme Outdoors Secure Talkgroup",
      },
      {
        id: 3,
        encrypted: false,
        frequency: 856250000,
        name: "State Patrol Channel",
        ppm: 0,
        sourceAddress: 5463,
        sourceTag: "Trooper Allen",
        systemName: "Statewide System",
        tdma: true,
        tgID: 456,
        tgTag: "Section 1A Talkgroup",
      },
    ],
    systems: [],
    terminalConfig: undefined,
    send_queue: [{ command: "get_config", arg1: 0, arg2: 0 }],
  },
};

export const storeWithDummyData = configureStore({
  reducer: {
    interface: interfaceReducer,
    op25: op25Reducer,
    preferences: preferencesReducer,
  },
  preloadedState: dummyData,
});

export type AppDispatch = typeof store.dispatch;
export type RootState = ReturnType<typeof store.getState>;
export type AppThunk<ReturnType = void> = ThunkAction<
  ReturnType,
  RootState,
  unknown,
  Action<string>
>;

export type StoreType = typeof store;
