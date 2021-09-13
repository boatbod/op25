import { useAppSelector } from "redux/app/hooks";
import { selectSystem } from "redux/slices/op25/op25Slice";
import { selectIsDarkMode } from "redux/slices/preferences/preferencesSlice";
import { frequencyToString } from "lib/op25";

import {
  Card,
  CardContent,
  Theme,
  Typography,
  CardHeader,
  createStyles,
  makeStyles,
} from "@material-ui/core";

type SystemDisplayProps = {
  className?: string | undefined;
  systemId: number;
};

type useStylesProps = {
  isDarkMode: boolean;
};

const useStyles = makeStyles((theme: Theme) =>
  createStyles({
    root: {
      minWidth: 275,
      border: "0",
    },
    cardContent: {
      paddingRight: 15,
      borderLeftStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderRightStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderWidth: 1,
    },
    cardHeader: {
      backgroundColor: theme.palette.primary.main,
      borderLeftStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderRightStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderTopStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderWidth: 1,
      borderColor: theme.palette.primary.main,
      margin: "0",
      textAlign: "center",
      height: 30,
      color: theme.palette.primary.contrastText,
    },
    currentsystem: {
      marginLeft: 15,
      marginBottom: 20,
      overflow: "auto",
      textAlign: "center",
    },
    table: {
      width: "100%",
      borderSpacing: 0,
      borderTopWidth: 1,
      borderTopStyle: "solid",
      borderTopColor: "#666666",
    },
    tr: {
      "&:hover": {
        backgroundColor: "#515151",
      },
    },
    td: {
      borderBottomWidth: 1,
      borderBottomStyle: "solid",
      borderBottomColor: "#666666",
      paddingTop: 15,
      paddingBottom: 15,
      paddingLeft: 10,
      paddingRight: 10,
    },
    tdName: {
      width: 110,
      borderBottomWidth: 1,
      borderBottomStyle: "solid",
      borderBottomColor: "#666666",
      paddingTop: 15,
      paddingBottom: 15,
      textAlign: "right",
    },
    grid: {
      minHeight: 260,
    },
    cardActions: {
      paddingBottom: 20,
      borderLeftStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderRightStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderBottomStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderWidth: 1,
      flexWrap: "wrap",
      justifyContent: "center",
    },
    actionbuttons: {
      paddingLeft: 15,
      paddingRight: 15,
    },
  })
);

const SystemDisplay = ({ className, systemId }: SystemDisplayProps) => {
  const system = useAppSelector(selectSystem(systemId));
  const isDarkMode = useAppSelector(selectIsDarkMode);
  const classes = useStyles({
    isDarkMode,
  });

  const getCardHeaderText = (): string => {
    if (system) {
      return system.name ? system.name : "-";
    } else {
      return "-";
    }
  };

  const systemFrequency = system ? (
    <span>
      {system.rxFrequency ? frequencyToString(system.rxFrequency) : "-"}{" "}
      &nbsp;/&nbsp;{" "}
      {system.txFrequency ? frequencyToString(system.txFrequency) : "-"}
    </span>
  ) : (
    <span>&ndash;</span>
  );

  return (
    <Card
      className={`${classes.root}${
        className !== undefined ? ` ${className}` : ""
      }`}
      variant="outlined"
    >
      <CardHeader
        title={getCardHeaderText()}
        className={classes.cardHeader}
        titleTypographyProps={{ variant: "subtitle2" }}
      />
      <CardContent className={classes.cardContent}>
        <Typography
          className={classes.currentsystem}
          variant="caption"
          component="h2"
        >
          {system && system.TopLine ? system.TopLine : "-"}
        </Typography>
        <div className={classes.grid}>
          <Typography
            className={classes.table}
            variant="caption"
            component="table"
          >
            <tr className={classes.tr}>
              <td className={classes.tdName}>WACN:</td>
              <td className={classes.td}>
                {system && system.wacn
                  ? `0x${system.wacn.toString(16).toUpperCase()}`
                  : "-"}
              </td>
            </tr>
            <tr className={classes.tr}>
              <td className={classes.tdName}>System ID:</td>
              <td className={classes.td}>
                {system && system.syid
                  ? `0x${system.syid.toString(16).toUpperCase()}`
                  : "-"}
              </td>
            </tr>
            <tr className={classes.tr}>
              <td className={classes.tdName}>NAC:</td>
              <td className={classes.td}>
                {system && system.nac
                  ? `0x${system.nac.toString(16).toUpperCase()}`
                  : "-"}
              </td>
            </tr>
            <tr className={classes.tr}>
              <td className={classes.tdName}>RFSS/Site:</td>
              <td className={classes.td}>
                {system && system.rfid
                  ? `${system.rfid.toString()} (${system.rfid
                      .toString(16)
                      .toUpperCase()})`
                  : "-"}{" "}
                &nbsp;/&nbsp;
                {system && system.stid
                  ? `${system.stid.toString().padStart(3, "0")} (${system.stid
                      .toString(16)
                      .toUpperCase()})`
                  : "-"}
              </td>
            </tr>
            <tr className={classes.tr}>
              <td className={classes.tdName}>Rx/Tx Frequency:</td>
              <td className={classes.td}>{systemFrequency}</td>
            </tr>
            <tr className={classes.tr}>
              <td className={classes.tdName}>Test:</td>
              <td className={classes.td}>
                {system && system.nac
                  ? `${system.nac.toString()} || 0x${system.nac
                      .toString(16)
                      .toUpperCase()}`
                  : "-"}
              </td>
            </tr>
          </Typography>
        </div>
      </CardContent>
    </Card>
  );
};

export default SystemDisplay;
