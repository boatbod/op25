import MenuDrawer from "./MenuDrawer";
import AppBarWithToolbar from "./AppBarWithToolbar";

import { createStyles, makeStyles } from "@material-ui/core";

const useStyles = makeStyles(() =>
  createStyles({
    root: {
      display: "flex",
    },
  })
);

const TopMenuBar = () => {
  const classes = useStyles();

  return (
    <div className={classes.root}>
      <AppBarWithToolbar />
      <MenuDrawer />
    </div>
  );
};

export default TopMenuBar;
