import interfaceReducer, {
  initialState,
  setMenuDrawerOpen,
  toggleMenuDrawerOpen,
  toggleMobileMenuDrawerOpen,
  setMobileMenuDrawerOpen,
  togglePreferencesDrawerOpen,
  setPreferencesDrawerOpen,
} from "../interfaceSlice";

describe("interface reducer", () => {
  describe("menu drawer", () => {
    it("should handle toggling open and close", () => {
      const doAction = interfaceReducer(initialState, toggleMenuDrawerOpen());
      expect(doAction.isMenuDrawerOpen).toEqual(!initialState.isMenuDrawerOpen);
    });

    it("should handle opening", () => {
      const doAction = interfaceReducer(initialState, setMenuDrawerOpen(true));
      expect(doAction.isMenuDrawerOpen).toEqual(true);
    });

    it("should handle closing", () => {
      const doAction = interfaceReducer(initialState, setMenuDrawerOpen(false));
      expect(doAction.isMenuDrawerOpen).toEqual(false);
    });
  });

  describe("mobile menu drawer", () => {
    it("should handle toggling open and close", () => {
      const doAction = interfaceReducer(
        initialState,
        toggleMobileMenuDrawerOpen()
      );
      expect(doAction.isMobileMenuDrawerOpen).toEqual(
        !initialState.isMobileMenuDrawerOpen
      );
    });

    it("should handle opening", () => {
      const doAction = interfaceReducer(
        initialState,
        setMobileMenuDrawerOpen(true)
      );
      expect(doAction.isMobileMenuDrawerOpen).toEqual(true);
    });

    it("should handle closing", () => {
      const doAction = interfaceReducer(
        initialState,
        setMobileMenuDrawerOpen(false)
      );
      expect(doAction.isMobileMenuDrawerOpen).toEqual(false);
    });
  });

  describe("preferences drawer", () => {
    it("should handle toggling open and close", () => {
      const doAction = interfaceReducer(
        initialState,
        togglePreferencesDrawerOpen()
      );
      expect(doAction.isPreferencesDrawerOpen).toEqual(
        !initialState.isPreferencesDrawerOpen
      );
    });

    it("should handle opening", () => {
      const doAction = interfaceReducer(
        initialState,
        setPreferencesDrawerOpen(true)
      );
      expect(doAction.isPreferencesDrawerOpen).toEqual(true);
    });

    it("should handle closing", () => {
      const doAction = interfaceReducer(
        initialState,
        setPreferencesDrawerOpen(false)
      );
      expect(doAction.isPreferencesDrawerOpen).toEqual(false);
    });
  });
});
