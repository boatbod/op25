import { createTheme, ThemeProvider } from "@material-ui/core";
import { useAppSelector } from "./redux/app/hooks";
import { selectIsDarkMode } from "./redux/slices/preferences/preferencesSlice";

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
