export interface TerminalConfig {
  module: string;
  terminalType: string;
  cursesPlotInterval: number;
  httpPlotInterval: number;
  httpPlotDirectory: string;
  tuningStepSizeSmall: number;
  tuningStepSizeLarge: number;
}
