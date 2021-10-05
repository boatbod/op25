import { NavLink } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "../redux/app/hooks";
import { selectIsDarkMode } from "../redux/slices/preferences/preferencesSlice";

import {
  isMenuDrawerOpen,
  isMobileMenuDrawerOpen,
  setMenuDrawerOpen,
  setMobileMenuDrawerOpen,
} from "../redux/slices/interface/interfaceSlice";

import {
  AppBar,
  createStyles,
  Divider,
  Drawer,
  Hidden,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  makeStyles,
  SwipeableDrawer,
  Theme,
  Toolbar,
  Typography,
  useTheme,
} from "@material-ui/core";

import {
  Home as HomeIcon,
  PieChart as PieChartIcon,
  InfoRounded as InfoRoundedIcon,
  Build as BuildIcon,
  History as HistoryIcon,
} from "@material-ui/icons";

const drawerWidth = 240;

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    drawer: {
      [theme.breakpoints.up("sm")]: {
        width: drawerWidth,
        flexShrink: 0,
      },
    },

    drawerPaper: {
      width: drawerWidth,
    },
    // necessary for content to be below app bar
    toolbar: theme.mixins.toolbar,
  })
);

const MenuDrawerContent = () => {
  const isDarkMode = useAppSelector(selectIsDarkMode);

  return (
    <div>
      <AppBar
        position="relative"
        color={isDarkMode ? "transparent" : "primary"}
      >
        <Toolbar>
          <Typography variant="h6" noWrap>
            OP25 (Boatbod)
          </Typography>
        </Toolbar>
      </AppBar>
      <Divider />
      <List>
        <ListItem
          button
          component={NavLink}
          to="/"
          activeClassName="Mui-selected"
          exact
        >
          <ListItemIcon>
            <HomeIcon />
          </ListItemIcon>
          <ListItemText>Receiver</ListItemText>
        </ListItem>
        <ListItem
          button
          component={NavLink}
          to="/history"
          activeClassName="Mui-selected"
        >
          <ListItemIcon>
            <HistoryIcon />
          </ListItemIcon>
          <ListItemText>History</ListItemText>
        </ListItem>
        <ListItem
          button
          component={NavLink}
          to="/config"
          activeClassName="Mui-selected"
        >
          <ListItemIcon>
            <BuildIcon />
          </ListItemIcon>
          <ListItemText>Config</ListItemText>
        </ListItem>
        <ListItem
          button
          component={NavLink}
          to="/plot"
          activeClassName="Mui-selected"
        >
          <ListItemIcon>
            <PieChartIcon />
          </ListItemIcon>
          <ListItemText>Plot</ListItemText>
        </ListItem>
      </List>
      <Divider />
      <List>
        <ListItem
          button
          component={NavLink}
          to="/about"
          activeClassName="Mui-selected"
        >
          <ListItemIcon>
            <InfoRoundedIcon />
          </ListItemIcon>
          <ListItemText>About</ListItemText>
        </ListItem>
      </List>
    </div>
  );
};

const container =
  globalThis !== undefined ? () => globalThis.document.body : undefined;

const MenuDrawer = () => {
  const dispatch = useAppDispatch();
  const isOpen = useAppSelector(isMenuDrawerOpen);
  const mobileOpen = useAppSelector(isMobileMenuDrawerOpen);
  const classes = useStyles();
  const theme = useTheme();

  return (
    <nav className={classes.drawer}>
      <Hidden smUp implementation="css">
        <SwipeableDrawer
          container={container}
          variant="temporary"
          anchor={theme.direction === "rtl" ? "right" : "left"}
          open={mobileOpen}
          onOpen={() => {
            dispatch(setMobileMenuDrawerOpen(true));
          }}
          onClose={() => {
            dispatch(setMobileMenuDrawerOpen(false));
          }}
          classes={{
            paper: classes.drawerPaper,
          }}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
        >
          <MenuDrawerContent />
        </SwipeableDrawer>
      </Hidden>
      <Hidden xsDown implementation="css">
        <Drawer
          classes={{
            paper: classes.drawerPaper,
          }}
          variant="persistent"
          anchor={theme.direction === "rtl" ? "right" : "left"}
          open={isOpen}
          onClose={() => {
            dispatch(setMenuDrawerOpen(false));
          }}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
        >
          <MenuDrawerContent />
        </Drawer>
      </Hidden>
    </nav>
  );
};

export default MenuDrawer;
