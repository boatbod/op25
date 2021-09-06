import { useEffect } from "react";
import TopMenuBarAndDrawers from "./components/TopMenuBarAndDrawers";
import { useAppDispatch, useAppSelector } from "redux/app/hooks";
import { isMenuDrawerOpen } from "redux/slices/interface/interfaceSlice";
import ReceiverUi from "pages/ReceiverUi";
import {
  addToSendQueue,
  selectChannels,
  sendQueue,
} from "redux/slices/op25/op25Slice";

import { createStyles, makeStyles, Theme } from "@material-ui/core";

interface useStylesProps {
  isOpen: boolean;
}

const drawerWidth = 240;

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    content: {
      width: "100%",
      [theme.breakpoints.down("xs")]: {
        paddingTop: 90,
        paddingBottom: 20,
        paddingLeft: 20,
        paddingRight: 20,
      },
      [theme.breakpoints.up("sm")]: {
        paddingLeft: (props: useStylesProps) =>
          props.isOpen && drawerWidth + 25,
        paddingTop: 90,
        paddingBottom: 25,
        paddingRight: 25,
      },
    },
    tempDebugContent: {
      marginTop: 50,
    },
  })
);

const App = () => {
  const dispatch = useAppDispatch();
  const channels = useAppSelector(selectChannels);
  const isOpen = useAppSelector(isMenuDrawerOpen);
  const classes = useStyles({ isOpen });

  useEffect(() => {
    dispatch(addToSendQueue({ command: "get_config", arg1: 0, arg2: 0 }));
    const updateTimer = setInterval(async () => {
      if (channels.length === 0) {
        await dispatch(addToSendQueue({ command: "update", arg1: 0, arg2: 0 }));
        dispatch(sendQueue());
      } else {
        channels.forEach(async (channel) => {
          await dispatch(
            addToSendQueue({
              command: "update",
              arg1: 0,
              arg2: channel.id,
            })
          );
        });
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
        <ReceiverUi />
      </div>
    </>
  );
};

export default App;
