import { InterfaceState } from "../../../models/InterfaceState";
import interfaceReducer, { gotoTalkgroup } from "./interfaceSlice";

describe("counter reducer", () => {
  const initialState: InterfaceState = {
    activeFrequency: undefined,
    activeTalkgroup: undefined,
    activeGroupAddress: undefined,
    activeSourceAddress: undefined,
  };
  it("should handle initial state", () => {
    expect(interfaceReducer(undefined, { type: "unknown" })).toEqual({
      activeFrequency: undefined,
      activeTalkgroup: undefined,
      activeGroupAddress: undefined,
      activeSourceAddress: undefined,
    });
  });

  it("should handle going to a talkgroup", () => {
    const actual = interfaceReducer(initialState, gotoTalkgroup(123));
    expect(actual.activeTalkgroup).toEqual("123");
  });
});
