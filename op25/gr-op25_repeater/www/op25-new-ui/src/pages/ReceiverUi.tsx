import ChannelDisplay from "components/ChannelDisplay";
import { useAppSelector } from "redux/app/hooks";
import { selectChannels } from "redux/slices/op25/op25Slice";

import {
  createStyles,
  Grid,
  makeStyles,
  Theme,
  Typography,
} from "@material-ui/core";

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    headingText: {
      color: theme.palette.getContrastText(theme.palette.background.default),
      fontSize: "2em",
      marginBottom: 15,
    },
  })
);

const MainUi = () => {
  const classes = useStyles();
  const channels = useAppSelector(selectChannels);

  return (
    <>
      <Typography component="h1" className={classes.headingText}>
        Channels:
      </Typography>
      <Grid container spacing={2}>
        {channels.map((channel) => (
          <Grid item key={channel.id} xs={12} md={6}>
            <ChannelDisplay channelId={channel.id} />
          </Grid>
        ))}
      </Grid>
    </>
  );
};

export default MainUi;
