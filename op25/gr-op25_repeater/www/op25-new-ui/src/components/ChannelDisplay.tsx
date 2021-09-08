import { createStyles, makeStyles } from "@material-ui/core/styles";
import { useAppSelector } from "redux/app/hooks";
import { selectChannel, selectStepSizes } from "redux/slices/op25/op25Slice";
import { frequencyToString, OP25 } from "lib/op25";
import { DataGrid, GridColDef, GridRenderCellParams } from "@mui/x-data-grid";

import {
  Card,
  CardActions,
  CardContent,
  Button,
  Theme,
  Typography,
  IconButton,
  Tooltip,
  Grid,
  CardHeader,
} from "@material-ui/core";

import {
  FiChevronsLeft as DoubleArrowsLeftIcon,
  FiChevronLeft as ArrowLeftIcon,
  FiChevronsRight as DoubleArrowsRightIcon,
  FiChevronRight as ArrowRightIcon,
} from "react-icons/fi";
import { selectIsDarkMode } from "redux/slices/preferences/preferencesSlice";

type ChannelDisplayProps = {
  className?: string | undefined;
  channelId: number;
};

type useStylesProps = {
  isEncrypted: boolean;
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
      backgroundColor: (props: useStylesProps) =>
        props.isEncrypted ? "red" : theme.palette.primary.main,
      borderLeftStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderRightStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderTopStyle: (props: useStylesProps) =>
        props.isDarkMode ? "none" : "solid",
      borderWidth: 1,
      borderColor: (props: useStylesProps) =>
        props.isEncrypted ? "red" : theme.palette.primary.main,
      margin: "0",
      textAlign: "center",
      height: 30,
      color: theme.palette.primary.contrastText,
    },
    currentchannel: {
      marginLeft: 15,
      marginBottom: 20,
      overflow: "auto",
    },
    grid: {
      height: 210,
    },
    gridRoot: {
      fontSize: 12,
      border: "0",
    },
    rowRoot: {
      border: "0",
    },
    cellRoot: {
      paddingLeft: 5,
      paddingRight: 5,
      border: "0",
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

const ChannelDisplay = ({ className, channelId }: ChannelDisplayProps) => {
  const op25 = OP25.getInstance();
  const channel = useAppSelector(selectChannel(channelId));
  const isDarkMode = useAppSelector(selectIsDarkMode);
  const classes = useStyles({
    isEncrypted: channel ? channel.encrypted : false,
    isDarkMode,
  });
  const { stepSizeSmall, stepSizeLarge } = useAppSelector(selectStepSizes);

  const columns: GridColDef[] = [
    { field: "id", hide: true, sortable: false },
    {
      field: "stateName",
      align: "right",
      sortable: false,
      minWidth: 110,
      renderHeader: (_) => <></>,
      renderCell: (params: GridRenderCellParams) =>
        params.getValue(params.id, "description") ? (
          <Tooltip
            title={`${
              params.getValue(params.id, "description") &&
              params.getValue(params.id, "description")?.toString()
            }`}
            enterDelay={500}
            placement="right"
          >
            <span>{params.getValue(params.id, "stateName")}</span>
          </Tooltip>
        ) : (
          <span>{params.getValue(params.id, "stateName")}</span>
        ),
    },
    {
      field: "stateValue",
      align: "left",
      sortable: false,
      renderHeader: (_) => <></>,
    },
    { field: "description", hide: true, sortable: false },
  ];

  const rows = [
    {
      id: 1,
      stateName: "Group Address:",
      stateValue: channel && channel.tgID ? channel.tgID : "-",
      description:
        "Also known as the Talkgroup ID, this is the unique ID assigned to a group.",
    },
    {
      id: 2,
      stateName: "Source Address:",
      stateValue:
        channel && channel.sourceAddress ? channel.sourceAddress : "-",
      description: "ID of the person talking (Radio ID / Unit ID)",
    },
    {
      id: 3,
      stateName: "Frequency:",
      stateValue:
        channel && channel.frequency
          ? frequencyToString(channel.frequency)
          : "-",
    },
    {
      id: 4,
      stateName: "Encrypted:",
      stateValue: channel ? (channel.encrypted ? "Yes" : "No") : "-",
      description:
        "Shows as yes if this channel is encrpyted (false positives do occur)",
    },
  ];

  const getCardHeaderText = (): string => {
    if (channel) {
      if (channel.name && channel.systemName) {
        return `${channel.name} / ${channel.systemName}`;
      } else if (channel.name) {
        return channel.name;
      } else if (channel.systemName) {
        return channel.systemName;
      } else {
        return "-";
      }
    } else {
      return "-";
    }
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
        className={classes.cardHeader}
        titleTypographyProps={{ variant: "subtitle2" }}
      />
      <CardContent className={classes.cardContent}>
        <Typography
          className={classes.currentchannel}
          variant="h5"
          component="h2"
        >
          {channel && (channel.tgTag || channel.tgID)
            ? channel.tgTag
              ? channel.tgTag
              : channel.tgID
            : "-"}
        </Typography>
        <div className={classes.grid}>
          <DataGrid
            classes={{
              root: classes.gridRoot,
              row: classes.rowRoot,
              cell: classes.cellRoot,
            }}
            rows={rows}
            columns={columns}
            headerHeight={0}
            isRowSelectable={(_) => false}
            hideFooter
          />
        </div>
      </CardContent>
      <CardActions className={classes.cardActions}>
        <Grid container direction="column" spacing={2}>
          <Grid item>
            <Grid container direction="row" justifyContent="center">
              <Button size="small">Skip</Button>
              <Button size="small">Hold</Button>
              <Button
                size="small"
                onClick={() => {
                  channel && op25.sendReloadOnChannel(channel.id);
                }}
              >
                Reload
              </Button>
              <Button size="small">GOTO</Button>
              <Tooltip title="Blacklist" placement="top" enterDelay={500}>
                <Button size="small">B/List</Button>
              </Tooltip>
              <Tooltip title="Whitelist" placement="top" enterDelay={500}>
                <Button size="small">W/List</Button>
              </Tooltip>
              <Tooltip title="Log Verbosity" placement="top" enterDelay={500}>
                <Button size="small">Log/V</Button>
              </Tooltip>
            </Grid>
          </Grid>
          <Grid item>
            <Grid container direction="row" justifyContent="center">
              <Tooltip title={`-${stepSizeLarge}`} placement="top">
                <IconButton size="small" className={classes.actionbuttons}>
                  <DoubleArrowsLeftIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title={`-${stepSizeSmall}`} placement="top">
                <IconButton size="small" className={classes.actionbuttons}>
                  <ArrowLeftIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title={`+${stepSizeSmall}`} placement="top">
                <IconButton size="small" className={classes.actionbuttons}>
                  <ArrowRightIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title={`+${stepSizeLarge}`} placement="top">
                <IconButton size="small" className={classes.actionbuttons}>
                  <DoubleArrowsRightIcon />
                </IconButton>
              </Tooltip>
            </Grid>
          </Grid>
        </Grid>
      </CardActions>
    </Card>
  );
};

export default ChannelDisplay;
