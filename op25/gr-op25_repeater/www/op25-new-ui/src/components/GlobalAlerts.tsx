import { Alert } from "@material-ui/lab";
import { useAppSelector } from "redux/app/hooks";
import { isConnected } from "redux/slices/op25/op25Slice";

import { makeStyles, createStyles, Theme } from "@material-ui/core";

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    root: {
      paddingBottom: 20,
    },
  })
);

const GlobalAlerts = () => {
  const isAppConnected = useAppSelector(isConnected);
  const classes = useStyles();

  return (
    <div className={classes.root}>
      {isAppConnected !== undefined && !isAppConnected && (
        <>
          <Alert variant="filled" severity="error">
            The OP25 web gui does not have a connection with the python HTTP
            server.
          </Alert>
        </>
      )}
    </div>
  );
};

export default GlobalAlerts;
