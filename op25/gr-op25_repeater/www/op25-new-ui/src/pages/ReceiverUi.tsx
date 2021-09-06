import MainHUD from "components/MainHUD";
import { frequencyToString, ppmToString } from "lib/op25";
import { useAppSelector } from "redux/app/hooks";
import { isMenuDrawerOpen } from "redux/slices/interface/interfaceSlice";
import { selectAllState } from "redux/slices/op25/op25Slice";

import { createStyles, makeStyles, Theme } from "@material-ui/core";

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    tempDebugContent: {
      marginTop: 50,
    },
  })
);

const MainUi = () => {
  const state = useAppSelector(selectAllState);
  const isOpen = useAppSelector(isMenuDrawerOpen);
  const classes = useStyles({ isOpen });

  return (
    <>
      <MainHUD />
      <div className={classes.tempDebugContent}>
        channel_frequency:{" "}
        {state.channel_frequency && frequencyToString(state.channel_frequency)}
      </div>
      <div>channel_index: {state.channel_index}</div>
      <div>channel_list: {state.channel_list}</div>
      <div>channel_name: {state.channel_name}</div>
      <div>
        channel_ppm: {state.channel_ppm && ppmToString(state.channel_ppm)}
      </div>
      <div>channel_sourceAddress: {state.channel_sourceAddress}</div>
      <div>channel_sourceTag: {state.channel_sourceTag}</div>
      <div>channel_streamURL: {state.channel_streamURL}</div>
      <div>channel_system: {state.channel_system}</div>
      <div>channel_tag: {state.channel_tag}</div>
      <div>current_talkgroupId: {state.current_talkgroupId}</div>
      <div>stepSizeLarge: {state.stepSizeLarge}</div>
      <div>stepSizeSmall: {state.stepSizeSmall}</div>
    </>
  );
};

export default MainUi;
