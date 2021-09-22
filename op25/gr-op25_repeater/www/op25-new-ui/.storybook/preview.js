import { storeWithDummyData } from "redux/app/store";
import { Provider } from "react-redux";
import { CssBaseline } from "@material-ui/core";
import "@fontsource/roboto";
import Theme from "Theme";
import { OP25 } from "lib/op25";

export const parameters = {
  actions: {
    argTypesRegex: "^on[A-Z].*",
    argTypesRegex: "^fetch[A-Z].*",
    argTypesRegex: "^create[A-Z].*",
    argTypesRegex: "^update[A-Z].*",
  },
  controls: {
    matchers: {
      color: /(background|color)$/i,
      date: /Date$/,
    },
  },
};

const appStore = storeWithDummyData;

OP25.getInstance().setStore(appStore);

export const decorators = [
  (Story, context) => (
    <Provider store={appStore}>
      <Theme
        theme={
          context?.parameters?.theme ? context.parameters.theme : "default"
        }
      >
        <CssBaseline />
        <Story />
      </Theme>
    </Provider>
  ),
];
