import React from "react";
import ReactDOM from "react-dom";
import App from "./App";
import { store } from "./redux/app/store";
import { Provider } from "react-redux";
import { CssBaseline } from "@material-ui/core";
import "@fontsource/roboto";
import Theme from "./Theme";
import { OP25 } from "lib/op25";

const appStore = store;

OP25.getInstance().setStore(appStore);

ReactDOM.render(
  <React.StrictMode>
    <Provider store={appStore}>
      <Theme>
        <CssBaseline />
        <App />
      </Theme>
    </Provider>
  </React.StrictMode>,
  document.getElementById("root")
);
