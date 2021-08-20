import { useAppDispatch, useAppSelector } from "../redux/app/hooks";
import {
  isMenuDrawerOpen,
  toggleMenuDrawerOpen,
  toggleMobileMenuDrawerOpen,
} from "../redux/slices/interface/interfaceSlice";

import {
  AppBar,
  createStyles,
  IconButton,
  makeStyles,
  // MenuItem,
  Theme,
  Toolbar,
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
        width: (props: useStylesProps) =>
          props.isOpen && `calc(100% - ${drawerWidth}px)`,
        marginLeft: (props: useStylesProps) => props.isOpen && drawerWidth,
      },
    },
    menuButton: {
      marginRight: theme.spacing(2),
      [theme.breakpoints.down("md")]: {
        display: "none",
      },
    },
    mobileMenuButton: {
      marginRight: theme.spacing(2),
      [theme.breakpoints.up("sm")]: {
        display: "none",
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
      <Toolbar>
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
        {/* <MenuItem button>Skip</MenuItem>
        <MenuItem button>Hold</MenuItem>
        <MenuItem button>GoTo</MenuItem>
        <MenuItem button>LockOut</MenuItem> */}
        <div className={classes.grow} />
        <IconButton color="inherit" aria-label="preferences" onClick={() => {}}>
          <SettingsIcon />
        </IconButton>
      </Toolbar>
    </AppBar>
  );
};

export default AppBarWithToolbar;
