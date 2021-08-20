import { configureStore, ThunkAction, Action } from "@reduxjs/toolkit";
import interfaceReducer from "../slices/interface/interfaceSlice";
import preferencesReducer from "../slices/preferences/preferencesSlice";

export const store = configureStore({
  reducer: {
    interface: interfaceReducer,
    preferences: preferencesReducer,
  },
});

export type AppDispatch = typeof store.dispatch;
export type RootState = ReturnType<typeof store.getState>;
export type AppThunk<ReturnType = void> = ThunkAction<
  ReturnType,
  RootState,
  unknown,
  Action<string>
>;
