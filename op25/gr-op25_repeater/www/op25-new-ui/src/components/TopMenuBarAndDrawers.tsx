import AppBarWithToolbar from "./AppBarWithToolbar";

import { createStyles, makeStyles } from "@material-ui/core";

const useStyles = makeStyles(() =>
  createStyles({
    root: {
      display: "flex",
    },
  })
);

const TopMenuBarAndDrawers = () => {
  const classes = useStyles();

  return (
    <div className={classes.root}>
      <AppBarWithToolbar />
    </div>
  );
};

export default TopMenuBarAndDrawers;
