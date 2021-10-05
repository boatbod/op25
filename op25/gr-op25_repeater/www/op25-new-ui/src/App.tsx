import { useEffect } from "react";
import { BrowserRouter as Router, Switch, Route } from "react-router-dom";
import TopMenuBarAndDrawers from "./components/TopMenuBarAndDrawers";
import { useAppDispatch, useAppSelector } from "redux/app/hooks";
import { isMenuDrawerOpen } from "redux/slices/interface/interfaceSlice";
import ReceiverUi from "pages/ReceiverUi";
import { sendQueue } from "redux/slices/op25/op25Slice";
import { OP25 } from "lib/op25";
import GlobalAlerts from "components/GlobalAlerts";

import { createStyles, makeStyles, Theme } from "@material-ui/core";
import ScrollToTop from "components/ScrollToTop";

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

  const onChannelHoldTalkgroup = async (
    channelId: number,
    channelTgId: number
  ) => {
    await op25.sendHoldOnChannel(channelId, channelTgId);
  };

  // TODO: Create better prompt.
  const onGoToTalkgroup = async (channelId: number) => {
    const talkgroupId = prompt("Hold on what talkgroup ID?");
    if (talkgroupId) {
      await op25.sendHoldOnChannel(channelId, Number.parseInt(talkgroupId));
    }
  };

  const onReloadChannel = async (channelId: number) => {
    await op25.sendReloadOnChannel(channelId);
  };

  // TODO: Create better prompt.
  const onBlacklistTalkgroup = async (
    channelId: number,
    channelTgId: number
  ) => {
    const talkgroupId = prompt(
      "Blacklist what talkgroup ID?",
      channelTgId.toString()
    );
    if (talkgroupId) {
      await op25.sendBlacklistOnChannel(
        channelId,
        Number.parseInt(talkgroupId)
      );
    }
  };

  // TODO: Create better prompt.
  const onWhitelistTalkgroup = async (
    channelId: number,
    channelTgId: number
  ) => {
    const talkgroupId = prompt(
      "Whitelist what talkgroup ID?",
      channelTgId.toString()
    );
    if (talkgroupId) {
      await op25.sendWhitelistOnChannel(
        channelId,
        Number.parseInt(talkgroupId)
      );
    }
  };

  // TODO: Create better prompt.
  const onLogVerboseChange = async (channelId: number) => {
    const verboseLevel = prompt("What log verbose level?");
    if (verboseLevel) {
      await op25.sendSetDebugOnChannel(
        channelId,
        Number.parseInt(verboseLevel)
      );
    }
  };
  const onSkipTalkgroup = async (channelId: number) => {
    await op25.sendSkipOnChannel(channelId);
  };

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
    <Router>
      <TopMenuBarAndDrawers />
      <div className={classes.content}>
        <GlobalAlerts />
        <Switch>
          <Route path="/" exact>
            <ScrollToTop />
            <ReceiverUi
              onChannelHoldTalkgroup={onChannelHoldTalkgroup}
              onGoToTalkgroup={onGoToTalkgroup}
              onReloadChannel={onReloadChannel}
              onBlacklistTalkgroup={onBlacklistTalkgroup}
              onWhitelistTalkgroup={onWhitelistTalkgroup}
              onLogVerboseChange={onLogVerboseChange}
              onSkipTalkgroup={onSkipTalkgroup}
            />
          </Route>
        </Switch>
      </div>
    </Router>
  );
};

export default App;
