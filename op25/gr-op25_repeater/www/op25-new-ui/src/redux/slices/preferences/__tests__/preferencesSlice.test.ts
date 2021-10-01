import preferencesReducer, {
  initialState,
  setDarkMode,
  toogleDarkMode,
} from "../preferencesSlice";

describe("preferences reducer", () => {
  describe("dark mode", () => {
    it("should handle toggling on and off", () => {
      const doAction = preferencesReducer(initialState, toogleDarkMode());
      expect(doAction.darkmode).toEqual(!initialState.darkmode);
    });

    it("should handle being enabled", () => {
      const doAction = preferencesReducer(initialState, setDarkMode(true));
      expect(doAction.darkmode).toEqual(true);
    });

    it("should handle being disabled", () => {
      const doAction = preferencesReducer(initialState, setDarkMode(false));
      expect(doAction.darkmode).toEqual(false);
    });
  });
});
