import { useEffect } from "react";
import TopMenuBarAndDrawers from "./components/TopMenuBarAndDrawers";
import { useAppDispatch, useAppSelector } from "redux/app/hooks";
import { isMenuDrawerOpen } from "redux/slices/interface/interfaceSlice";
import MainUi from "pages/ReceiverUi";
import {
  selectAllState,
  addToSendQueue,
  sendQueue,
} from "redux/slices/op25/op25Slice";

import { createStyles, makeStyles, Theme } from "@material-ui/core";
import { selectShowChannelInTitle } from "redux/slices/preferences/preferencesSlice";

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
        marginRight: 20,
      },
      [theme.breakpoints.up("sm")]: {
        marginLeft: (props: useStylesProps) => props.isOpen && drawerWidth + 25,
        marginRight: 25,
      },
    },
    tempDebugContent: {
      marginTop: 50,
    },
  })
);

const App = () => {
  const dispatch = useAppDispatch();
  const state = useAppSelector(selectAllState);
  const isOpen = useAppSelector(isMenuDrawerOpen);
  const showChannelInTitle = useAppSelector(selectShowChannelInTitle);
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

  useEffect(() => {
    if (showChannelInTitle) {
      document.title = `${
        (state.channel_tag
          ? state.channel_tag
          : state.current_talkgroupId?.toString()) + " - "
      }OP25 (Boatbod) Web Interface`;
    } else {
      document.title = "OP25 (Boatbod) Web Interface";
    }
  }, [showChannelInTitle, state.current_talkgroupId, state.channel_tag]);

  return (
    <>
      <TopMenuBarAndDrawers />
      <div className={classes.content}>
        <MainUi />
      </div>
    </>
  );
};

export default App;
