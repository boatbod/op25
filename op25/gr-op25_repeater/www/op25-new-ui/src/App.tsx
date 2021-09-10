import { useEffect } from "react";
import TopMenuBarAndDrawers from "./components/TopMenuBarAndDrawers";
import { useAppDispatch, useAppSelector } from "redux/app/hooks";
import { isMenuDrawerOpen } from "redux/slices/interface/interfaceSlice";
import ReceiverUi from "pages/ReceiverUi";
import { sendQueue } from "redux/slices/op25/op25Slice";

import { createStyles, makeStyles, Theme } from "@material-ui/core";
import { OP25 } from "lib/op25";

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
  const op25 = OP25.getInstance();
  const dispatch = useAppDispatch();
  const isOpen = useAppSelector(isMenuDrawerOpen);
  const classes = useStyles({ isOpen });

  useEffect(() => {
    const updateTimer = setInterval(async () => {
      op25.sendUpdateChannels();
    }, 1000);

    const sendQueueTimer = setInterval(async () => {
      await dispatch(sendQueue());
    }, 1000);

    return () => {
      clearInterval(updateTimer);
      clearInterval(sendQueueTimer);
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
