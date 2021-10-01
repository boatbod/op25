import { useAppDispatch, useAppSelector } from "../redux/app/hooks";
import {
  isPreferencesOpen,
  setPreferencesDrawerOpen,
} from "../redux/slices/interface/interfaceSlice";
import {
  selectIsDarkMode,
  setDarkMode,
} from "../redux/slices/preferences/preferencesSlice";

import {
  AppBar,
  createStyles,
  Divider,
  FormControlLabel,
  FormGroup,
  Grid,
  IconButton,
  makeStyles,
  SwipeableDrawer,
  Switch,
  Theme,
  Toolbar,
  Typography,
  useTheme,
} from "@material-ui/core";

import { Close as CloseIcon } from "@material-ui/icons";

import { blue } from "@material-ui/core/colors";

const drawerWidth = 300;

interface StylesProps {
  isDarkMode: boolean;
}

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    appBar: {
      [theme.breakpoints.up("sm")]: {
        width: `${drawerWidth}px`,
      },
    },
    drawer: {
      [theme.breakpoints.up("sm")]: {
        width: drawerWidth,
        flexShrink: 0,
      },
    },
    gridSpace: {
      paddingLeft: theme.spacing(2),
    },
    drawerPaper: {
      width: drawerWidth,
    },
    preferencesHeader: {
      color: (props: StylesProps) =>
        props.isDarkMode ? theme.palette.common.white : blue[800],
    },
    checkboxMaxWidth: {
      width: 180,
    },
    toolbar: theme.mixins.toolbar, // necessary for content to be below app bar
  })
);

const container =
  globalThis !== undefined ? () => globalThis.document.body : undefined;

const PreferencesDrawer = () => {
  const dispatch = useAppDispatch();
  const isOpen = useAppSelector(isPreferencesOpen);
  const isDarkMode = useAppSelector(selectIsDarkMode);
  const classes = useStyles({ isDarkMode });
  const theme = useTheme();

  return (
    <nav className={classes.drawer}>
      <SwipeableDrawer
        container={container}
        variant="temporary"
        anchor={theme.direction === "rtl" ? "left" : "right"}
        open={isOpen}
        onClose={() => {
          dispatch(setPreferencesDrawerOpen(false));
        }}
        onOpen={() => {
          dispatch(setPreferencesDrawerOpen(true));
        }}
        classes={{
          paper: classes.drawerPaper,
        }}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile.
        }}
      >
        <AppBar
          position="relative"
          className={classes.appBar}
          color={isDarkMode ? "transparent" : "primary"}
        >
          <Toolbar></Toolbar>
        </AppBar>
        <Divider />
        <Grid className={classes.gridSpace} container spacing={0}>
          <Grid item xs={12}>
            <Grid container justifyContent="flex-end">
              <IconButton
                onClick={() => {
                  dispatch(setPreferencesDrawerOpen(false));
                }}
              >
                <CloseIcon />
              </IconButton>
            </Grid>
          </Grid>
          <Grid item xs={12}>
            <Typography className={classes.preferencesHeader} variant="h6">
              Theme
            </Typography>
          </Grid>
          <Grid item xs={12}>
            <FormGroup>
              <FormControlLabel
                control={
                  <Switch
                    checked={isDarkMode}
                    onChange={(e) => {
                      dispatch(setDarkMode(e.target.checked));
                    }}
                    name="darkModeEnabled"
                  />
                }
                label="Dark Mode"
              />
            </FormGroup>
          </Grid>
        </Grid>
      </SwipeableDrawer>
    </nav>
  );
};

export default PreferencesDrawer;
