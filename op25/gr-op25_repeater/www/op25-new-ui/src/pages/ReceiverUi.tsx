import ChannelDisplay from "components/ChannelDisplay";
import { useAppSelector } from "redux/app/hooks";
import { selectChannels, selectSystems } from "redux/slices/op25/op25Slice";
import SystemDisplay from "components/SystemDisplay";

import {
  createStyles,
  Grid,
  makeStyles,
  Theme,
  Typography,
} from "@material-ui/core";

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    channelsHeadingText: {
      color: theme.palette.getContrastText(theme.palette.background.default),
      fontSize: "2em",
      marginBottom: 15,
    },
    systemsHeadingText: {
      color: theme.palette.getContrastText(theme.palette.background.default),
      fontSize: "2em",
      marginTop: 50,
      marginBottom: 15,
    },
  })
);

const MainUi = () => {
  const classes = useStyles();
  const channels = useAppSelector(selectChannels);
  const systems = useAppSelector(selectSystems);

  return (
    <>
      <Typography component="h1" className={classes.channelsHeadingText}>
        Channels:
      </Typography>
      <Grid container spacing={2}>
        {channels.map((channel) => (
          <Grid item key={channel.id} xs={12} md={6}>
            <ChannelDisplay channelId={channel.id} />
          </Grid>
        ))}
      </Grid>
      <Typography component="h1" className={classes.systemsHeadingText}>
        Systems:
      </Typography>
      <Grid container spacing={2}>
        {systems.map((system) => (
          <Grid item key={system.id} xs={12}>
            <SystemDisplay systemId={system.id} />
          </Grid>
        ))}
      </Grid>
    </>
  );
};

export default MainUi;
