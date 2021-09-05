import { useAppDispatch, useAppSelector } from "../redux/app/hooks";
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
  // MenuItem,
  Theme,
  Toolbar,
  Tooltip,
  Typography,
} from "@material-ui/core";

import { Menu as MenuIcon, Settings as SettingsIcon } from "@material-ui/icons";
import { selectAllState } from "redux/slices/op25/op25Slice";

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
        width: (props: useStylesProps) =>
          props.isOpen && `calc(100% - ${drawerWidth}px)`,
        marginLeft: (props: useStylesProps) => props.isOpen && drawerWidth,
      },
    },
    menuButton: {
      marginRight: theme.spacing(2),
    },
    mobileMenuButton: {
      marginRight: theme.spacing(2),
    },
    content: {
      flexGrow: 1,
      padding: theme.spacing(3),
    },
  })
);

const AppBarWithToolbar = () => {
  const dispatch = useAppDispatch();
  const currentState = useAppSelector(selectAllState);
  const isOpen = useAppSelector(isMenuDrawerOpen);
  const classes = useStyles({ isOpen });

  return (
    <AppBar position="sticky" className={classes.appBar}>
      <Toolbar>
        <Hidden smUp>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={() => {
              dispatch(toggleMobileMenuDrawerOpen());
            }}
            className={classes.mobileMenuButton}
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
            className={classes.menuButton}
          >
            <MenuIcon />
          </IconButton>
        </Hidden>
        {/* <MenuItem button>Skip</MenuItem>
        <MenuItem button>Hold</MenuItem>
        <MenuItem button>GoTo</MenuItem>
        <MenuItem button>LockOut</MenuItem> */}
        <Typography>
          Current:{" "}
          {currentState.channel_sourceAddress &&
          currentState.current_talkgroupId
            ? currentState.channel_sourceAddress +
              " on " +
              currentState.current_talkgroupId
            : ""}{" "}
          ** {currentState.channel_tag}
        </Typography>
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
    </AppBar>
  );
};

export default AppBarWithToolbar;
