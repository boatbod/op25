import { useState } from "react";
import { useAppSelector } from "redux/app/hooks";
import { selectSystem } from "redux/slices/op25/op25Slice";
import { selectIsDarkMode } from "redux/slices/preferences/preferencesSlice";
import { frequencyToString } from "lib/op25";

import {
  Card,
  CardContent,
  Theme,
  Typography,
  IconButton,
  CardHeader,
  createStyles,
  makeStyles,
  Grid,
  Icon,
  Hidden,
  useMediaQuery,
  useTheme,
} from "@material-ui/core";

import {
  FiMinimize2 as MinimizeIcon,
  FiMaximize2 as MaximizeIcon,
  FiRadio as RadioIcon,
} from "react-icons/fi";
import { formatDuration, intervalToDuration, sub } from "date-fns";

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
    cardHeaderActions: {
      display: "block",
      marginTop: -15,
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
      borderTopColor: (props: useStylesProps) =>
        props.isDarkMode ? "#666666" : "#CCCCCC",
    },
    tableInfo: {
      borderSpacing: 0,
      borderTopWidth: 1,
      borderTopStyle: "solid",
      borderTopColor: (props: useStylesProps) =>
        props.isDarkMode ? "#666666" : "#CCCCCC",
      [theme.breakpoints.up("lg")]: {
        width: "100%",
      },
    },
    tr: {
      "&:hover": {
        backgroundColor: (props: useStylesProps) =>
          props.isDarkMode ? "#515151" : "#F5F5F5",
      },
    },
    td: {
      borderBottomWidth: 1,
      borderBottomStyle: "solid",
      borderBottomColor: (props: useStylesProps) =>
        props.isDarkMode ? "#666666" : "#CCCCCC",
      paddingTop: 15,
      paddingBottom: 15,
      paddingLeft: 10,
      paddingRight: 10,
    },
    tdFrequency: {
      borderBottomWidth: 1,
      borderBottomStyle: "solid",
      borderBottomColor: (props: useStylesProps) =>
        props.isDarkMode ? "#666666" : "#CCCCCC",
      paddingTop: 5,
      paddingBottom: 5,
      paddingLeft: 10,
      paddingRight: 10,
      textAlign: "center",
    },
    tdName: {
      width: 110,
      borderBottomWidth: 1,
      borderBottomStyle: "solid",
      borderBottomColor: (props: useStylesProps) =>
        props.isDarkMode ? "#666666" : "#CCCCCC",
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
  const theme = useTheme();
  const isMediumUpScreen = useMediaQuery(theme.breakpoints.up("md"));
  const system = useAppSelector(selectSystem(systemId));
  const isDarkMode = useAppSelector(selectIsDarkMode);
  const [minimized, setMinimized] = useState(false);
  const classes = useStyles({
    isDarkMode,
  });

  const getCardHeaderText = (): string => {
    if (minimized) {
      if (system) {
        if (!isMediumUpScreen) {
          return system.name ? system.name : "-";
        } else {
          return system.name || system.TopLine
            ? `${system.name ? `${system.name} / ` : ""}${
                system.TopLine ? system.TopLine : "-"
              }`
            : "-";
        }
      } else {
        return "-";
      }
    } else {
      return system ? (system.name ? system.name : "-") : "-";
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

  const toggleMinimized = () => {
    setMinimized(!minimized);
  };

  return (
    <Card
      className={`${classes.root}${
        className !== undefined ? ` ${className}` : ""
      }`}
      variant="outlined"
    >
      <CardHeader
        title={getCardHeaderText()}
        action={
          <span className={classes.cardHeaderActions}>
            <IconButton onClick={toggleMinimized}>
              {minimized ? <MaximizeIcon /> : <MinimizeIcon />}
            </IconButton>
          </span>
        }
        className={classes.cardHeader}
        titleTypographyProps={{ variant: "subtitle2" }}
      />
      {!minimized && (
        <CardContent className={classes.cardContent}>
          <Typography
            className={classes.currentsystem}
            variant="caption"
            component="h2"
          >
            {system && system.TopLine ? system.TopLine : "-"}
          </Typography>
          <div className={classes.grid}>
            <Grid container justifyContent="center" spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography
                  className={classes.tableInfo}
                  variant="caption"
                  component="table"
                >
                  <tbody>
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
                          ? `${system.stid
                              .toString()
                              .padStart(3, "0")} (${system.stid
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
                      <td className={classes.tdName}>Secondary CC:</td>
                      <td className={classes.td}>
                        {system && system.secondaryFrequencies
                          ? system.secondaryFrequencies.map((freq, index) =>
                              index > 0
                                ? `, ${frequencyToString(freq)}`
                                : frequencyToString(freq)
                            )
                          : "-"}
                      </td>
                    </tr>
                  </tbody>
                </Typography>
              </Grid>
              <Grid item xs={12} lg={6}>
                <Typography
                  className={classes.table}
                  variant="caption"
                  component="table"
                >
                  <thead>
                    <tr className={classes.tr}>
                      <th className={classes.td}>Voice Frequency:</th>
                      <th className={classes.td}>Last Used:</th>
                      <th className={classes.td}>Active Talkgroup ID(s):</th>
                      <th className={classes.td}>Count:</th>
                    </tr>
                  </thead>
                  <tbody>
                    {system?.frequencies?.map((frequency) => (
                      <tr key={frequency.frequency} className={classes.tr}>
                        <td className={classes.tdFrequency}>
                          <Grid
                            container
                            justifyContent="space-around"
                            alignItems="center"
                            spacing={2}
                          >
                            <Hidden smDown>
                              <Grid item>
                                <Icon>
                                  <RadioIcon />
                                </Icon>
                              </Grid>
                            </Hidden>
                            <Grid item>
                              {frequencyToString(frequency.frequency)}
                            </Grid>
                          </Grid>
                        </td>
                        <td className={classes.tdFrequency}>
                          {frequency.lastActivitySeconds
                            ? formatDuration(
                                intervalToDuration({
                                  start: sub(new Date(Date.now()), {
                                    seconds: frequency.lastActivitySeconds,
                                  }),
                                  end: new Date(Date.now()),
                                }),
                                {
                                  format: [
                                    "years",
                                    "days",
                                    "hours",
                                    "minutes",
                                    "seconds",
                                  ],
                                }
                              )
                            : "-"}
                        </td>
                        <td className={classes.tdFrequency}>
                          {frequency.talkgroups
                            ?.filter(
                              (tg, index, arry) =>
                                index === 0 ||
                                arry.findIndex((t) => t.id === tg.id) === -1
                            )
                            .map((tg, index) =>
                              tg.id
                                ? index > 0
                                  ? ` / [ ${tg.id.toString()} ]`
                                  : `[ ${tg.id.toString()} ]`
                                : "-"
                            )}
                        </td>
                        <td className={classes.tdFrequency}>
                          {frequency.counter && frequency.counter > 0
                            ? frequency.counter.toString()
                            : "00"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Typography>
              </Grid>
            </Grid>
          </div>
        </CardContent>
      )}
    </Card>
  );
};

export default SystemDisplay;
