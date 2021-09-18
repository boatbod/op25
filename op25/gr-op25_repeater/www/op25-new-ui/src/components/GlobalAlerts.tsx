import { SyntheticEvent, useEffect, useState } from "react";
import { Alert } from "@material-ui/lab";
import { useAppSelector } from "redux/app/hooks";
import { getSystemsCount, isConnected } from "redux/slices/op25/op25Slice";

import { makeStyles, createStyles, Theme, Snackbar } from "@material-ui/core";
import { AXIOS_BASE_URL } from "utils/axios";

const useStyles = makeStyles((_theme: Theme) =>
  createStyles({
    spaced: {
      marginBottom: 20,
    },
  })
);

const GlobalAlerts = () => {
  const [snackbarReconnectedOpen, setSnackbarReconnectedOpen] = useState(false);
  const [holdAlerts, setHoldAlerts] = useState(true);
  const isAppConnected = useAppSelector(isConnected);
  const systemsCount = useAppSelector(getSystemsCount);
  const classes = useStyles();

  const openSnackbarReconnected = () => {
    setSnackbarReconnectedOpen(true);
  };

  const closeSnackbarReconnected = () => {
    setSnackbarReconnectedOpen(false);
  };

  useEffect(() => {
    if (isAppConnected && !holdAlerts) {
      openSnackbarReconnected();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAppConnected]);

  useEffect(() => {
    // This prevents messages/alerts when the interface is first loaded.
    setTimeout(() => {
      setHoldAlerts(false);
    }, 5000);
  }, []);

  const handleSnackbarReconnectedClose = (
    _event?: SyntheticEvent,
    reason?: string
  ) => {
    if (reason === "clickaway") {
      return;
    }
    closeSnackbarReconnected();
  };

  return (
    <>
      {!holdAlerts && isAppConnected !== undefined && !isAppConnected && (
        <Alert className={classes.spaced} variant="filled" severity="error">
          The OP25 web interface does not have a connection with the Python HTTP
          server. Address attempted is: {AXIOS_BASE_URL}
        </Alert>
      )}
      {!holdAlerts && isAppConnected && systemsCount === 0 && (
        <Alert className={classes.spaced} variant="outlined" severity="error">
          There are no available systems. Check the logs for a control channel
          timeout.
        </Alert>
      )}
      {snackbarReconnectedOpen && (
        <Snackbar
          open={snackbarReconnectedOpen}
          autoHideDuration={6000}
          onClose={handleSnackbarReconnectedClose}
        >
          <Alert
            variant="filled"
            severity="success"
            onClose={handleSnackbarReconnectedClose}
          >
            OP25 web interface reconnected with Python HTTP server.
          </Alert>
        </Snackbar>
      )}
    </>
  );
};

export default GlobalAlerts;
