import { createTheme, ThemeProvider } from "@material-ui/core";
import { useAppSelector } from "./redux/app/hooks";
import { selectIsDarkMode } from "./redux/slices/preferences/preferencesSlice";

import { blue } from "@material-ui/core/colors";

interface ThemeFuncProps {
  useDarkMode?: boolean;
}

interface ThemeComponentProps {
  children: any;
}

const theme = ({ useDarkMode }: ThemeFuncProps = {}) =>
  createTheme({
    palette: {
      type: useDarkMode === false ? "light" : "dark",
      secondary: {
        main: blue[500],
      },
    },
  });

const Theme = ({ children }: ThemeComponentProps) => {
  const darkmode = useAppSelector(selectIsDarkMode);
  return (
    <ThemeProvider theme={theme({ useDarkMode: darkmode })}>
      {children}
    </ThemeProvider>
  );
};

export default Theme;
