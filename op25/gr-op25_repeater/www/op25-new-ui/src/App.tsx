import { useEffect } from "react";
import TopMenuBarAndDrawers from "./components/TopMenuBarAndDrawers";
import { useAppDispatch, useAppSelector } from "redux/app/hooks";
import {
  selectAllState,
  addToSendQueue,
  sendQueue,
} from "redux/slices/op25/op25Slice";

import { createStyles, makeStyles, Theme } from "@material-ui/core";
import { isMenuDrawerOpen } from "redux/slices/interface/interfaceSlice";
import { frequencyToString, ppmToString } from "lib/op25";
interface useStylesProps {
  isOpen: boolean;
}

const drawerWidth = 240;

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    content: {
      marginTop: 20,
      [theme.breakpoints.down("xs")]: {
        marginLeft: 20,
      },
      [theme.breakpoints.up("sm")]: {
        marginLeft: (props: useStylesProps) => props.isOpen && drawerWidth + 25,
      },
    },
  })
);

const App = () => {
  const dispatch = useAppDispatch();
  const state = useAppSelector(selectAllState);
  const isOpen = useAppSelector(isMenuDrawerOpen);
  const classes = useStyles({ isOpen });

  useEffect(() => {
    dispatch(addToSendQueue({ command: "get_config", arg1: 0, arg2: 0 }));
    const updateTimer = setInterval(async () => {
      if (state.channel_list.length === 0) {
        await dispatch(addToSendQueue({ command: "update", arg1: 0, arg2: 0 }));
        dispatch(sendQueue());
      } else {
        await dispatch(
          addToSendQueue({
            command: "update",
            arg1: 0,
            arg2: Number(state.channel_list[state.channel_index]),
          })
        );
        dispatch(sendQueue());
      }
    }, 1000);

    return () => {
      clearInterval(updateTimer);
    };

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <TopMenuBarAndDrawers />
      <div className={classes.content}>
        <div>
          channel_frequency:{" "}
          {state.channel_frequency &&
            frequencyToString(state.channel_frequency)}
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
      </div>
    </>
  );
};

export default App;
