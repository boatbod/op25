import { createTheme, ThemeProvider } from "@material-ui/core";
import { useAppSelector } from "./redux/app/hooks";
import { selectIsDarkMode } from "./redux/slices/preferences/preferencesSlice";

import { blue } from "@material-ui/core/colors";

interface ThemeFuncProps {
  useDarkMode?: boolean;
}

interface ThemeComponentProps {
  children: any;
  theme?: "default" | "light" | "dark";
}

const themeCreator = ({ useDarkMode }: ThemeFuncProps = {}) =>
  createTheme({
    palette: {
      type: useDarkMode === false ? "light" : "dark",
      secondary: {
        main: blue[500],
      },
    },
  });

const Theme = ({ children, theme = "default" }: ThemeComponentProps) => {
  const preferencesDarkMode = useAppSelector(selectIsDarkMode);
  const darkmode = theme === "default" ? preferencesDarkMode : theme === "dark";

  return (
    <ThemeProvider theme={themeCreator({ useDarkMode: darkmode })}>
      {children}
    </ThemeProvider>
  );
};

export default Theme;
