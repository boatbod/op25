import { useAppDispatch, useAppSelector } from "../redux/app/hooks";
import MenuDrawer from "./MenuDrawer";
import PreferencesDrawer from "./PreferencesDrawer";
import {
  isMenuDrawerOpen,
  toggleMenuDrawerOpen,
  toggleMobileMenuDrawerOpen,
  togglePreferencesDrawerOpen,
} from "../redux/slices/interface/interfaceSlice";

import {
  AppBar,
  createStyles,
  Hidden,
  IconButton,
  makeStyles,
  Theme,
  Toolbar,
  Tooltip,
} from "@material-ui/core";

import { Menu as MenuIcon, Settings as SettingsIcon } from "@material-ui/icons";

interface useStylesProps {
  isOpen: boolean;
}

const drawerWidth = 240;

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    grow: {
      flexGrow: 1,
    },
    appBar: {
      [theme.breakpoints.up("sm")]: {
        width: (props: useStylesProps) => (props.isOpen ? `calc(100%)` : ""),
        paddingLeft: (props: useStylesProps) => props.isOpen && drawerWidth,
      },
    },
    content: {
      flexGrow: 1,
      padding: theme.spacing(3),
    },
  })
);

const AppBarWithToolbar = () => {
  const dispatch = useAppDispatch();
  const isOpen = useAppSelector(isMenuDrawerOpen);
  const classes = useStyles({ isOpen });

  return (
    <AppBar position="fixed" className={classes.appBar}>
      <MenuDrawer />
      <Toolbar>
        <Hidden smUp>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={() => {
              dispatch(toggleMobileMenuDrawerOpen());
            }}
          >
            <MenuIcon />
          </IconButton>
        </Hidden>
        <Hidden xsDown>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={() => {
              dispatch(toggleMenuDrawerOpen());
            }}
          >
            <MenuIcon />
          </IconButton>
        </Hidden>
        <div className={classes.grow} />
        <Tooltip title="Preferences" aria-label="preferences">
          <IconButton
            color="inherit"
            aria-label="preferences"
            onClick={() => {
              dispatch(togglePreferencesDrawerOpen());
            }}
          >
            <SettingsIcon />
          </IconButton>
        </Tooltip>
      </Toolbar>
      <PreferencesDrawer />
    </AppBar>
  );
};

export default AppBarWithToolbar;
