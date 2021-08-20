import MenuDrawer from "./MenuDrawer";
import AppBarWithToolbar from "./AppBarWithToolbar";

import { createStyles, makeStyles } from "@material-ui/core";
import PreferencesDrawer from "./PreferencesDrawer";

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
      <MenuDrawer />
      <PreferencesDrawer />
    </div>
  );
};

export default TopMenuBarAndDrawers;
